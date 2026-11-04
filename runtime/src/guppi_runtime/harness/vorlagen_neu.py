"""Neue Vorlage anlegen (Wunsch des Captains 04.11.2026, wie „Neues Projekt“): Name, Beschreibung, Werkzeuge und Anweisung → Antrag im Posteingang;
die zwei Dateien (`<id>.yaml` und `<id>.md`) entstehen erst nach der Freigabe, in `local_config/harness_vorlagen/` (Vorrang vor dem Repo, nie darin).

Ein Formular darf nie mehr Rechte vergeben als ein Captain-Klick: eine neue Vorlage hat keine Rechte (`rechte: {}`) und keine Sitzungs-Erlaubnisse, und sie darf die
Werkzeuge des Vorarbeiters nicht nennen (die brauchen Rechte). Wer mehr will, schreibt die Datei selbst. Eine vorhandene id (Repo oder local_config) wird nie überschrieben.
Die Prüfung ist die der geladenen Vorlagen (`vorlagen.pruefen`), damit nichts angelegt wird, das sich später nicht laden lässt."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import yaml

from . import vorlagen as harness_vorlagen
from .vorlagen import VorlageFehler

NUR_VORARBEITER = ('freigaben_offen', 'freigabe_entscheiden', 'aufgabe_vorschlagen', 'aufgabe_beenden')
OFFEN_MAX = 5                       # offene Vorlagen-Anträge zugleich
UMLAUTE = {'ß': 'ss', 'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'Ä': 'ae', 'Ö': 'oe', 'Ü': 'ue'}


def id_aus_name(name):
    """„Mein Prüfer 2“ → mein-pruefer-2 (kleine Buchstaben, Ziffern, Bindestrich; höchstens 32 Zeichen)."""
    t = ''.join(UMLAUTE.get(c, c) for c in str(name or ''))
    t = unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', t).strip('-')[:32].strip('-')


def entwurf(projekt_root, payload, repo_dir=harness_vorlagen.VORLAGEN_DIR):
    """{vorlage: <geprüfte Vorlage>, yaml: Text, md: Text, basis} aus den Angaben des Formulars – oder VorlageFehler mit Satz.
    Angaben: name (Pflicht), id?, beschreibung?, basis? (id einer vorhandenen Vorlage: Werkzeuge, Modell, Grenzen, Anweisung als Vorgabe), werkzeuge?, system?, modell?, hinweis?."""
    p = payload if isinstance(payload, dict) else {}
    name = str(p.get('name') or '').strip()
    if not name:
        raise VorlageFehler('name_fehlt: ein Name für die Vorlage')
    vid = str(p.get('id') or '').strip() or id_aus_name(name)
    if not harness_vorlagen.ID.fullmatch(vid or '-'):
        raise VorlageFehler('id_ungueltig: kleine Buchstaben, Ziffern und Bindestrich (aus dem Namen wurde nichts Brauchbares)')
    ordner = harness_vorlagen._ordner(projekt_root, repo_dir)
    if any((o / (vid + '.yaml')).exists() for o in ordner):
        raise VorlageFehler(f'id_vergeben: es gibt schon eine Vorlage „{vid}“ – anderen Namen wählen')
    basis = None
    if p.get('basis'):
        basis = harness_vorlagen.laden(projekt_root, p['basis'], repo_dir)         # unbekannt/ungültig → VorlageFehler
    werkzeuge = p.get('werkzeuge') if p.get('werkzeuge') is not None else ([w for w in basis['werkzeuge'] if w not in NUR_VORARBEITER] if basis else None)       # aus der Basis fallen sie still weg
    if not isinstance(werkzeuge, list) or not werkzeuge:
        raise VorlageFehler('werkzeuge_fehlen: mindestens ein Werkzeug (oder eine Basis-Vorlage wählen)')
    vorarbeiter = [w for w in werkzeuge if w in NUR_VORARBEITER]
    if vorarbeiter:
        raise VorlageFehler('werkzeug_nur_vorarbeiter: ' + ', '.join(vorarbeiter) + ' – das braucht Rechte, die ein Formular nicht vergibt')
    system = p.get('system') if isinstance(p.get('system'), str) and p['system'].strip() else (basis['system'] if basis else '')
    if not system.strip():
        raise VorlageFehler('system_leer: die Anweisung für das Modell (oder eine Basis-Vorlage wählen)')
    modell = p.get('modell') if isinstance(p.get('modell'), str) and p['modell'].strip() else (basis['modell'] if basis else None)
    hinweis = p.get('hinweis') if isinstance(p.get('hinweis'), str) and p['hinweis'].strip() else (basis['hinweis'] if basis and basis['hinweis'] else None)
    daten = {'id': vid, 'name': name, 'beschreibung': str(p.get('beschreibung') or '').strip(), 'system': vid + '.md', 'werkzeuge': [str(w) for w in werkzeuge]}
    if modell:
        daten['modell'] = modell
    if hinweis:
        daten['hinweis'] = hinweis
    if basis:
        daten.update({k: basis[k] for k in ('max_zuege', 'frist_min', 'bremse_pro_stunde')})
    daten['rechte'] = {}
    doc = {'harness_vorlage': daten}
    geprueft = harness_vorlagen.pruefen(doc, system)
    kopf = (f'# Neue Vorlage „{name}“ – angelegt über die Harness-Shell (Neue Vorlage …) nach Freigabe im Posteingang.\n'
            '# Keine Rechte und keine Sitzungs-Erlaubnisse; Löschen dieser Datei und der .md daneben entfernt die Vorlage wieder.\n')
    return {'vorlage': geprueft, 'yaml': kopf + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120), 'md': system.strip() + '\n',
            'basis': basis['id'] if basis else None}


def schreiben(projekt_root, yaml_text, md_text, vid, repo_dir=harness_vorlagen.VORLAGEN_DIR):
    """Nur der Applier eines freigegebenen Antrags: legt die zwei Dateien an; vorhanden → VorlageFehler (nie überschreiben). Rückgabe {datei, md}."""
    from ..core.util import atomic_write_text
    if not harness_vorlagen.ID.fullmatch(str(vid)):
        raise VorlageFehler('id_ungueltig')
    ziel_dir = Path(projekt_root) / 'local_config' / 'harness_vorlagen'
    if any((o / (vid + '.yaml')).exists() for o in harness_vorlagen._ordner(projekt_root, repo_dir)):
        raise VorlageFehler(f'id_vergeben: {vid}')
    ziel_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(ziel_dir / (vid + '.md'), md_text)
    atomic_write_text(ziel_dir / (vid + '.yaml'), yaml_text)
    harness_vorlagen.laden(projekt_root, vid, repo_dir)                       # muss sich laden lassen – sonst wirft es hier
    return {'datei': str(ziel_dir / (vid + '.yaml')), 'md': str(ziel_dir / (vid + '.md'))}
