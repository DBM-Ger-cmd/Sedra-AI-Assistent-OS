"""Berater-Schritt des Baus: ein Cloud-Modell (NVIDIA) schlaegt eine korrigierte Fassung der Dateien vor. Ohne Werkzeuge, nur Text.

Die Antwort wird nie direkt uebernommen: die Schleife schreibt sie in einen neuen Kandidaten und prueft die Stufe in der microVM.
Schluessel und Modell kommen aus den Einstellungen von SEDRA (Anbieter nvidia, gespeicherter Schluessel, Modell).
Ist der Berater nicht eingerichtet, sagt berater_status() den Grund, und der Bau laeuft ohne ihn weiter.

Aufruf (Pruefung ohne Netz):  python benchmarks/berater.py status
"""
import os
import re
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
PROVIDER = "nvidia"
AUFGABE_TYP = "code_und_spec_des_baus"      # Aufgabentyp laut Gesetzen (config/manager/gesetze.yaml)
MAX_DATEI = 20000
TRENNER = re.compile(r"^=== DATEI: (\S+) ===$", re.MULTILINE)
ENDE = "=== ENDE ==="


def _config():
    import yaml
    with (RUNTIME / "config" / "cloud_providers.yaml").open(encoding="utf-8") as f:
        return yaml.safe_load(f)["cloud_providers"]


SEDRA_ROOT = RUNTIME.parent / "workspace" / "SEDRA_OS"     # hier liegen die Einstellungen und der Schluessel-Speicher der Captain-Einrichtung


def _festes_modell():
    """Das feste Berater-Modell aus config/manager/berater.yaml (Captain-Entscheidung)."""
    import yaml
    pfad = RUNTIME / "config" / "manager" / "berater.yaml"
    if not pfad.exists():
        return None
    return (yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}).get("berater", {}).get("modell")


def berater_status(root=SEDRA_ROOT):
    """(ok, grund). Liest den Stand aus den Einstellungen von SEDRA (Anbieter, Modell, Schluessel-Status), nie einen Schluesselwert."""
    from sedra_runtime import cloud_settings as cs
    v = cs.view(Path(root), cs.CloudKeyStore(cs.key_store_path(Path(root))))
    if not v.get("enabled"):
        return False, "Cloud-Hauptschalter aus"
    eintrag = next((p for p in v.get("providers", []) if p["id"] == PROVIDER), None)
    if eintrag is None or not eintrag.get("enabled"):
        return False, f"Anbieter {PROVIDER} aus"
    if eintrag.get("status") != "bereit":
        return False, f"Anbieter {PROVIDER} nicht bereit: {', '.join(eintrag.get('reasons') or []) or eintrag.get('status')}"
    # Reihenfolge: Umgebungsvariable (zum Testen), dann die Wahl aus den Fähigkeitstests (Manager), dann das feste Modell, dann der Standard
    from sedra_runtime.manager.modellwahl import waehle_modell
    gewaehlt = waehle_modell(AUFGABE_TYP, Path(root) / "wissen_quellen" / "modelle")
    modell = os.environ.get("SEDRA_BAU_BERATER_MODELL", "").strip() or gewaehlt or _festes_modell() or eintrag.get("default_model")
    return (True, modell) if modell else (False, "kein Modell eingestellt")


def _prompt(fehlerbericht, dateien):
    teile = [
        "Du bist Berater eines Software-Baus. Unten stehen der Fehlerbericht eines Tests und die betroffenen Dateien.",
        "Antworte NUR mit den korrigierten Dateien, jede Datei so:",
        "=== DATEI: <Pfad> ===",
        "<vollstaendiger Inhalt der Datei>",
        "=== ENDE ===",
        "Aendere nur, was der Fehlerbericht verlangt. Erfinde keine Felder, die in den Regeln nicht stehen.",
        "",
        "FEHLERBERICHT:",
        fehlerbericht,
        "",
    ]
    for pfad, text in dateien.items():
        teile += [f"DATEI {pfad}:", text[:MAX_DATEI], ""]
    return "\n".join(teile)


def parse_antwort(text):
    """Liest die Dateien aus der Antwort. Gibt {pfad: inhalt} zurueck; Pfade mit '..' oder absolute werden verworfen."""
    treffer = list(TRENNER.finditer(text))
    out = {}
    for n, m in enumerate(treffer):
        pfad = m.group(1)
        if pfad.startswith(("/", "\\")) or ":" in pfad or ".." in Path(pfad).parts:
            continue
        ende = treffer[n + 1].start() if n + 1 < len(treffer) else len(text)
        inhalt = text[m.end():ende]
        inhalt = inhalt.split(ENDE)[0].strip("\n") + "\n"
        out[pfad] = inhalt
    return out


def berater_fragen(fehlerbericht, dateien, root=SEDRA_ROOT, audit=None):
    """Fragt den Berater ueber SEDRA (labor.cloud_chat: Inhaltsschutz und Audit wie bei jedem Cloudaufruf).
    Gibt {pfad: neuer Inhalt} zurueck. Fehler kommen als ValueError, ohne Schluesselwert."""
    from sedra_runtime import cloud_settings as cs
    from sedra_runtime import labor
    ok, modell = berater_status(root)
    if not ok:
        raise ValueError(f"Berater nicht eingerichtet: {modell}")
    root = Path(root)
    # Schritt 1 der Manager-Verfassung: jede Cloud-Anfrage des Baus wird vorher gegen die Gesetze geprueft und ins Journal geschrieben.
    from sedra_runtime.manager import Manager, VerfassungsVerstoss
    manager = Manager("berater", set(), journal=root / "runtime_data" / "manager" / "journal.jsonl")
    try:
        manager.pruefe_auftrag(AUFGABE_TYP, cloud=True)
    except VerfassungsVerstoss as exc:
        raise ValueError(f"Gesetz verletzt, Cloud-Anfrage nicht gesendet: {exc}") from None
    cfg = cs.load_config(root)
    store = cs.CloudKeyStore(cs.key_store_path(root))
    if audit is None:      # der Inhaltsschutz verlangt ein Audit; ohne Audit blockiert er den Aufruf (SG_AUDIT_FAILED)
        from sedra_runtime.core.audit import AuditLog
        protokoll = AuditLog(root / "runtime_data" / "audit" / "events.jsonl")
        audit = protokoll          # der Inhaltsschutz ruft audit.append(...) selbst auf
    antwort = labor.cloud_chat(cfg, PROVIDER, modell, [{"role": "user", "content": _prompt(fehlerbericht, dateien)}],
                               environ=os.environ, key_store=store, audit=audit)
    text = (antwort.get("reply") or antwort.get("content") or "") if isinstance(antwort, dict) else ""      # labor.cloud_chat liefert 'reply'
    neu = parse_antwort(text)
    if not neu:
        raise ValueError("Berater-Antwort ohne Dateien")
    return neu


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "status":
        ok, grund = berater_status()
        print("bereit" if ok else "nicht bereit", "-", grund)
        sys.exit(0 if ok else 1)
    print(__doc__)
