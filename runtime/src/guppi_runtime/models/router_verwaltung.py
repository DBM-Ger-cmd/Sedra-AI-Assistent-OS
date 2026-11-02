"""Der Sedra-Modell-Router: Sedra startet den llama-server im Router-Modus selbst (statt dass der Captain ihn von Hand starten muss),
schreibt dessen Modellliste (eine Datei mit einem Abschnitt je Rezept, aus denselben Argumenten wie beim eigenen Server) und startet ihn
neu, wenn sich der Abschnitt des geladenen Modells ändert (z. B. ein anderes Kontextfenster). Ein Router, den ein anderer Client gestartet
hat (Pi, StarNet), wird weder angefasst noch beendet; dann bleibt es beim bisherigen Weg (nur Laden und Entladen über den Router).

Dateien unter `<state_dir>/router/`: optionen.json (Automatik, models_max, Leerlauf), modelle.ini (die Modellliste), abschnitte.json
(die Abschnitte aller bisher geladenen Rezepte), router.pid (der eigene Prozess, damit ein Neustart von Sedra ihn wiederfindet), router.log."""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

from .runtime_control import RuntimeControlError

STANDARD = {"auto_start": True, "models_max": 1, "sleep_idle_s": 900}
OHNE_WERT = {"no-webui", "no-mmproj"}                 # Schalter ohne Wert, im Abschnitt überflüssig
NICHT_IM_ABSCHNITT = {"host", "port", "alias"}        # die setzt der Router selbst (Abschnittsname = Modell-ID)


def abschnitt_aus_argv(argv):
    """{Schlüssel: Wert} eines Abschnitts aus der Argumentliste des eigenen Servers (Programm vorn)."""
    out, i = {}, 1
    while i < len(argv):
        a = str(argv[i])
        if not a.startswith("-"):
            i += 1; continue
        key = a.lstrip("-")
        if key == "no-jinja":
            out["jinja"] = "false"; i += 1; continue
        if key in OHNE_WERT:
            i += 1; continue
        wert = str(argv[i + 1]) if i + 1 < len(argv) else ""
        i += 2
        if key in NICHT_IM_ABSCHNITT:
            continue
        out["model" if key == "m" else key] = wert
    return out


def preset_text(abschnitte):
    zeilen = ["; Vom Sedra-Modell-Router geschrieben, wird bei jeder Aenderung neu erzeugt (nicht von Hand aendern).", "version = 1", ""]
    for rid, kv in sorted(abschnitte.items()):
        zeilen.append(f"[{rid}]")
        zeilen += [f"{k} = {v}" for k, v in kv.items()]
        zeilen.append("")
    return "\n".join(zeilen)


def _http_gesund(get_json, endpoint):
    try:
        return get_json(endpoint + "/health")[0] == 200
    except Exception:
        return False


def _kill_baum(proc):
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.kill()


def _pid_lebt(pid):
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True).stdout or b""      # Bytes: die Codepage der Ausgabe ist egal, es geht nur um die Nummer
        return str(pid) in out.decode("utf-8", "replace")
    try:
        os.kill(pid, 0); return True
    except OSError:
        return False


