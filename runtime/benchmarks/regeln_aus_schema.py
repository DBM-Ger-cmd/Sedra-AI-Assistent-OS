"""Regelblätter aus den Factory-SDK-Schemata (docs/factory_sdk/schemas), fest im Bau-Werkzeug.

Erzeugt Klartext für Bau-Specs: Pflichtfelder, erlaubte Werte, Muster, verschachtelte Objekte,
Auswahl zwischen Formen (oneOf) und die Bedingungen (if/then, allOf). Die Bedingungen sind der Teil,
der beim Bau gefehlt hat; sie werden deshalb immer mit ausgegeben.

Aufruf:  python benchmarks/regeln_aus_schema.py <objekt> [<objekt> ...]    (ohne Angabe: alle)
Nur lesen. Ändert keine Schema-Datei.
"""
import json
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
SCHEMAS = HIER.parent.parent / "docs" / "factory_sdk" / "schemas"
COMMON = json.loads((SCHEMAS / "common.schema.json").read_text(encoding="utf-8"))["$defs"]
OBJEKTE = ["project", "workflow", "task_run", "artifact", "evidence", "approval"]


def aufloesen(node):
    """Löst $ref auf die gemeinsamen Typen auf (urn:...#/$defs/<name>)."""
    if isinstance(node, dict) and "$ref" in node:
        name = node["$ref"].split("#/$defs/")[-1]
        merged = dict(COMMON.get(name, {}))
        merged.update({k: v for k, v in node.items() if k != "$ref"})
        return merged
    return node


def wert(v):
    return json.dumps(v, ensure_ascii=False)


def feld_text(name, prop, pflicht):
    p = aufloesen(prop)
    teile = []
    if "const" in p:
        teile.append(f"genau {wert(p['const'])}")
    if "enum" in p:
        teile.append("erlaubt: " + ", ".join(wert(x) for x in p["enum"]))
    if "type" in p:
        t = p["type"]
        teile.append("Typ: " + (" oder ".join(t) if isinstance(t, list) else t))
    if "minimum" in p:
        teile.append(f"mindestens {p['minimum']}")
    if "maxItems" in p:
        teile.append(f"höchstens {p['maxItems']} Einträge")
    if "minLength" in p:
        teile.append(f"mindestens {p['minLength']} Zeichen")
    if "maxLength" in p:
        teile.append(f"höchstens {p['maxLength']} Zeichen")
    if "pattern" in p:
        teile.append("Muster " + p["pattern"])
    return ("PFLICHT " if pflicht else "optional ") + name + (": " + "; ".join(teile) if teile else "")


def bedingung_text(if_teil):
    """Klartext für ein if: {properties: {feld: {const|enum|not}}}."""
    saetze = []
    for feld, bed in (if_teil.get("properties") or {}).items():
        if "const" in bed:
            saetze.append(f"{feld} ist {wert(bed['const'])}")
        elif "enum" in bed:
            saetze.append(f"{feld} ist eines von " + ", ".join(wert(x) for x in bed["enum"]))
        elif "not" in bed and "const" in bed["not"]:
            saetze.append(f"{feld} ist nicht {wert(bed['not']['const'])}")
        elif "not" in bed and "enum" in bed["not"]:
            saetze.append(f"{feld} ist nicht " + " oder ".join(wert(x) for x in bed["not"]["enum"]))
        else:
            saetze.append(f"{feld} erfüllt eine Bedingung")
    return " und ".join(saetze) or "der Fall"


def dann_text(then_teil, ind):
    out = []
    for feld, bed in (then_teil.get("properties") or {}).items():
        b = aufloesen(bed)
        if "const" in b:
            out.append(f"{ind}  {feld} muss genau {wert(b['const'])} sein")
        elif "enum" in b:
            out.append(f"{ind}  {feld} muss einer von " + ", ".join(wert(x) for x in b["enum"]) + " sein")
        elif "minimum" in b:
            out.append(f"{ind}  {feld} muss mindestens {b['minimum']} sein")
        elif b.get("type") == "null":
            out.append(f"{ind}  {feld} muss leer (null) sein")
        elif "type" in b:
            out.append(f"{ind}  {feld} muss vom Typ {b['type']} sein")
    for pflicht in then_teil.get("required", []):
        out.append(f"{ind}  Pflichtfeld: {pflicht}")
    return out


def bedingungen(schema, ind, titel):
    """Alle if/then-Regeln einer Stufe (allOf-Liste) als Klartext."""
    out = []
    for n, regel in enumerate(schema.get("allOf", []), 1):
        if "if" not in regel:
            continue
        out.append(f"{ind}{titel} Regel {n}: Wenn {bedingung_text(regel['if'])}:")
        out.extend(dann_text(regel.get("then", {}), ind))
    return out


def objekt_text(schema, ind="", titel=""):
    out = []
    pflicht = set(schema.get("required", []))
    out.append(f"{ind}Pflichtfelder: {sorted(pflicht)}; zusätzliche Felder erlaubt: {schema.get('additionalProperties', True)}")
    for name, prop in schema.get("properties", {}).items():
        out.append(ind + "- " + feld_text(name, prop, name in pflicht))
        p = aufloesen(prop)
        if p.get("type") == "object" and "properties" in p:
            out.extend(objekt_text(p, ind + "    ", f"{titel}/{name}"))
        if p.get("type") == "array" and isinstance(p.get("items"), dict) and "properties" in p["items"]:
            out.append(ind + "    jeder Eintrag:")
            out.extend(objekt_text(p["items"], ind + "      ", f"{titel}/{name}[]"))
        if "oneOf" in p:
            out.append(ind + "    eine von diesen Formen (jede ist ein eigenes Objekt):")
            for n, alt in enumerate(p["oneOf"], 1):
                out.append(ind + f"      Form {n}:")
                out.extend(objekt_text(alt, ind + "        ", f"{titel}/{name}#{n}"))
        if "allOf" in p and name == "*":
            pass
    out.extend(bedingungen(schema, ind, titel or "Objekt"))
    return out


def regeln(objekt):
    if objekt not in OBJEKTE:
        raise ValueError("unbekanntes Objekt: " + objekt)
    s = json.loads((SCHEMAS / f"{objekt}.schema.json").read_text(encoding="utf-8"))
    return [f"# Regeln {objekt} (aus {objekt}.schema.json)"] + objekt_text(s, "", objekt)


def main(argv):
    namen = argv or OBJEKTE
    for name in namen:
        print("\n".join(regeln(name)))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
