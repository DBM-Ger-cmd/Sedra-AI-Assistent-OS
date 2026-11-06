"""Zerlegen einer Quelle in Abschnitte (Spec 7, D7.3, D7.6; Bau-Spec `wis_chunk`, Version `z2`): Blöcke eines Textes (Absatz,
Liste, Tabelle, Code), die Stücke eines Blocks unter einer Obergrenze (Listen an Punktgrenzen mit Einleitungszeile, Tabellen mit
wiederholter Kopfzeile), Markdown nach Überschriften, reiner Text, das Logbuch je Tabellenzeile, ein Eintrag eines Speichers; dazu
die einzeilige Stelle für die Kopfzeile des Datenblocks, der Abschnitts-Hash und der Eingabetext fürs Einbetten.

Rein: keine Datei, keine Uhr, keine Datenbank. Längen zählen Zeichen (`len`). Leerer oder nicht passender Text gibt `[]`;
ungültige Grenzen `ValueError('wis_zerlegen_grenzen')`, falsche Eingabe `ValueError('wis_zerlegen_eingabe')`."""
import hashlib
import re
import unicodedata

ZERLEGER_VERSION = "z2"
ZIEL_ZEICHEN = 1200
MAX_ZEICHEN = 1600
MIN_ZEICHEN = 80
EINLEITUNG_MAX = 200
KOPF_MAX = 160
_LISTE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_TRENNER = re.compile(r"^\s*\|?\s*:?-{2,}")
_KOPF = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_STRICHE = re.compile(r"([=\-])\1{2,}")


def _art(zeile):
    if _LISTE.match(zeile):
        return "liste"
    if zeile.lstrip().startswith("|"):
        return "tabelle"
    return "absatz"


def _grenzen(ziel, grenze):
    if type(ziel) is not int or type(grenze) is not int or ziel < 1 or grenze < ziel:
        raise ValueError("wis_zerlegen_grenzen")


def bloecke(zeilen):
    """Zeilen → Blöcke `{"art", "zeilen", "einleitung"}`. Code-Zäune werden nicht zerschnitten, Leerzeilen trennen; eine Liste
    oder Tabelle trägt als Einleitung die letzte Zeile des Absatzes direkt davor (höchstens EINLEITUNG_MAX Zeichen)."""
    if not isinstance(zeilen, (list, tuple)) or any(not isinstance(z, str) for z in zeilen):
        raise ValueError("wis_zerlegen_eingabe")
    out, offen = [], None
    for z in zeilen:
        if offen is not None and offen["art"] == "code":
            offen["zeilen"].append(z)
            if z.lstrip().startswith("```"):
                offen = None
            continue
        if z.lstrip().startswith("```"):
            offen = {"art": "code", "zeilen": [z], "einleitung": ""}
            out.append(offen)
            continue
        if not z.strip():
            offen = None
            continue
        art = _art(z)
        if offen is not None and offen["art"] == "liste" and art == "absatz" and z.startswith("  "):
            offen["zeilen"].append(z)
            continue
        if offen is None or offen["art"] != art:
            vorher = out[-1]["zeilen"][-1].strip()[:EINLEITUNG_MAX] if out and out[-1]["art"] == "absatz" else ""
            offen = {"art": art, "zeilen": [], "einleitung": vorher if art in ("liste", "tabelle") else ""}
            out.append(offen)
        offen["zeilen"].append(z)
    return out


def _schneide(text, ziel):
    """Ein Element über der Grenze in Stücke bis `ziel`, am letzten Leerzeichen, sonst hart."""
    teile = []
    while len(text) > ziel:
        schnitt = text.rfind(" ", 1, ziel + 1)
        if schnitt < 1:
            schnitt = ziel
        teile.append(text[:schnitt].rstrip())
        text = text[schnitt:].lstrip()
    if text:
        teile.append(text)
    return teile


def _packe(stuecke, ziel, vorspann=()):
    """Elemente gierig in Gruppen bis `ziel` packen; jede Gruppe beginnt mit dem Vorspann, das erste Element geht immer hinein."""
    gruppen, aktuell = [], []
    for s in stuecke:
        probe = list(vorspann) + aktuell + [s]
        if aktuell and len("\n".join(probe)) > ziel:
            gruppen.append("\n".join(list(vorspann) + aktuell))
            aktuell = []
        aktuell.append(s)
    if aktuell:
        gruppen.append("\n".join(list(vorspann) + aktuell))
    return gruppen


def _elemente(zeilen, ziel, grenze):
    out = []
    for z in zeilen:
        out += _schneide(z, ziel) if len(z) > grenze else [z]
    return out


def _listenpunkte(zeilen):
    punkte = []
    for z in zeilen:
        if _LISTE.match(z) or not punkte:
            punkte.append(z)
        else:
            punkte[-1] += "\n" + z
    return punkte


