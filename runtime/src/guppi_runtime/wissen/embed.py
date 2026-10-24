"""Einbetten auf der CPU (Spec 7, D7.4; G2-S7-h, -i, -r): ein eigener `llama-server --embeddings` als getrennter Prozess auf
Port 8094 (nie 8089), `-ngl 0 --device none`, eigene PID-Datei, Alias `wissen-embed`, ohne GUPPI-Signatur. Kein Netz: HTTP nur an
`127.0.0.1` über einen Opener ohne Proxy (WIS-04). Keine Lease, kein VRAM; die GPU-Stufe ist S7.4b.

Pause (WIS-12): `TestLabZugang.lage()` liest nur die heutigen Tabellen von `testlab.db` (`holder`, `reservations`, `queue`) –
`bau`, solange ein Bau, eine Messung oder eine Reservierung die GPU hat; `dienst`, wenn nur der Modellserver für Chat und Agenten
läuft; sonst `frei`. Der Dienst nimmt nie `try_acquire`, `acquire` oder `lease` und ruft nie `clear_leftovers`.

Modell-ID: `<name>@<sha256 der GGUF, 12 Zeichen>#<pooling>#<dim>#e<eingabeformat>`; jede Änderung ist ein Modellwechsel (WIS-04)."""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import vektor

ALIAS = "wissen-embed"
HOST = "127.0.0.1"
START_WARTEN_S = 90.0
FEHLSTART_SPERRE_S = 600.0
NETZFEHLER = (OSError, http.client.HTTPException)        # auch IncompleteRead, RemoteDisconnected (Prüfung F11)


@dataclass(frozen=True)
class GpuLage:
    zustand: str                                  # 'frei' | 'dienst' | 'bau'
    grund: str = ""


class OhneGpuZugang:
    """Kein Testlabor (Tests, Rechner ohne GPU): die Lage ist immer frei."""

    def lage(self):
        return GpuLage("frei", "")


class TestLabZugang:
    """Die Lage der GPU aus den heutigen Tabellen von `testlab.db` (D7.4), nur lesend."""
    DIENST_EIGNER = frozenset({"guppi-uix"})

    def __init__(self, lab, *, dienst_eigner=DIENST_EIGNER):
        self.lab = lab
        self.dienst_eigner = frozenset(dienst_eigner)

    def lage(self):
        try:
            for r in self.lab.reservations():
                return GpuLage("bau", "reservierung:" + str(r.get("owner") or "?"))
            halter = self.lab.holder()
            if halter and not halter.get("stale"):
                eigner = str(halter.get("owner") or "?")
                if eigner in self.dienst_eigner:
                    return GpuLage("dienst", "lease:" + eigner)
                return GpuLage("bau", "lease:" + eigner)
            for runde in self.lab.queue(("running",)):
                return GpuLage("bau", "runde:" + str(runde.get("id") or "?"))
        except Exception as exc:                                   # ein unlesbares Labor hält die Aufnahme an, statt zu raten
            return GpuLage("bau", "testlab_unlesbar:" + (str(exc) or type(exc).__name__)[:80])
        return GpuLage("frei", "")


