import re

PRAEFIX = "SEDRA Desktop (UIX): "
ADRESSE = re.compile(r"http://127\.0\.0\.1:([0-9]{1,5})/(#[A-Za-z0-9_-]{16,128})?", re.ASCII)
SHELL = re.compile(r"[a-z0-9-]{2,40}", re.ASCII)


def _wert(x):
    return isinstance(x, str) and bool(x) and "\x00" not in x and not x.startswith("-")


def vorschau_befehl(python, root, architecture, shell=None):
    if not isinstance(python, str) or not python or "\x00" in python:
        raise ValueError("python")
    if not _wert(root):
        raise ValueError("root")
    if not _wert(architecture):
        raise ValueError("architecture")
    if shell is not None and not (isinstance(shell, str) and SHELL.fullmatch(shell)):
        raise ValueError("shell")
    cmd = [python, "-m", "sedra_runtime.uix_server", "--root", root, "--architecture", architecture, "--port", "0"]
    if shell is not None:
        cmd += ["--shell", shell]
    return cmd


def adresse_gueltig(url):
    if not isinstance(url, str):
        return False
    m = ADRESSE.fullmatch(url)
    return bool(m) and 1 <= int(m.group(1)) <= 65535


def adresse_lesen(ausgabe):
    if isinstance(ausgabe, str):
        zeilen = ausgabe.splitlines()
    elif isinstance(ausgabe, list):
        zeilen = ausgabe
    else:
        return None
    for z in zeilen:
        if not isinstance(z, str):
            continue
        z = z.strip()
        if z.startswith(PRAEFIX):
            rest = z[len(PRAEFIX):].strip()
            if adresse_gueltig(rest):
                return rest
    return None


def adresse_fuer_log(url):
    if not adresse_gueltig(url):
        return ""
    return url.split("#", 1)[0]


def vorschau_ende(gestartet, jetzt, max_minuten=30, server_laeuft=True, sammelkarte_beantwortet=False):
    for x in (gestartet, jetzt):
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            raise ValueError("zeit")
    if jetzt < gestartet:
        raise ValueError("zeit")
    if not server_laeuft:
        return "server_ende"
    if sammelkarte_beantwortet:
        return "beantwortet"
    if jetzt - gestartet >= max_minuten * 60:
        return "zeit"
    return None