class RouterVerwaltung:
    def __init__(self, *, endpoint, executable_dir, vendor_dir, ordner, standard=None, popen=subprocess.Popen, get_json=None, sleep=time.sleep,
                 mono=time.monotonic, kill=_kill_baum, pid_lebt=_pid_lebt, audit=None, startup_timeout_s=90):
        from .llama_server_runtime import _http_json
        self.endpoint, self.exe_dir, self.vendor_dir = endpoint, Path(executable_dir), Path(vendor_dir) if vendor_dir else None
        self.ordner = Path(ordner)
        self.standard = dict(STANDARD, **(standard or {}))
        self._popen, self._get_json, self._sleep, self._mono = popen, get_json or _http_json, sleep, mono
        self._kill, self._pid_lebt, self.audit, self.startup_timeout_s = kill, pid_lebt, audit, startup_timeout_s
        self._proc, self._pid = None, None
        self._abschnitte, self._text = self._lesen("abschnitte.json", {}), None
        pid = self._lesen("router.pid", None)
        if type(pid) is int and self._pid_lebt(pid):
            self._pid = pid                                    # ein früher von Sedra gestarteter Router läuft noch: wieder übernehmen

    # ---- Dateien
    def _lesen(self, name, standard):
        try:
            return json.loads((self.ordner / name).read_text(encoding="utf-8"))
        except Exception:
            return standard

    def _schreiben(self, name, daten):
        self.ordner.mkdir(parents=True, exist_ok=True)
        (self.ordner / name).write_text(json.dumps(daten, ensure_ascii=False, indent=1), encoding="utf-8")

    @property
    def preset(self):
        return self.ordner / "modelle.ini"

    # ---- Optionen (vom Captain im Fenster „Modellserver“ gesetzt)
    def optionen(self):
        gespeichert = self._lesen("optionen.json", {})
        out = dict(self.standard)
        for k in out:
            if k in gespeichert and type(gespeichert[k]) is type(out[k]):
                out[k] = gespeichert[k]
        return out

    def optionen_setzen(self, neu):
        aktuell = self.optionen()
        for k, wert in (neu or {}).items():
            if k not in aktuell:
                raise ValueError(f"router_option_unbekannt:{k}")
            if type(wert) is not type(aktuell[k]):
                raise ValueError(f"router_option_ungueltig:{k}")
            if k == "models_max" and not 1 <= wert <= 8: raise ValueError("router_option_ungueltig:models_max")
            if k == "sleep_idle_s" and not 0 <= wert <= 86400: raise ValueError("router_option_ungueltig:sleep_idle_s")
            aktuell[k] = wert
        self._schreiben("optionen.json", aktuell)
        return aktuell

    # ---- Zustand
    def laeuft(self):
        return _http_gesund(self._get_json, self.endpoint)

    def eigen(self):
        if self._proc is not None and self._proc.poll() is None:
            return True
        if self._pid is not None and self._pid_lebt(self._pid):
            return True
        self._proc, self._pid = None, None
        return False

    def status(self):
        laeuft = self.laeuft()
        return {"laeuft": laeuft, "eigen": laeuft and self.eigen(), "endpoint": self.endpoint, "optionen": self.optionen(),
                "modelle": sorted(self._abschnitte), "preset": str(self.preset), "log": str(self.ordner / "router.log")}

    def ergaenzen(self, abschnitte):
        """Abschnitte für Rezepte, die noch nicht geladen wurden (damit die Liste beim Start alle Modelle kennt); vorhandene bleiben unverändert."""
        neu = {k: v for k, v in (abschnitte or {}).items() if k not in self._abschnitte}
        if neu:
            self._abschnitte.update(neu)
            self._schreiben("abschnitte.json", self._abschnitte)
        return sorted(neu)

    # ---- Start und Ende
    def _befehl(self):
        opt = self.optionen()
        port = urlsplit(self.endpoint).port or 8090
        return [str(self.exe_dir / "llama-server.exe"), "--models-preset", str(self.preset), "--models-max", str(opt["models_max"]), "--host", "127.0.0.1",
                "--port", str(port), "--no-webui", "--sleep-idle-seconds", str(opt["sleep_idle_s"])]

    def starten(self):
        if self.laeuft():
            raise RuntimeControlError("router_laeuft_schon")
        if not self._abschnitte:
            raise RuntimeControlError("router_ohne_modelle")
        self.ordner.mkdir(parents=True, exist_ok=True)
        self.preset.write_text(preset_text(self._abschnitte), encoding="utf-8")
        self._text = preset_text(self._abschnitte)
        env = dict(os.environ)
        env["PATH"] = os.pathsep.join(str(p) for p in (self.exe_dir, self.vendor_dir) if p) + os.pathsep + env.get("PATH", "")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        log = self.ordner / "router.log"
        with log.open("wb") as f:
            self._proc = self._popen(self._befehl(), cwd=str(self.exe_dir), env=env, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, shell=False, creationflags=flags)
        self._pid = None
        began = self._mono()
        while not self.laeuft():
            if self._proc.poll() is not None:
                code = self._proc.poll(); self._proc = None
                raise RuntimeControlError(f"router_beendet_beim_start:{code}")
            if self._mono() - began > self.startup_timeout_s:
                self._kill(self._proc); self._proc = None
                raise RuntimeControlError(f"router_start_zeitueberschreitung:{self.startup_timeout_s}s")
            self._sleep(0.5)
        self._schreiben("router.pid", self._proc.pid)
        self._log("ROUTER_GESTARTET", pid=self._proc.pid, modelle=sorted(self._abschnitte), sekunden=round(self._mono() - began, 1))
        return self.status()

    def beenden(self):
        if not self.laeuft():
            return self.status()
        if not self.eigen():
            raise RuntimeControlError("router_fremd")      # den hat ein anderer Client gestartet: nicht anfassen
        pid = self._proc.pid if self._proc is not None else self._pid
        self._kill(self._proc if self._proc is not None else type("P", (), {"pid": pid})())
        began = self._mono()
        while self.laeuft() and self._mono() - began < 15:
            self._sleep(0.3)
        self._proc, self._pid = None, None
        try: (self.ordner / "router.pid").unlink()
        except OSError: pass
        self._log("ROUTER_BEENDET", pid=pid)
        return self.status()

    def bereitstellen(self, rid, abschnitt):
        """Vor dem Laden eines Modells: der Router muss laufen und den Abschnitt `rid` mit genau diesen Werten kennen.
        Rückgabe: "bereit" (nichts zu tun), "gestartet" (neu gestartet), "fremd" (ein fremder Router läuft, nichts getan), "aus" (Automatik ausgeschaltet)."""
        laeuft = self.laeuft()
        if laeuft and not self.eigen():
            return "fremd"
        if not laeuft and not self.optionen()["auto_start"]:
            return "aus"
        neu = dict(self._abschnitte); neu[rid] = abschnitt
        text = preset_text(neu)
        if laeuft and text == (self._text if self._text is not None else (self.preset.read_text(encoding="utf-8") if self.preset.exists() else None)):
            return "bereit"
        if laeuft:
            self.beenden()                                      # der Abschnitt hat sich geändert: der Router liest die Liste nur beim Start
        self._abschnitte = neu
        self._schreiben("abschnitte.json", neu)
        self.starten()
        return "gestartet"

    def _log(self, ereignis, **payload):
        if self.audit:
            self.audit.append(ereignis, component="llama-server", payload=payload)