def teile_block(block, *, ziel=ZIEL_ZEICHEN, grenze=MAX_ZEICHEN):
    """Die Stücke eines Blocks, je rund `ziel` Zeichen: Absatz und Code nach Zeilen, Liste nach Punkten (Einleitung je Gruppe),
    Tabelle nach Zeilen mit wiederholter Kopfzeile. Bis `grenze` bleibt der Block ganz."""
    _grenzen(ziel, grenze)
    zeilen, art = list(block["zeilen"]), block["art"]
    text = "\n".join(zeilen)
    if len(text) <= grenze:
        return [text] if text.strip() else []
    vorspann = [block.get("einleitung")] if block.get("einleitung") else []
    if art == "liste":
        return _packe(_elemente(_listenpunkte(zeilen), ziel, grenze), ziel, vorspann)
    if art == "tabelle":
        kopf = 2 if len(zeilen) > 1 and _TRENNER.match(zeilen[1]) else 1
        if len(zeilen) > kopf:
            return _packe(_elemente(zeilen[kopf:], ziel, grenze), ziel, vorspann + zeilen[:kopf])
        return _packe(_elemente(zeilen, ziel, grenze), ziel)
    return _packe(_elemente(zeilen, ziel, grenze), ziel)


def _stuecke(bloecke_, ziel, grenze):
    """Stücke aller Blöcke; ein Absatz vor einer geteilten Liste oder Tabelle verliert seine letzte Zeile (sie ist die Einleitung)."""
    teile = [teile_block(b, ziel=ziel, grenze=grenze) for b in bloecke_]
    for i, b in enumerate(bloecke_[:-1]):
        folgt = bloecke_[i + 1]
        if b["art"] == "absatz" and folgt["einleitung"] and len(teile[i + 1]) > 1:
            teile[i] = teile_block(dict(b, zeilen=b["zeilen"][:-1]), ziel=ziel, grenze=grenze)
    return [s for t in teile for s in t]


def _abschnitt(stelle, zeilen, ziel, grenze):
    """Die Zeilen eines Abschnitts → Teile: Stücke gierig bis `ziel` zusammenfügen, Reste unter MIN_ZEICHEN an den Vorgänger."""
    stuecke = _stuecke(bloecke(zeilen), ziel, grenze)
    texte = []
    for s in stuecke:
        if texte and len(texte[-1]) + 2 + len(s) <= ziel:
            texte[-1] += "\n\n" + s
        else:
            texte.append(s)
    out = []
    for t in texte:
        t = t.strip()
        if len(t) < 3:
            continue
        if len(t) < MIN_ZEICHEN and out and len(out[-1]) + 2 + len(t) <= grenze:
            out[-1] += "\n\n" + t
        else:
            out.append(t)
    return [{"stelle": stelle, "teil": i, "text": t} for i, t in enumerate(out, 1)]


def zerlege_markdown(text, kopf, *, ziel=ZIEL_ZEICHEN, grenze=MAX_ZEICHEN):
    """Markdown nach Überschriften: Stelle = Pfad `H1 > H2 > …` (Stapel je Ebene), vor der ersten Überschrift `kopf`;
    Überschriften in Code-Zäunen zählen nicht. Rückgabe `[{"stelle", "teil", "text"}]`."""
    _grenzen(ziel, grenze)
    out, stack, zeilen, zaun = [], {}, [], False

    def schliessen():
        out.extend(_abschnitt(" > ".join(stack[k] for k in sorted(stack)) or kopf, zeilen, ziel, grenze))

    for z in str(text).splitlines():
        if z.lstrip().startswith("```"):
            zaun = not zaun
        m = None if zaun else _KOPF.match(z)
        if m:
            schliessen()
            zeilen = []
            stufe = len(m.group(1))
            for k in [k for k in stack if k >= stufe]:
                del stack[k]
            stack[stufe] = m.group(2)
        else:
            zeilen.append(z)
    schliessen()
    return out


def zerlege_text(text, kopf, *, ziel=ZIEL_ZEICHEN, grenze=MAX_ZEICHEN):
    """Reiner Text: ein Abschnitt mit Stelle `kopf`, nach den Regeln von `zerlege_markdown` geteilt."""
    _grenzen(ziel, grenze)
    return _abschnitt(kopf, str(text).splitlines(), ziel, grenze)


def zerlege_eintrag(stelle, text, *, ziel=ZIEL_ZEICHEN, grenze=MAX_ZEICHEN):
    """Ein Eintrag eines Speichers (Notiz, Regel, Zeile): wie `zerlege_text(text, stelle)`."""
    return zerlege_text(text, stelle, ziel=ziel, grenze=grenze)


