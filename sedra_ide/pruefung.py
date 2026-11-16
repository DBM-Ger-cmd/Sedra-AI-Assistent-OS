"""Pruefskript Sedra IDE (Spec Runde 2). Aufruf: python pruefung.py ; Exit-Code 0 = alles gruen.

Geprueft je Datei: Zeilenzahl <= 400, keine Netzadressen, kein eval / new Function,
keine Hex-Farben ausserhalb von css/tokens.css, kein innerHTML, localStorage nur in zustand.js,
kein setInterval, kein fetch/XMLHttpRequest. Dazu: gleiche Textschluessel in de und en,
jeder benutzte Textschluessel vorhanden, jede eingebundene Datei vorhanden.
"""
import re
import sys
from pathlib import Path

ORT = Path(__file__).resolve().parent
GRENZE = 400
ENDUNGEN = {".html", ".css", ".js", ".py", ".md"}
# Einzige erlaubte Adresse: Kennung des SVG-Namensraums (kein Abruf).
ERLAUBT = {"http://www.w3.org/2000/svg"}
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
ADRESSE = re.compile(r"(?:https?:)?//[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z]{2,}[^\s'\"<>)]*")
VERBOTEN = [
    ("eval", re.compile(r"\beval\s*\(")),
    ("new Function", re.compile(r"\bnew\s+Function\b")),
    ("innerHTML", re.compile(r"\b(?:innerHTML|outerHTML|insertAdjacentHTML|document\.write)\b")),
    ("setInterval", re.compile(r"\bsetInterval\b")),
    ("Netzabruf", re.compile(r"\b(?:fetch\s*\(|XMLHttpRequest|WebSocket|EventSource|importScripts|sendBeacon)")),
    ("@latest", re.compile(r"@latest")),
]


def dateien():
    return sorted(p for p in ORT.rglob("*") if p.is_file() and p.suffix in ENDUNGEN and "__pycache__" not in p.parts)


def schluessel(pfad):
    text = pfad.read_text(encoding="utf-8")
    return set(re.findall(r"(?:^|[\s,{])([a-zA-Z_][\w]*):\s*'", text, flags=re.M)) | set(
        re.findall(r"(?:^|[\s,{])([a-zA-Z_][\w]*):\s*\"", text, flags=re.M))


def main():
    fehler = []
    zeilen_liste = []
    selbst = Path(__file__).resolve()
    for p in dateien():
        rel = p.relative_to(ORT).as_posix()
        text = p.read_text(encoding="utf-8")
        n = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
        zeilen_liste.append((n, rel))
        if n > GRENZE:
            fehler.append(f"{rel}: {n} Zeilen (Grenze {GRENZE})")
        if p == selbst or p.suffix == ".md":
            continue
        for nr, zeile in enumerate(text.split("\n"), 1):
            for adr in ADRESSE.findall(zeile):
                if adr not in ERLAUBT:
                    fehler.append(f"{rel}:{nr}: Netzadresse {adr}")
            for name, muster in VERBOTEN:
                if muster.search(zeile):
                    fehler.append(f"{rel}:{nr}: verboten: {name}")
            if rel != "css/tokens.css" and p.suffix in {".css", ".js", ".html"} and HEX.search(zeile):
                fehler.append(f"{rel}:{nr}: Hex-Farbe {HEX.search(zeile).group(0)}")
            if "localStorage" in zeile and rel != "js/zustand.js":
                fehler.append(f"{rel}:{nr}: localStorage ausserhalb von js/zustand.js")
    # localStorage nur in try-Bloecken
    zustand = (ORT / "js" / "zustand.js").read_text(encoding="utf-8")
    for nr, zeile in enumerate(zustand.split("\n"), 1):
        if "root.localStorage" in zeile and "try" not in zeile and "try" not in "".join(zustand.split("\n")[max(0, nr - 3):nr]):
            fehler.append(f"js/zustand.js:{nr}: localStorage ohne try")
    # Texte
    de, en = schluessel(ORT / "js" / "texte_de.js"), schluessel(ORT / "js" / "texte_en.js")
    for k in sorted(de - en):
        fehler.append(f"Text fehlt in en: {k}")
    for k in sorted(en - de):
        fehler.append(f"Text fehlt in de: {k}")
    benutzt = set()
    praefixe = set()
    for p in (ORT / "js").glob("*.js"):
        t = p.read_text(encoding="utf-8")
        benutzt |= set(re.findall(r"\bT\('([a-zA-Z_]\w*)'", t))
        benutzt |= set(re.findall(r"\b(?:key|_key): '([a-zA-Z_]\w*)'", t))
        benutzt |= set(re.findall(r"'((?:leer|pb|au_lauf)_\w+)'", t))
        praefixe |= set(re.findall(r"\bT\('([a-zA-Z_]\w*_)' \+", t))
    for k in sorted(benutzt - de):
        if k + "_" in praefixe or any(x.startswith(k) for x in de) and k.endswith("_"):
            continue
        fehler.append(f"Textschluessel benutzt, aber nicht vorhanden: {k}")
    for pr in sorted(praefixe):
        if not any(x.startswith(pr) for x in de):
            fehler.append(f"Kein Text mit Vorsatz: {pr}")
    # Eingebundene Dateien
    index = (ORT / "index.html").read_text(encoding="utf-8")
    for ref in re.findall(r"(?:src|href)=\"([^\"#]+)\"", index):
        if not (ORT / ref).is_file():
            fehler.append(f"index.html: Datei fehlt: {ref}")
    eingebunden = set(re.findall(r"src=\"js/([^\"]+)\"", index))
    for p in (ORT / "js").glob("*.js"):
        if p.name not in eingebunden:
            fehler.append(f"js/{p.name} ist nicht in index.html eingebunden")

    print("Zeilen je Datei (Grenze %d):" % GRENZE)
    for n, rel in zeilen_liste:
        print(f"  {n:4d}  {rel}")
    print(f"Dateien: {len(zeilen_liste)}, Zeilen gesamt: {sum(n for n, _ in zeilen_liste)}")
    print(f"Textschluessel: de {len(de)}, en {len(en)}, benutzt {len(benutzt)}")
    if fehler:
        print(f"ROT: {len(fehler)} Befunde")
        for f in fehler:
            print("  " + f)
        return 1
    print("GRUEN: keine Befunde")
    return 0


if __name__ == "__main__":
    sys.exit(main())
