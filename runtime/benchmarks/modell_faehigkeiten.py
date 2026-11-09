"""Kleiner Fähigkeitstest der Cloud-Modelle (Anbieter nvidia): drei kurze Aufgaben je Modell, ohne personenbezogene Daten.

Prüft:
  antwort   antwortet das Modell überhaupt, und in welcher Zeit
  folgen    hält es das Ausgabeformat ein (nur das Wort OK)
  code      korrigiert eine einfache Funktion (add soll a + b liefern)
  json      liefert gültiges JSON mit dem geforderten Feld

Ergebnis: JSON und Markdown im Wissensquellen-Ordner, damit die Fähigkeiten später in die Wissensdatenbank können.
Aufruf: python benchmarks/modell_faehigkeiten.py <modell> [<modell> ...]   (ohne Angabe: die Testliste unten)
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
SEDRA_ROOT = RUNTIME.parent / "workspace" / "SEDRA_OS"
AUSGABE = SEDRA_ROOT / "wissen_quellen" / "modelle"
MIT_3D = False

# Textmodelle aus dem NVIDIA-Katalog (Bilder, Einbettungen und Sicherheitsprüfer ausgelassen)
STANDARD = [
    "nvidia/nemotron-3.5-lightning-30b-a3b", "nvidia/nemotron-3-super-120b-a12b", "nvidia/nemotron-nano-3-30b-a3b",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", "nvidia/llama-3.1-nemotron-70b-instruct", "nvidia/nemotron-4-340b-instruct",
    "google/gemma-4-31b-it", "google/gemma-3-12b-it", "google/gemma-3-4b-it",
    "meta/codellama-70b", "deepseek-ai/deepseek-coder-6.7b-instruct", "deepseek-ai/deepseek-v4.1-flash",
    "mistralai/mistral-large", "mistralai/codestral-22b-instruct-v0.1", "ibm/granite-34b-code-instruct",
    "moonshotai/kimi-k2.6", "minimaxai/minimax-m3.1-flash", "openai/gpt-oss-20b", "poolside/laguna-xs-2.1",
    "writer/palmyra-creative-122b", "bigcode/starcoder2-15b",
]

AUFGABEN = {
    "folgen": ("Antworte nur mit dem Wort OK.", lambda t: t.strip().strip(".").upper() == "OK"),
    "code": ("Diese Funktion soll a + b liefern, liefert aber a - b. Gib nur die korrigierte Funktion in Python zurück, ohne Erklärung.\n"
             "def add(a, b):\n    return a - b",
             lambda t: "a + b" in t.replace(" ", " ").replace("a+b", "a + b")),
    "json": ('Gib nur gültiges JSON zurück, ohne Text davor oder danach: {"zahl": 7}',
             lambda t: _ist_json_mit_zahl(t)),
}

# 3D-Test: kein Bildmodell für 3D im Katalog (Stand 09.11.2026). Geprüft wird, ob ein Textmodell ein 3D-Modell als Datei schreiben kann.
AUFGABEN_3D = {
    "obj_wuerfel": ("Schreibe eine Wavefront-OBJ-Datei für einen Würfel mit den Kanten der Länge 1, Mittelpunkt im Ursprung. "
                    "Acht Eckpunkte (v), sechs Flächen (f) mit je vier Eckpunkten. Gib nur den Dateiinhalt zurück, ohne Erklärung.",
                    lambda t: _ist_wuerfel_obj(t)),
}


def _ist_wuerfel_obj(text):
    t = text.strip().strip("`")
    if t.lower().startswith("obj"):
        t = t[3:]
    punkte = [z for z in t.splitlines() if z.strip().startswith("v ")]
    flaechen = [z for z in t.splitlines() if z.strip().startswith("f ")]
    if len(punkte) != 8 or len(flaechen) != 6:
        return False
    try:
        koordinaten = [[float(x) for x in z.split()[1:4]] for z in punkte]
    except ValueError:
        return False
    return all(abs(abs(c) - 0.5) < 1e-6 for k in koordinaten for c in k)


def _ist_json_mit_zahl(text):
    t = text.strip().strip("`")
    if t.startswith("json"):
        t = t[4:]
    try:
        return json.loads(t).get("zahl") == 7
    except (ValueError, AttributeError):
        return False


def pruefe_modell(modell):
    from sedra_runtime import cloud_settings as cs, labor
    from sedra_runtime.core.audit import AuditLog
    cfg = cs.load_config(SEDRA_ROOT)
    store = cs.CloudKeyStore(cs.key_store_path(SEDRA_ROOT))
    prot = AuditLog(SEDRA_ROOT / "runtime_data" / "audit" / "events.jsonl")
    ergebnis = {"modell": modell, "aufgaben": {}}
    alle = {**AUFGABEN, **AUFGABEN_3D} if MIT_3D else AUFGABEN
    for name, (frage, bewerte) in alle.items():
        t0 = time.monotonic()
        try:
            a = labor.cloud_chat(cfg, "nvidia", modell, [{"role": "user", "content": frage}], environ=os.environ, key_store=store, audit=prot)
            text = (a.get("reply") or a.get("content") or "") if isinstance(a, dict) else ""
            if isinstance(a, dict) and a.get("status") not in (None, "completed"):
                raise RuntimeError(f"status {a.get('status')} {a.get('reasons')}")
            ok = bool(bewerte(text))
            ergebnis["aufgaben"][name] = {"ok": ok, "sekunden": round(time.monotonic() - t0, 1), "antwort": text.strip()[:120]}
        except Exception as exc:
            ergebnis["aufgaben"][name] = {"ok": False, "sekunden": round(time.monotonic() - t0, 1), "fehler": f"{type(exc).__name__}: {str(exc)[:120]}"}
    ergebnis["antwortet"] = any("antwort" in v or "fehler" not in v for v in ergebnis["aufgaben"].values()) and \
        not all("fehler" in v for v in ergebnis["aufgaben"].values())
    return ergebnis


def schreibe(ergebnisse):
    AUSGABE.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    (AUSGABE / f"faehigkeiten_{stamp}.json").write_text(json.dumps(ergebnisse, ensure_ascii=False, indent=2), encoding="utf-8")
    zeilen = [f"# Fähigkeitstest der Cloud-Modelle ({stamp})", "",
              "Drei kurze Aufgaben je Modell: Folgen (OK), Code (add korrigieren), JSON. Ohne personenbezogene Daten.", "",
              "| Modell | antwortet | folgen | code | json | Zeit je Aufgabe (s) |", "|---|---|---|---|---|---|"]
    for e in ergebnisse:
        a = e["aufgaben"]
        zeit = "/".join(str(a[k]["sekunden"]) for k in ("folgen", "code", "json") if k in a)
        zeilen.append(f"| {e['modell']} | {'ja' if e['antwortet'] else 'nein'} | {'ja' if a['folgen']['ok'] else 'nein'} | "
                      f"{'ja' if a['code']['ok'] else 'nein'} | {'ja' if a['json']['ok'] else 'nein'} | {zeit} |")
    (AUSGABE / f"faehigkeiten_{stamp}.md").write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return AUSGABE / f"faehigkeiten_{stamp}.md"


def main(argv):
    global MIT_3D
    MIT_3D = "--3d" in argv
    argv = [a for a in argv if a != "--3d"]
    modelle = argv or STANDARD
    ergebnisse = []
    for m in modelle:
        e = pruefe_modell(m)
        ergebnisse.append(e)
        print(m, "antwortet" if e["antwortet"] else "keine Antwort", {k: v["ok"] for k, v in e["aufgaben"].items()}, flush=True)
    print("Bericht:", schreibe(ergebnisse))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