def zerlege_logbuch(text, kopf):
    """Das Logbuch: jede Zeile `| 20…` ist ein eigener Abschnitt (Stelle `<Titel> > Zeile <Zeit> <Art> <Eintrag[:60]>`), alles
    Übrige ohne die Titelzeile ein Abschnitt mit dem Titel; erst der Rest, dann die Zeilen."""
    zeilen = str(text).splitlines()
    kopfzeile = next((z for z in zeilen if z.startswith("# ")), None)
    titel = kopfzeile[2:].strip() if kopfzeile is not None else kopf
    out, rest = [], []
    for z in zeilen:
        if z is kopfzeile:
            continue
        if z.startswith("| 20"):
            zellen = [c.strip() for c in z.strip().strip("|").split("|")]
            zeit, art, eintrag = (zellen + ["", "", ""])[:3]
            stelle = f"{titel} > Zeile {zeit} {art} {eintrag[:60]}"
            teile = _schneide(z, ZIEL_ZEICHEN) if len(z) > MAX_ZEICHEN else [z]      # auch eine lange Zeile bleibt unter der Grenze (F10)
            out.extend({"stelle": stelle, "teil": i, "text": t} for i, t in enumerate(teile, 1))
        else:
            rest.append(z)
    return _abschnitt(titel, rest, ZIEL_ZEICHEN, MAX_ZEICHEN) + out


def saeubere_stelle(stelle):
    """Eine Zeile für die Kopfzeile des Datenblocks (D7.6): Steuer-, Format- und Trennzeichen werden Leerzeichen, Weißraum
    fällt zusammen, Folgen von `===`/`---` werden zwei Zeichen, höchstens KOPF_MAX Zeichen; leer wird '?'."""
    zeichen = [" " if unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") else c for c in str(stelle)]
    eine = " ".join("".join(zeichen).split())
    eine = _STRICHE.sub(lambda m: m.group(1) * 2, eine)
    return eine[:KOPF_MAX].rstrip() or "?"


def abschnitt_hash(stelle, text, version=ZERLEGER_VERSION):
    """sha256 über `version|stelle|text`; eine neue Zerleger-Version ändert alle Hashes (gewollt, D7.3)."""
    return hashlib.sha256(f"{version}|{stelle}|{text}".encode("utf-8")).hexdigest()


def eingabetext(stelle, text):
    """Eingabeformat e1 fürs Einbetten: Stelle, Zeilenumbruch, Text."""
    return f"{stelle}\n{text}"


SPEICHER_NAMEN = {"knowledge": "Wissensnotiz", "arbeitsumfeld": "Arbeitsumfeld", "gateway": "KI-GateWay", "vorschlag": "Freigegebener Vorschlag"}


def dokumentname(datei):
    """Ein lesbarer Name der Herkunft: bei Dateien der Name ohne Endung (Unterstriche als Leerzeichen), bei Einträgen eines Speichers
    (`knowledge:KN-1`, `gateway:R-07`) der Name des Speichers."""
    datei = str(datei or "")
    vorn = datei.split(":", 1)[0]
    if ":" in datei and vorn in SPEICHER_NAMEN:
        return SPEICHER_NAMEN[vorn]
    name = datei.rsplit("/", 1)[-1]
    name = name.rsplit(".", 1)[0] if "." in name else name
    return " ".join(name.replace("_", " ").split()) or "?"


def _zellen(zeile):
    return [c.strip() for c in zeile.strip().strip("|").split("|")]


def tabellen_als_zeilen(text):
    """Markdown-Tabellen eines Abschnitts als „Spalte: Wert; Spalte: Wert“ je Zeile (S7.6 A1): so trägt jede Zeile im Vektor ihre
    Spaltennamen. Text ohne Tabelle (Kopfzeile + Trennzeile) bleibt, wie er ist; leere Zellen entfallen."""
    zeilen = str(text).split("\n")
    out, kopf, i = [], None, 0
    while i < len(zeilen):
        z = zeilen[i]
        if z.lstrip().startswith("|") and i + 1 < len(zeilen) and _TRENNER.match(zeilen[i + 1]) and zeilen[i + 1].lstrip().startswith("|"):
            kopf = _zellen(z)
            i += 2
            continue
        if kopf is not None and z.lstrip().startswith("|"):
            werte = _zellen(z)
            paare = [f"{k}: {v}" if k else v for k, v in zip(kopf + [""] * max(0, len(werte) - len(kopf)), werte) if v]
            out.append("; ".join(paare))
        else:
            kopf = None if not z.lstrip().startswith("|") else kopf
            out.append(z)
        i += 1
    return "\n".join(out)


def eingabetext_e2(datei, stelle, text):
    """Eingabeformat e2 fürs Einbetten (S7.6 A1, Muster „Contextual Retrieval“ ohne Modell): Dokument > Stelle, Zeilenumbruch,
    Text mit Tabellenzeilen als „Spalte: Wert“. Nur der Vektor sieht diese Form; Volltext und Datenblock behalten den Originaltext."""
    return f"{dokumentname(datei)} > {stelle}\n{tabellen_als_zeilen(text)}"
