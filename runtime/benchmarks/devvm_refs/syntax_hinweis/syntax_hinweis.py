import json

MAX_ZEICHEN = 2000000
ARTEN = {"py": "py", "json": "json", "js": "js"}
OK = "Syntax ok"


def _art(pfad):
    if not isinstance(pfad, str):
        return None
    name = pfad.replace("\\", "/").rsplit("/", 1)[-1]
    if "." not in name or name.startswith(".") and name.count(".") == 1:
        return None
    return ARTEN.get(name.rsplit(".", 1)[1].lower())


def _erg(art, ok, hinweis):
    return {"art": art, "ok": ok, "hinweis": hinweis}


def _py(text):
    try:
        compile(text, "<datei>", "exec")
    except SyntaxError as e:
        return _erg("py", False, "Zeile %d: %s" % (e.lineno or 1, e.msg))
    except ValueError:
        return _erg("py", False, "Zeile 1: nicht lesbar")
    return _erg("py", True, OK)


def _json(text):
    try:
        json.loads(text)
    except json.JSONDecodeError as e:
        return _erg("json", False, "Zeile %d: %s" % (e.lineno, e.msg))
    except (ValueError, RecursionError):
        return _erg("json", False, "Zeile 1: nicht lesbar")
    return _erg("json", True, OK)


def _js(text, pruefer):
    if pruefer is None:
        return _erg("js", None, "nicht geprueft: Node fehlt")
    try:
        ok, meldung = pruefer(text)
    except Exception:
        return _erg("js", None, "nicht geprueft: Pruefer abgestuerzt")
    if ok:
        return _erg("js", True, OK)
    zeilen = [z.strip() for z in str(meldung or "").splitlines() if z.strip()]
    return _erg("js", False, zeilen[0] if zeilen else "Syntaxfehler")


def syntax_hinweis(pfad, text, node_pruefer=None):
    art = _art(pfad)
    if art is None:
        return _erg(None, None, "")
    if not isinstance(text, str):
        return _erg(art, None, "nicht geprueft: kein Text")
    if len(text) > MAX_ZEICHEN:
        return _erg(art, None, "nicht geprueft: zu gross")
    if art == "py":
        return _py(text)
    if art == "json":
        return _json(text)
    return _js(text, node_pruefer)


def karten_zeile(erg):
    if not isinstance(erg, dict):
        return ""
    if erg.get("ok") is True:
        return "Syntax ok (%s)" % erg.get("art")
    if erg.get("ok") is False:
        return "Syntax-Hinweis: " + str(erg.get("hinweis") or "")
    return ""
