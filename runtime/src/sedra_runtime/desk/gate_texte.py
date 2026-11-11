"""Die Risiko-Texte im Einbau-Gate (AM0-07, SPEC_APPS_v1_AM0_G2 §7): was der Captain liest, bevor er ein Werkzeug oder eine Vorgabe-Shell einbauen lässt.

Gebaut als Kandidat von SEDRAs Factory-Bau (`am0_gate_texte`, 10.11.2026), unverändert übernommen."""
RAHMEN = "läuft abgeschottet in einem eigenen Rahmen: ohne Token, ohne Netz, ohne Zugriff auf die Seite"
GRENZE = "nicht begrenzt: Rechenzeit und Speicher im Browser"

def leserouten_text(routen):
    if not isinstance(routen, list):
        return "Leserouten: keine"
    seen = set()
    paths = []
    for entry in routen:
        if isinstance(entry, str) and entry.startswith("GET "):
            path = entry[4:]
            if len(path) >= 1:
                if path not in seen:
                    seen.add(path)
                    paths.append(path)
    if not paths:
        return "Leserouten: keine"
    return "Leserouten: " + ", ".join(paths)

def risiken_werkzeug(routen, funde=None):
    result = [RAHMEN, GRENZE, leserouten_text(routen)]
    if isinstance(funde, list):
        for f in funde:
            if isinstance(f, str) and f:
                result.append(f)
    return result

def risiken_shell(funde=None):
    result = ["ohne eigenen Code und ohne eigenes CSS \u2013 die Oberfl\u00e4che baut der Rahmen des Vertrags (ui/frame.js)", "Routen: nur die festen Routen des Rahmens"]
    if isinstance(funde, list):
        for f in funde:
            if isinstance(f, str) and f:
                result.append(f)
    return result

def risiken(art, routen=None, funde=None):
    if art == "tool":
        return risiken_werkzeug(routen, funde)
    elif art == "shell":
        return risiken_shell(funde)
    else:
        raise ValueError("art")
