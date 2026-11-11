"""Englische Fassung einer Arbeitsanweisung erzeugen, prüfen und freigeben (dritte Ebene, siehe manager/uebersetzung.py).

  python benchmarks/anweisung_uebersetzen.py erzeugen bau_coder --url http://127.0.0.1:8080 [--modell NAME]
  python benchmarks/anweisung_uebersetzen.py erzeugen bau_coder --rezept coder.local_primary [--projekt <ordner>]
      Das lokale Modell übersetzt und schärft; die Strukturprüfung entscheidet. Mit --url nimmt das Werkzeug einen laufenden llama-server (nur Loopback),
      mit --rezept startet es das Modell selbst (GPU-Lease, beendet fremde llama-server von SEDRA, braucht das Ja des Captains) und beendet es danach wieder.
      Ergebnis: runtime_data/manager/anweisung_vorschlaege/<typ>.en.md und <typ>.rueckuebersetzung.de.md (zur Kontrolle).
  python benchmarks/anweisung_uebersetzen.py status [typ]
      Zeigt je Anweisung, ob die englische Fassung gilt (frisch, freigegeben, Struktur) und warum nicht.
  python benchmarks/anweisung_uebersetzen.py freigeben bau_coder
      NUR der Captain: übernimmt den Vorschlag nach config/manager/arbeitsanweisungen/<typ>.en.md, nach erneuter Prüfung von Hash und Struktur.
"""
import argparse
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

from sedra_runtime.manager import lade_gesetze, uebersetzung  # noqa: E402
from sedra_runtime.manager.verfassung import CONFIG  # noqa: E402

VORSCHLAEGE = RUNTIME.parent / "runtime_data" / "manager" / "anweisung_vorschlaege"


def ordner():
    return CONFIG / lade_gesetze()["arbeitsanweisungen"]["ordner"]


def typen():
    return sorted(p.stem for p in ordner().glob("*.md") if p.stem != "README" and not p.stem.endswith(".en"))


def _ausfuehren(typ, fragen):
    erg = uebersetzung.erzeuge(typ, fragen, ordner(), VORSCHLAEGE)
    if not erg["ok"]:
        print("Abgelehnt von der Strukturprüfung, nichts geschrieben:")
        for p in erg["probleme"]:
            print("  -", p)
        return 2
    print(f"Vorschlag: {erg['pfad']}\nRückübersetzung zur Kontrolle: {erg['rueckuebersetzung']}\nDer Captain prüft beides und gibt mit `freigeben {typ}` frei.")
    return 0


def erzeugen(typ, url, modell):
    from sedra_runtime.models.openai_local import OpenAICompatibleLocalAdapter
    adapter = OpenAICompatibleLocalAdapter("anweisung_uebersetzen", url, timeout=300)
    if not adapter.health():
        print(f"Kein Modellserver unter {url}: erst ein Modell laden.")
        return 1

    def fragen(nachrichten):
        a = adapter.chat(nachrichten, model=modell, temperature=0.2, max_tokens=3000, reasoning_effort="none")
        return a.get("content") if isinstance(a, dict) else str(a)

    return _ausfuehren(typ, fragen)


def erzeugen_mit_modellstart(typ, rezept, projekt):
    """Startet das Modell wie der Bau (gleiche Laufzeit, Lease, Aufräumen) und beendet es am Ende. Nur nach dem Ja des Captains."""
    import os
    import tempfile
    sys.path.insert(0, str(RUNTIME / "benchmarks"))
    import cuda_crash_hunt as hunt  # noqa: E402
    import small_team as st  # noqa: E402
    from sedra_runtime.jobs.testlab import TestLab, default_path  # noqa: E402
    from sedra_runtime.models.gpu_preflight import clear_leftovers  # noqa: E402
    from sedra_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime  # noqa: E402
    projekt = Path(projekt)
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml")
    config.enabled = True
    laufzeit = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="anweisung_rt_")))
    spec = hunt.model_spec(rezept, projekt)
    with TestLab(default_path(projekt)).lease(os.environ.get("TESTLAB_OWNER", "anweisung_uebersetzen"), f"Anweisung {typ} uebersetzen", ttl_s=1800, wait_s=600, preflight=clear_leftovers):
        try:
            laufzeit.load_model(spec["alias"], context_length=spec["context"], gpu="max", identifier=spec["alias"], parallel=1, server={**spec["server"], "reasoning": "off"})
            post = st.post_factory(laufzeit.endpoint)

            def fragen(nachrichten):
                antwort = post({"model": spec["alias"], "messages": nachrichten, "temperature": 0.2, "max_tokens": 3000})
                return antwort["choices"][0]["message"]["content"]

            return _ausfuehren(typ, fragen)
        finally:
            laufzeit.unload_model(all_models=True)


def status(nur=None):
    for t in ([nur] if nur else typen()):
        p = uebersetzung.pruefe_fassung(t, ordner())
        print(f"{t}: " + ("englische Fassung gilt" if not p else "deutsch (" + "; ".join(p) + ")"))
    return 0


def freigeben(typ):
    p = uebersetzung.freigeben(typ, ordner(), VORSCHLAEGE)
    if p:
        print("Nicht übernommen:")
        for x in p:
            print("  -", x)
        return 2
    print(f"Übernommen: {ordner() / (typ + '.en.md')}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("erzeugen"); e.add_argument("typ"); e.add_argument("--url"); e.add_argument("--modell"); e.add_argument("--rezept"); e.add_argument("--projekt", default=str(RUNTIME.parent / "workspace" / "SEDRA_OS"))
    s = sub.add_parser("status"); s.add_argument("typ", nargs="?")
    f = sub.add_parser("freigeben"); f.add_argument("typ")
    a = ap.parse_args()
    if a.cmd == "erzeugen":
        if bool(a.url) == bool(a.rezept):
            raise SystemExit("erzeugen: genau eines von --url (laufender Server) oder --rezept (Modell selbst starten)")
        return erzeugen(a.typ, a.url, a.modell) if a.url else erzeugen_mit_modellstart(a.typ, a.rezept, a.projekt)
    return status(a.typ) if a.cmd == "status" else freigeben(a.typ)


if __name__ == "__main__":
    sys.exit(main())
