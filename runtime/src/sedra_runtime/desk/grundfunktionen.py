"""Die sieben Grundfunktionen (AM2-12 bis AM2-18, SPEC_APPS_v1_AM2_ORTE_UND_GRUNDFUNKTIONEN §2.3): feste Kernwege, die jede Shell erreichbar machen muss, und die Erklärung,
wie eine Shell das tut. Rein. Eine fehlende Erklärung ist im Vertrag 1.1 eine Warnung (AM2-15), kein Fehler."""
from __future__ import annotations

NAMEN = ('entscheidungen', 'gespraech', 'aufgaben', 'logbuch', 'modus_grenzen', 'module_berechtigungen', 'einstellungen_zustand')
WERKZEUG = {'entscheidungen': 'decisions', 'gespraech': 'talk', 'aufgaben': 'task', 'logbuch': 'logbook', 'modus_grenzen': 'boundaries',
            'module_berechtigungen': 'modules', 'einstellungen_zustand': 'system'}
ORT = {'entscheidungen': 'decisions', 'aufgaben': 'tasks', 'logbuch': 'logbook', 'modus_grenzen': 'boundary', 'module_berechtigungen': 'modules', 'einstellungen_zustand': 'machine'}
OBJEKTTYP = {'decisions': 'decision', 'task': 'task', 'logbook': 'logbook', 'boundaries': 'boundary', 'modules': 'module', 'system': 'machine'}      # was ein App-Ort nicht überdecken darf (AM2-18)
ARTEN = ('ort', 'eigen', 'verwaltung')
OEFFNER = ('dock', 'windows', 'flaeche', 'reiter', 'seite')          # Slots, mit denen eine Shell ein Objekt zeigt (ort setzt einen davon voraus)


def pruefe_tool_feld(wert, trust, origin) -> list:
    """AM2-13: `grundfunktion` im Manifest eines Werkzeugs – nur im Paket (CORE), nur ein bekannter Name."""
    if wert is None:
        return []
    if wert not in NAMEN:
        return ['grundfunktion_unbekannt']
    if origin != 'package' or trust != 'CORE':
        return ['grundfunktion_nur_im_paket']
    return []


def pruefe_erklaerung(feld, slots) -> list:
    """AM2-14: Fehler im Feld `grundfunktionen` einer Shell (Form, Namen, Arten). `slots` sind die Slots der Shell (für `slot:<name>`)."""
    if feld is None:
        return []
    if not isinstance(feld, dict):
        return ['grundfunktionen_ungueltig']
    fehler = []
    for name, art in feld.items():
        if name not in NAMEN:
            fehler.append('grundfunktion_unbekannt:' + str(name))
        elif not isinstance(art, str) or not (art in ARTEN or (art.startswith('slot:') and art[5:] in (slots or ()))):
            fehler.append('grundfunktion_art_ungueltig:' + str(name))
    return fehler


def erreichbar(art, slots) -> bool:
    """AM2-16 (statischer Teil): trägt die Shell, was sie erklärt? `ort` braucht einen Öffner, `slot:x` den Slot x; `eigen` und `verwaltung` prüft der Browser bzw. ab AM7."""
    if art == 'ort':
        return any(s in (slots or ()) for s in OEFFNER)
    if isinstance(art, str) and art.startswith('slot:'):
        return art[5:] in (slots or ())
    return art in ('eigen', 'verwaltung')


def warnungen(feld, slots, archiv=False, einstieg=False) -> list:
    """AM2-15/17: `grundfunktion_nicht_erklaert:<name>` je fehlender, `grundfunktion_nicht_erreichbar:<name>` je erklärter, aber nicht tragender Grundfunktion.
    Eine Archiv- oder Einstiegs-Shell muss nur `module_berechtigungen` erklären (AM2-17)."""
    feld = feld if isinstance(feld, dict) else {}
    pflicht = ('module_berechtigungen',) if (archiv or einstieg) else NAMEN
    erg = [f'grundfunktion_nicht_erklaert:{n}' for n in pflicht if n not in feld]
    erg += [f'grundfunktion_nicht_erreichbar:{n}' for n in NAMEN if n in feld and not erreichbar(feld[n], slots)]
    return erg


def aus_rahmen(slots) -> dict:
    """AM2-14: eine Shell aus Vorgabe bekommt die Erklärung vom Rahmen – aus dem, was er für die Shell anbietet: Gespräch im Slot `talk`, Entscheidungen als Karte (`inbox`),
    alles andere über die Suche (`palette`) als Ort."""
    slots = tuple(slots or ())
    erg = {}
    if 'talk' in slots:
        erg['gespraech'] = 'slot:talk'
    if 'inbox' in slots:
        erg['entscheidungen'] = 'slot:inbox'
    elif 'palette' in slots and 'dock' in slots:
        erg['entscheidungen'] = 'ort'
    if 'palette' in slots and 'dock' in slots:
        for n in ('aufgaben', 'logbuch', 'modus_grenzen', 'module_berechtigungen', 'einstellungen_zustand'):
            erg[n] = 'ort'
    return erg


def ueberdeckt(ort_objekt_typ) -> bool:
    """AM2-18: ein App-Ort mit dem Objekttyp einer Grundfunktion würde ihren Kernweg überdecken."""
    return ort_objekt_typ in OBJEKTTYP.values()