@dataclass(frozen=True)
class EmbedEinstellung:
    engine: Path | None
    gguf: Path | None
    gguf_sha256: str
    name: str
    port: int = 8094
    kontext: int = 8192
    stapel: int = 16
    pooling: str = ""
    cpu_threads: int | None = None
    leerlauf_s: float = 900.0
    anfrage_timeout_s: float = 5.0
    schritt_s: float = 120.0
    eingabeformat: str = "e1"
    dim: int = 1024
    start_warten_s: float = START_WARTEN_S

    def threads(self):
        return self.cpu_threads or max(2, (os.cpu_count() or 4) // 2)


def sha256_datei(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


class EmbeddingDienst:
    """Start, Prüfung, Stapel-Einbetten, Anfrage-Vektor und Stopp des eigenen Servers. `starter` (Vorgabe `subprocess.Popen`) und
    `merke_lesen`/`merke_schreiben` (Prüfsummen-Merker, z. B. `meta`) sind für Tests austauschbar."""

    def __init__(self, einstellung, *, gpu, audit, pid_datei, uhr=time.monotonic, starter=None, merke_lesen=None, merke_schreiben=None):
        self.e = einstellung
        self.gpu = gpu
        self.audit = audit
        self.pid_datei = Path(pid_datei)
        self.uhr = uhr
        self.starter = starter or subprocess.Popen
        self.merke_lesen = merke_lesen or (lambda: None)
        self.merke_schreiben = merke_schreiben or (lambda wert: None)
        self._proc = None
        self._fehlstarts = []
        self._letzte_anfrage = None
        self._pausiert = False
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self._start_lock = threading.RLock()                     # Start und Stopp nacheinander, nie zwei Starts zugleich (Takt, Desk, Hintergrundstart)

    # ---- Kennung und Bereitschaft
    def modell_id(self):
        return f"{self.e.name}@{(self.e.gguf_sha256 or '')[:12]}#{self.e.pooling or 'modell'}#{self.e.dim}#e{self.e.eingabeformat.lstrip('e')}"

    def bereit(self):
        """Ohne Start: Engine da, Modell da, Prüfsumme bekannt, keine zwei Fehlstarts in der Sperrzeit."""
        if not self.e.engine or not Path(self.e.engine).is_file():
            return False, "wis_engine_fehlt"
        if not self.e.gguf or not Path(self.e.gguf).is_file():
            return False, "wis_modell_fehlt"
        if not self.e.gguf_sha256:
            return False, "wis_modell_pruefsumme"
        if len(self._fehlstarts) >= 2 and self.uhr() - self._fehlstarts[-1] < FEHLSTART_SPERRE_S:
            return False, "wis_server_start"
        return True, ""

    def pruefsumme(self):
        """SHA-256 der GGUF gegen die Einstellung, einmal je Größe und Änderungszeit (gemerkt über `merke_*`)."""
        st = Path(self.e.gguf).stat()
        stempel = f"{st.st_size}:{st.st_mtime_ns}"
        gemerkt = self.merke_lesen()
        if gemerkt and gemerkt.startswith(stempel + ":"):
            sha = gemerkt.split(":", 2)[2]
        else:
            sha = sha256_datei(self.e.gguf)
            self.merke_schreiben(f"{stempel}:{sha}")
        if sha.lower() != self.e.gguf_sha256.lower():
            raise ValueError("wis_modell_pruefsumme")
        return sha

    # ---- HTTP, nur 127.0.0.1
    def _url(self, pfad):
        return f"http://{HOST}:{self.e.port}{pfad}"

    def _get(self, pfad, timeout):
        with self._opener.open(urllib.request.Request(self._url(pfad)), timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8") or "{}")

    def _post(self, pfad, body, timeout):
        req = urllib.request.Request(self._url(pfad), data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        with self._opener.open(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8") or "{}")

    def gesund(self, timeout=2.0):
        try:
            return self._get("/health", timeout).get("status") == "ok"
        except Exception:
            return False

    def _alias_passt(self, timeout=2.0):
        try:
            daten = self._get("/v1/models", timeout).get("data") or []
            return any(str(m.get("id") or "") == ALIAS for m in daten)
        except Exception:
            return False

    def einbette(self, texte, timeout=None):
        """`/v1/embeddings` für einen Stapel; Form und Dimension werden geprüft (`wis_server_antwort`), Zeit (`wis_server_zeit`)."""
        if not texte:
            return []
        try:
            out = self._post("/v1/embeddings", {"input": list(texte), "model": ALIAS}, timeout or max(30.0, 3.0 * len(texte)))
        except (TimeoutError, urllib.error.URLError, *NETZFEHLER) as exc:
            if isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError) or "timed out" in str(exc):
                raise ValueError("wis_server_zeit") from None
            raise ValueError("wis_server_antwort") from None
        except ValueError:                                        # kaputtes JSON
            raise ValueError("wis_server_antwort") from None
        daten = out.get("data") if isinstance(out, dict) else None
        if not isinstance(daten, list) or len(daten) != len(texte):
            raise ValueError("wis_server_antwort")
        vektoren = []
        for d in sorted(daten, key=lambda x: x.get("index", 0) if isinstance(x, dict) else 0):
            v = d.get("embedding") if isinstance(d, dict) else None
            if isinstance(v, list) and v and isinstance(v[0], list):
                v = v[0]
            if not isinstance(v, list) or len(v) != self.e.dim:
                raise ValueError("wis_server_antwort")
            vektoren.append(v)
        return vektoren

    # ---- Start und Stopp
    def _befehl(self):
        cmd = [str(self.e.engine), "-m", str(self.e.gguf), "--embeddings", "--host", HOST, "--port", str(self.e.port), "-ngl", "0", "--device", "none",
               "-t", str(self.e.threads()), "-c", str(self.e.kontext), "-b", str(self.e.kontext), "-ub", str(self.e.kontext), "-np", "1", "--alias", ALIAS]
        if self.e.pooling:
            cmd += ["--pooling", self.e.pooling]
        return cmd

    def _lebt(self):
        return self._proc is not None and self._proc.poll() is None

    def laeuft(self):
        return self._lebt() and self.gesund()

    def antwortet(self):
        """Läuft ein eigener Server (dieser Prozess oder einer aus der PID-Datei mit dem Alias)? Startet nichts."""
        if self._proc is not None:
            return self._lebt()
        return self.gesund(0.5) and self._alias_passt(0.5)

    def _schreibe_pid(self, pid):
        self.pid_datei.parent.mkdir(parents=True, exist_ok=True)
        self.pid_datei.write_text(json.dumps({"pid": pid, "port": self.e.port, "alias": ALIAS, "start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}), encoding="utf-8")

    def starte(self):
        """Server starten und prüfen: Prüfsumme, Port frei (sonst `wis_port_belegt`), `/health`, Prüfsatz mit `dim`.
        Zwei Fehlstarts → nicht bereit (`wis_server_start`). Rückgabe True, wenn er läuft. Nie zwei Starts zugleich."""
        with self._start_lock:
            try:
                return self._starte()
            except NETZFEHLER as exc:                             # Prüfsumme oder PID-Datei nicht lesbar/schreibbar (F11)
                raise ValueError("wis_server_start:" + (str(exc) or type(exc).__name__)[:60]) from None

    def _starte(self):
        if self.laeuft():
            return True
        ok, grund = self.bereit()
        if not ok:
            raise ValueError(grund)
        self.pruefsumme()
        if self.gesund(1.0):
            if self._alias_passt(1.0):                     # ein eigener Server aus einem früheren Lauf (PID-Datei) antwortet schon
                return True
            raise ValueError("wis_port_belegt")
        t0 = self.uhr()
        try:
            self._proc = self.starter(self._befehl(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            self._fehlstarts.append(self.uhr())
            raise ValueError("wis_server_start") from None
        self._schreibe_pid(self._proc.pid)
        frist = time.monotonic() + self.e.start_warten_s
        while time.monotonic() < frist and self._lebt():
            if self.gesund(1.0):
                break
            time.sleep(0.25)
        try:
            if not self.laeuft():
                raise ValueError("wis_server_start")
            probe = self.einbette(["Prüfsatz"], timeout=30.0)
            vektor.normiere(probe[0])
        except ValueError:
            self._fehlstarts.append(self.uhr())
            self.stoppe()
            raise
        self._letzte_anfrage = self.uhr()
        self.audit("WIS_EMBED_SERVER", {"aktion": "start", "pid": self._proc.pid, "port": self.e.port, "geraet": "cpu", "startzeit_s": round(self.uhr() - t0, 2)})
        return True

    def _pid_aus_datei(self):
        try:
            d = json.loads(self.pid_datei.read_text(encoding="utf-8"))
            return int(d["pid"]) if d.get("alias") == ALIAS and int(d.get("port", 0)) == self.e.port else None
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def stoppe(self):
        """Nur die eigene PID: der eigene Prozess, oder die PID der Datei, wenn auf dem eigenen Port ein Server mit dem Alias
        antwortet; sonst wird nichts angefasst. Unter `_start_lock`: ein Stopp fällt nie in einen laufenden Start."""
        with self._start_lock:
            return self._stoppe()

    def _stoppe(self):
        pid = None
        if self._proc is not None:
            pid = self._proc.pid
            if self._lebt():
                self._proc.terminate()
                try:
                    self._proc.wait(10)
                except Exception:
                    self._proc.kill()
            self._proc = None
        else:
            alt = self._pid_aus_datei()
            if alt and self.gesund(1.0) and self._alias_passt(1.0):
                try:
                    os.kill(alt, signal.SIGTERM)
                    pid = alt
                except OSError:
                    pid = None
        if pid is not None:
            try:
                self.pid_datei.unlink()
            except OSError:
                pass
            self.audit("WIS_EMBED_SERVER", {"aktion": "stop", "pid": pid, "port": self.e.port, "geraet": "cpu", "startzeit_s": None})
        return pid

    def leerlauf_pruefen(self):
        """Nach `leerlauf_s` ohne Anfrage den Server beenden (vom Takt gerufen)."""
        if self._lebt() and self._letzte_anfrage is not None and self.uhr() - self._letzte_anfrage > self.e.leerlauf_s:
            self.stoppe()
            return True
        return False

    # ---- Einbetten und Anfrage
    def lauf(self, offene, schreibe, *, markiere=None):
        """Ein Einbett-Schritt: Lage `bau` → Pause (einmal Audit `WIS_EINBETTEN_PAUSE`); sonst Stapel zu `stapel` Abschnitten, vor
        jedem Stapel die Lage neu, höchstens `schritt_s`. Scheitert ein Stapel, wird er einzeln nachgebettet; ein Abschnitt, der
        allein scheitert, geht an `markiere(nr, hash, grund)` und blockiert die folgenden nicht mehr (Prüfung F2). Antwortet der
        Server gar nicht mehr, endet der Schritt mit `fehler`. Rückgabe {geraet, eingebettet, dauer_s, ende, grund, uebersprungen}."""
        t0 = self.uhr()
        lage = self.gpu.lage()
        if lage.zustand == "bau":
            if not self._pausiert:
                self.audit("WIS_EINBETTEN_PAUSE", {"grund": lage.grund})
            self._pausiert = True
            return {"geraet": "cpu", "eingebettet": 0, "dauer_s": 0.0, "ende": "pause", "grund": lage.grund}
        self._pausiert = False
        eingebettet, ende, grund, uebersprungen = 0, "fertig", "", 0
        try:
            self.starte()
            while True:
                stapel = offene(self.e.stapel)
                if not stapel:
                    break
                try:
                    zeilen = [(nr, h, vektor.packe(v)) for (nr, _, h), v in zip(stapel, self.einbette([t for _, t, _ in stapel]))]
                except ValueError:
                    if markiere is None or not self.gesund(2.0):
                        raise
                    zeilen = []
                    for nr, t, h in stapel:
                        try:
                            zeilen.append((nr, h, vektor.packe(self.einbette([t])[0])))
                        except ValueError as exc:
                            if not self.gesund(2.0):
                                raise
                            markiere(nr, h, str(exc))
                            uebersprungen += 1
                eingebettet += schreibe(zeilen) if zeilen else 0
                self._letzte_anfrage = self.uhr()
                if self.uhr() - t0 >= self.e.schritt_s:
                    ende = "schritt"
                    break
                lage = self.gpu.lage()
                if lage.zustand == "bau":
                    ende, grund = "pause", lage.grund
                    break
        except (ValueError, *NETZFEHLER) as exc:
            ende, grund = "fehler", (str(exc) or type(exc).__name__)
        dauer = round(self.uhr() - t0, 3)
        self.audit("WIS_EINBETTEN", {"geraet": "cpu", "eingebettet": eingebettet, "dauer_s": dauer, "ende": ende, "grund": grund or None,
                                     "uebersprungen": uebersprungen})
        if ende == "pause" and not self._pausiert:
            self.audit("WIS_EINBETTEN_PAUSE", {"grund": grund})
            self._pausiert = True
        return {"geraet": "cpu", "eingebettet": eingebettet, "dauer_s": dauer, "ende": ende, "grund": grund, "uebersprungen": uebersprungen}

    def anfrage_vektor(self, frage, *, starten=True):
        """Die Frage einbetten (auch in der Lage `bau`, G2-S7-i); Zeitgrenze `anfrage_timeout_s`, sonst None → Volltext-Rückfall.
        Mit `starten=False` (die Suche) wird kein Server gestartet: läuft keiner, kommt sofort None (Prüfung F3)."""
        try:
            if starten:
                self.starte()
            elif not self.antwortet():
                return None
            v = self.einbette([frage], timeout=self.e.anfrage_timeout_s)[0]
            self._letzte_anfrage = self.uhr()
            return vektor.lese(vektor.packe(v), self.e.dim)
        except (ValueError, *NETZFEHLER):
            return None


def einstellung_aus(konfig):
    """`EmbedEinstellung` aus der Konfiguration (`konfig.Konfig`); Pfade über `local_paths` aufgelöst."""
    return EmbedEinstellung(engine=konfig.engine_pfad(), gguf=konfig.modell_pfad(), gguf_sha256=konfig.modell_sha256,
                           name=konfig.modell_name or (Path(konfig.modell).stem if konfig.modell else "kein-modell"), port=konfig.port,
                           kontext=konfig.kontext, stapel=konfig.stapel, pooling=konfig.pooling, cpu_threads=konfig.cpu_threads,
                           leerlauf_s=konfig.leerlauf_s, anfrage_timeout_s=konfig.anfrage_timeout_s, schritt_s=konfig.schritt_s,
                           eingabeformat=konfig.eingabeformat, dim=konfig.dim, start_warten_s=getattr(konfig, "start_warten_s", START_WARTEN_S))
