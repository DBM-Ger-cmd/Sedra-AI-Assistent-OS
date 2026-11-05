"""Klassen der Freigaben und die Einordnung jedes Weges, auf dem der Server etwas annimmt (SPEC_APPS_v1_O3PLUS_G9_G2 §3.3, G9-01, G11).

Rein: kein Netz, kein Zustand, keine Wirkung. Klasse **H** erteilt Rechte für später, führt Code oder Programme aus, ändert Regeln oder
Kern, bringt Code in den Betrieb oder gibt Daten nach außen. Klasse **N** ist eine einzelne Handlung im Projekt ohne diese Folgen
(AM0-E1 §5b.3). Ablehnen und Zurücknehmen sind immer N; was die Tabelle nicht kennt, ist H.

Stand G9 (03.11.2026): Die Tür steht in `uix_server.UIXHub.freigabe_tuer` und `harness/api.beantworten`. Diese Datei ist die Bestandsliste, gegen die
`tests/test_freigabe_vollstaendig.py` jede Stelle mit `approve`, jede Route und jede Entscheidungsart prüft. Eine neue Stelle, Route oder
Art ohne Eintrag hier lässt den Test fehlschlagen – so kann kein neuer Freigabe-Weg an der Klasse H vorbei entstehen.
Diese Datei ist Prüfstelle (O3-02): Änderungen nur durch Claude mit Freigabe des Captains."""
from __future__ import annotations

H, N = 'H', 'N'

IMMER_N = frozenset({'ablehnen', 'zuruecknehmen', 'zur_kenntnis'})          # verengen, lesen – erteilen nichts

# ---------------------------------------------------------------- Entscheidungsarten (desk/decisions.py, harness, künftig G2/G6)
# Wert: Klasse für jeden erteilenden Weg, oder ein Wörterbuch Weg → Klasse, oder SONDER (hängt an der Bindung, siehe klasse()).
SONDER = 'sonder'
ARTEN = {
    'gate': H,                                   # Missions-Gate allgemein: Wirkung unbekannt (E2a)
    # Anträge (request:<art>, desk/decisions.REQUEST_TITLE)
    'request:switch': H, 'request:routing': H, 'request:boundaries': H,                 # Regeln
    'request:harness_katalog': H, 'request:harness_vorlage': H,                          # Regeln der Harness
    'request:harness_code_stand': H,                                                     # Code gilt als gesehen: Läufe und Befehle ohne Karte (G4, 04.11.2026)
    'request:install': H, 'request:trust': H, 'request:update': H,                       # Code und Rechte in den Betrieb
    'request:model_add': H, 'request:skill': H,                                          # neues Modell; Skill = Text für das Modell
    'request:cloud_url': H,                                                              # Daten nach außen
    'request:gateway': SONDER,                                                           # H außer LOCAL_ONLY
    'request:orchestra': H, 'request:standing': H, 'request:harness_projekt': H,         # Rechte für später
    'request:wissen_quelle': H, 'request:wissen_vorschlag': H,                           # Text wird Wissen für Agenten (E2b)
    # weitere Arten
    'boundary': H,                               # Grenze überschreiten (`einmal`) oder ändern (`aendern`)
    'content': SONDER,                           # Inhaltsschutz: H, wenn der Aufruf in die Cloud geht
    'cloud_offload': H,                          # Daten nach außen
    'slot_server': N,                            # „Entsperren“ des Modellservers: keine neuen Rechte (E2c)
    'harness_freigabe': SONDER,                  # nach Werkzeug, Ziel und Weg
    'harness_aufgabe': H,                        # Vorschlag einer Aufgabe = Freigabe im Voraus
    'harness_oberflaeche': {'uebernehmen': H, 'zuruecksetzen': N},     # G2 (noch nicht gebaut)
    'startbericht': N,                           # G6 (noch nicht gebaut): nur zur Kenntnis
    # Harness-Wege, die ohne Karte erteilen (F4, F5, F11)
    'harness:aufgabe_anlegen': H, 'harness:vorarbeiter_ernennen': H, 'harness:sitzung_erlaubnisse': H,
    # Routen, die vor G9 ohne Gate etwas der Klasse H taten (Befund N6, E12)
    'route:cloud_save': H, 'route:cloud_key': H, 'route:cloud_module_model': H, 'route:candidate_test': H,
}

# Jeder Weg, den eine Entscheidung anbieten kann (desk/decisions.WAYS, Harness-Karte, G2/G6). Ein unbekannter Weg ist H.
WEGE = frozenset({'einmal', 'freigeben_und_anwenden', 'aendern', 'ablehnen', 'cloud_diesen_lauf', 'bestaetigen',
                  'erlauben', 'sitzung', 'uebernehmen', 'zuruecksetzen', 'zur_kenntnis', 'zuruecknehmen'})

HARNESS_AUSFUEHREN = frozenset({'befehl', 'lauf_starten'})
HARNESS_SCHREIBEN = frozenset({'datei_schreiben', 'datei_aendern'})
HARNESS_N = frozenset({'modell_laden', 'modell_entladen', 'sitzungen_aufraeumen', 'lauf_stoppen'})


def _harness(binding, weg):
    if weg == 'sitzung':                                  # Sitzungs-Erlaubnis: Rechte für später
        return H
    werkzeug = str(binding.get('werkzeug') or '')
    if werkzeug in HARNESS_AUSFUEHREN:
        return H
    if werkzeug in HARNESS_SCHREIBEN:
        from ..harness import vorbehalte                 # erst hier: desk bleibt ohne harness importierbar
        ziel = str(binding.get('ziel') or '')
        if vorbehalte.pruefen(werkzeug, ziel, {'inhalt': 'x'}, vorhanden=False):
            return H                                      # harter Vorbehalt: Kern, Regeln, Harness, Oberfläche (ab O3)
        weich = vorbehalte.pruefen_weich(werkzeug, ziel)
        if isinstance(weich, dict) and weich.get('oberflaeche'):
            return H                                      # weicher Vorbehalt der Oberfläche (O3-03, noch nicht gebaut)
        return N
    if werkzeug in HARNESS_N:
        return N
    return H


def klasse(art, weg, binding=None):
    """'H' oder 'N' für eine Antwort `weg` auf eine Entscheidung der Art `art` mit ihrer Bindung (G9-01)."""
    weg = str(weg or '')
    if weg in IMMER_N:
        return N
    if weg not in WEGE:
        return H
    b = binding if isinstance(binding, dict) else {}
    regel = ARTEN.get(str(art or ''))
    if regel is None:
        return H
    if isinstance(regel, dict):
        return regel.get(weg, H)
    if regel != SONDER:
        return regel
    if art == 'request:gateway':
        return N if b.get('weg') == 'LOCAL_ONLY' else H
    if art == 'content':
        return N if b.get('route') == 'local' else H          # die Bindung der Entscheidung trägt `route` erst mit G9; bis dahin H
    if art == 'harness_freigabe':
        return _harness(b, weg)
    return H


GRUND_H = ('erteilt Rechte für später, führt Programme aus, ändert Regeln oder Kern, bringt Code in den Betrieb oder gibt Daten '
           'nach außen')


def text(art, id, weg, titel='', beschreibung=''):
    """Der Text des Systemdialogs und der Konsole – nur aus dem Kern (Art, Kennung, Titel und Beschreibung der Entscheidung), G9-05."""
    zeilen = [str(titel or art)[:200]]
    if beschreibung:
        zeilen.append(str(beschreibung)[:400])
    zeilen += ['', f'Art: {art} · Weg: {weg} · Kennung: {str(id)[:80]}', f'Klasse H: {GRUND_H}.',
               'Nur bestätigen, wenn du diese Freigabe gerade selbst in SEDRA gegeben hast.']
    return '\n'.join(zeilen)


def nutzlast_hash(payload):
    import hashlib
    import json
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode('utf-8')).hexdigest()


# ---------------------------------------------------------------- Routen (G11-02)
# Art der Route:
#   liest       – nur lesen (oder fragt auf Klick etwas ab, ohne etwas zu ändern)
#   antrag      – legt eine Entscheidung an; erteilt nichts
#   freigabe    – beantwortet eine Entscheidung (Klasse je Entscheidung, siehe klasse())
#   anwenden    – setzt eine schon erteilte Freigabe um (Einmal-Token, Bindung); ohne sie geschieht nichts
#   zurueck     – lehnt ab, nimmt zurück, stellt Bestätigtes wieder her
#   handlung    – tut etwas ohne Gate; Klasse sagt, ob das Wirkungen der Klasse H hat (dann Befund, siehe BEFUNDE_OHNE_GATE)
# Wert: (art, klasse oder None, notiz)

ROUTEN_SERVER = {
    '/api/decisions/answer': ('freigabe', None, 'Posteingang: alle Arten aus ARTEN (F1)'),
    '/api/freigabe/offen': ('liest', None, 'G9: wartende Bestätigungen – nur der Konsolen-Token'),
    '/api/freigabe/bestaetigen': ('freigabe', None, 'G9: Ja/Nein außerhalb des Browsers – nur der Konsolen-Token (Kanal konsole)'),
    '/api/objects': ('liest', None, 'Objekte des Desk (§10.1)'),
    '/api/actions': ('antrag', None, 'Verben des Desk; Verben mit Gate legen einen Antrag an (F7, desk/gated.py)'),
    '/api/live': ('liest', None, ''),
    '/api/candidate/diff': ('liest', None, ''),
    '/api/candidate/report': ('liest', None, ''),
    '/api/cost': ('liest', None, ''),
    '/api/intent/create': ('handlung', N, 'Vorhaben anlegen; führt nichts aus'),
    '/api/boundaries': ('liest', None, ''),
    '/api/boundaries/request': ('antrag', None, 'request:boundaries'),
    '/api/boundaries/apply': ('anwenden', None, ''),
    '/api/uix/shell': ('handlung', N, 'Shell wechseln (F9, Form)'),
    '/api/uix/standard': ('handlung', N, 'Shell als Standard (F9, Form)'),
    '/api/uix/enabled': ('handlung', N, 'Werkzeug an/aus (F9, Form)'),
    '/api/uix/shelf': ('handlung', N, 'Ablage der Shell'),
    '/api/uix/scaffold': ('handlung', N, 'eigenes Modul aus der Vorlage anlegen (kein fremder Code)'),
    '/api/uix/vorgabe': ('liest', None, 'schlägt eine Vorgabe vor, legt nichts an'),
    '/api/guard/probe': ('liest', None, ''),
    '/api/gateway/vorgang': ('liest', None, ''),
    '/api/gateway/neu': ('handlung', N, 'Vorgang anlegen'),
    '/api/gateway/vorgaben': ('liest', None, ''),
    '/api/gateway/vorgabe/merken': ('handlung', N, ''),
    '/api/gateway/vorgabe/loeschen': ('handlung', N, ''),
    '/api/update/suche': ('liest', None, 'fragt GitHub auf Klick nach Tags'),
    '/api/update/vorschau': ('antrag', None, 'lädt in den Staging-Ordner, legt request:update an'),
    '/api/update/uebernehmen': ('anwenden', None, 'F8; braucht die erteilte Freigabe'),
    '/api/update/zurueck': ('zurueck', None, 'stellt die letzte Sicherung des Programms her (schon einmal bestätigter Stand)'),
    '/api/gateway/vorschau': ('handlung', N, 'lokal'),
    '/api/gateway/ausgabe': ('handlung', N, 'lokal, schreibt in den Ausgang'),
    '/api/gateway/arbeitskopie': ('handlung', N, 'lokal'),
    '/api/gateway/speichern-unter': ('handlung', N, 'lokal, schreibt in den Ausgang'),
    '/api/gateway/upload': ('handlung', N, 'Datei in den Eingang'),
    '/api/gateway/pruefen': ('handlung', N, 'Datenschutz prüfen, lokal'),
    '/api/gateway/freigabe': ('antrag', None, 'request:gateway'),
    '/api/gateway/apply': ('anwenden', None, ''),
    '/api/gateway/pruefung': ('handlung', N, 'Urteil geprüft/verworfen'),
    '/api/gateway/verwerfen': ('zurueck', None, ''),
    '/api/gateway/frage': ('liest', None, 'Wissensbasis ohne Modell'),
    '/api/gateway/wissen': ('handlung', N, 'eigener Eintrag, nur Audit'),
    '/api/uix/install': ('antrag', None, 'request:install'),
    '/api/uix/install/apply': ('anwenden', None, ''),
    '/api/uix/trust': ('antrag', None, 'request:trust'),
    '/api/uix/trust/apply': ('anwenden', None, ''),
    '/api/uix/remove': ('zurueck', None, 'Modul entfernen (§6: was weg ist, kann nichts mehr tun)'),
    '/api/project/create': ('handlung', N, ''),
    '/api/standard-test/start': ('handlung', N, 'Modelltest'),
    '/api/mission/details': ('liest', None, ''),
    '/api/candidate': ('handlung', H, 'test/test-verify führen Tests eines Kandidaten aus (wo genau: in G9 prüfen); accept/rollback nur mit Gate'),
    '/api/code/generate': ('handlung', N, 'Modell erzeugt einen Kandidaten'),
    '/api/route': ('liest', None, 'Route für ein Vorhaben berechnen'),
    '/api/chat': ('handlung', N, 'Gesprächs-Mission anlegen'),
    '/api/project/files': ('liest', None, ''),
    '/api/project/file': ('liest', None, ''),
    '/api/chat/reply': ('handlung', N, 'Antwort des Modells'),
    '/api/chat/verlauf/leeren': ('handlung', N, ''),
    '/api/arbeitsstand': ('handlung', N, ''),
    '/api/arbeitsstand/leeren': ('handlung', N, ''),
    '/api/ablage/lesen': ('liest', None, ''),
    '/api/ablage/schreiben': ('handlung', N, 'eigene Ablage des Werkzeugs'),
    '/api/planung/reply': ('handlung', N, 'Antwort des Modells'),
    '/api/fisch/uebersetzen': ('handlung', N, 'lokales Modell (fisch/hub.py)'),
    '/api/fisch/profil/speichern': ('handlung', N, ''),
    '/api/fisch/brief': ('handlung', N, 'lokales Modell'),
    '/api/fisch/transkript': ('handlung', N, ''),
    '/api/fisch/transkript/import': ('handlung', N, ''),
    '/api/fisch/transkript/suche': ('liest', None, ''),
    '/api/fisch/transkript/pseudonymisieren': ('handlung', N, ''),
    '/api/fisch/transkript/status': ('liest', None, ''),
    '/api/fisch/transkript/export': ('handlung', N, ''),
    '/api/fisch/transkript/erkenntnisse': ('handlung', N, 'lokales Modell'),
    '/api/sprache/aufnahme': ('liest', None, ''),
    '/api/sprache/kern/start': ('handlung', N, ''),
    '/api/sprache/kern/pause': ('handlung', N, ''),
    '/api/sprache/kern/weiter': ('handlung', N, ''),
    '/api/sprache/kern/stopp': ('handlung', N, ''),
    '/api/sprache/kern/verwerfen': ('handlung', N, ''),
    '/api/sprache/aufnahme/beginnen': ('handlung', N, ''),
    '/api/sprache/aufnahme/stueck': ('handlung', N, ''),
    '/api/sprache/aufnahme/beenden': ('handlung', N, ''),
    '/api/sprache/aufnahme/loeschen': ('handlung', N, ''),
    '/api/sprache/aufnahme/transkribieren': ('handlung', N, 'lokales Programm (sprache/stt.py)'),
    '/api/chat/attach': ('liest', None, ''),
    '/api/diagnose/explain': ('liest', None, ''),
    '/api/diagnose/command': ('handlung', N, 'liest; `/rebind ja` ändert die Hardware-Bindung'),
    '/api/mission/run': ('anwenden', None, 'führt eine Mission mit ihrem Freigabe-Token aus; ohne Token entstehen Gates'),
    '/api/mission/approve': ('freigabe', None, 'ein Missions-Gate (F2) – Art `gate`'),
    '/api/mission/reject': ('zurueck', None, ''),
    '/api/switch/request': ('antrag', None, 'request:switch'),
    '/api/switch/apply': ('anwenden', None, ''),
    '/api/cloud/save': ('handlung', H, 'schreibt Cloud-Einstellungen (an/aus, Anbieter, Modelle) ohne Gate; nur `base_url` als Antrag (E2)'),
    '/api/cloud/base-url/apply': ('anwenden', None, ''),
    '/api/cloud/models': ('liest', None, 'fragt den Anbieter auf Klick nach seiner Modellliste'),
    '/api/labor/connection': ('handlung', N, 'Testnachricht an den Anbieter (keine Nutzdaten)'),
    '/api/labor/models-test': ('handlung', N, 'Testnachricht an jedes Modell (keine Nutzdaten, kostet Tokens)'),
    '/api/vorarbeiter/aktion': ('handlung', N, 'feste Aktionen des Entwurfsfensters'),
    '/api/entwurf/save': ('handlung', N, 'nur im Entwurfsordner'),
    '/api/entwurf/read': ('liest', None, ''),
    '/api/entwurf/list': ('liest', None, ''),
    '/api/chat/kombi': ('handlung', N, 'an den vom Captain eingerichteten Anbieter; der Inhaltsschutz prüft'),
    '/api/chat/cloud': ('handlung', N, 'an den vom Captain eingerichteten Anbieter; der Inhaltsschutz prüft'),
    '/api/cloud/key': ('handlung', H, 'setzt den API-Schlüssel ohne Gate; ein fremder Schlüssel = fremdes Konto beim Anbieter'),
    '/api/cloud/module-model': ('handlung', H, 'stellt ein Modul ohne Gate auf ein Cloud-Modell um (wirkt sofort)'),
    '/api/routing-config/request': ('antrag', None, 'request:routing'),
    '/api/routing-config/apply': ('anwenden', None, ''),
    '/api/model/pick': ('handlung', N, 'Dateidialog des Betriebssystems'),
    '/api/model/browse': ('liest', None, ''),
    '/api/model/inspect': ('liest', None, ''),
    '/api/model/add/request': ('antrag', None, 'request:model_add'),
    '/api/model/add/apply': ('anwenden', None, ''),
    '/api/model/test': ('handlung', N, ''),
    '/api/library/search': ('liest', None, ''),
    '/api/library/read': ('liest', None, ''),
    '/api/library/text': ('liest', None, ''),
    '/api/library/custom/request': ('antrag', None, 'request:skill'),
    '/api/library/custom/apply': ('anwenden', None, ''),
    '/api/model/load': ('handlung', N, ''),
    '/api/model/unload': ('handlung', N, ''),
    '/api/process/stop': ('handlung', N, 'nur Prozesse aus der eigenen Liste, mit confirm'),
    '/api/job/cancel': ('zurueck', None, ''),
    '/api/rework/hint': ('handlung', N, 'Hinweis des Captains an einen festgefahrenen Umbau'),
    '/api/routing-profile': ('handlung', N, 'wählt ein Profil aus local_config; die Regeln des Routers bleiben (routing_profiles.py:6–7)'),
}

# Harness (harness/api.py, WEG): Schlüssel 'METHODE weg[/unterweg]'
ROUTEN_HARNESS = {
    'POST karten': ('freigabe', None, 'Harness-Karte (F3): harness_freigabe / harness_aufgabe'),
    'POST karten/zuruecknehmen': ('zurueck', None, 'Entscheidung des Vorarbeiters zurücknehmen'),
    'POST katalog/antrag': ('antrag', None, 'request:harness_katalog (F6)'),
    'POST katalog/entfernen': ('antrag', None, 'request:harness_katalog'),
    'POST vorlagen/grenzen': ('antrag', None, 'request:harness_vorlage'),
    'POST vorlagen/neu': ('antrag', None, 'request:harness_vorlage'),
    'POST info/wissen': ('antrag', None, 'request:wissen_quelle (Betriebslog als Quelle der Wissensdatenbank)'),
    'POST code_stand/antrag': ('antrag', None, 'request:harness_code_stand'),
    'POST einstufen': ('liest', None, 'Vorschau der Einstufung'),
    'POST vorarbeiter': ('freigabe', H, 'Vorarbeiter ernennen (F5)'),
    'DELETE vorarbeiter': ('zurueck', None, 'Ernennung entziehen'),
    'POST vorgaben': ('handlung', N, 'Standard für Rezept und Projekt'),
    'POST aufraeumen': ('handlung', N, 'Sitzungen nach geloescht/ verschieben'),
    'POST gedaechtnis': ('handlung', N, 'Gedächtnis des Modells: dauerhafter Text, vergibt keine Rechte (offen: wie Skill und arbeitsplatz.yaml H?)'),
    'DELETE gedaechtnis': ('zurueck', None, ''),
    'POST verknuepfungen': ('handlung', N, ''),
    'DELETE verknuepfungen': ('zurueck', None, ''),
    'POST router': ('handlung', N, 'Sedra-Modell-Router starten/stoppen, Optionen'),
    'POST projekte': ('antrag', None, 'request:harness_projekt'),
    'POST sitzungen': ('freigabe', H, 'nur mit erlaubnisse_bestaetigt (F11, N1); sonst Handlung N'),
    'PATCH sitzungen': ('handlung', N, 'Titel, Modell; Sitzungs-Erlaubnis zurücknehmen'),
    'DELETE sitzungen': ('zurueck', None, 'nach geloescht/ verschieben'),
    'POST sitzungen/nachricht': ('handlung', N, 'Nachricht an das Modell'),
    'POST antworten/stopp': ('zurueck', None, ''),
    'POST aufgaben': ('freigabe', H, 'Aufgabe = Freigabe im Voraus (F4)'),
    'POST aufgaben/zuruecknehmen': ('zurueck', None, ''),
    'POST laeufe/stopp': ('zurueck', None, ''),
}
# Alle Wege und Unterwege aus harness/api.WEG. Der Test vergleicht sie mit dem Muster, damit ein neuer Weg auffällt; Wege, die schreiben,
# stehen zusätzlich oben in ROUTEN_HARNESS. Die übrigen lesen nur (GET).
HARNESS_WEGE = frozenset({'projekte', 'sitzungen', 'antworten', 'karten', 'katalog', 'einstufen', 'werkzeuge', 'vorlagen', 'vorarbeiter',
                          'vorschau', 'dateien', 'vorgaben', 'modelle', 'router', 'verknuepfungen', 'gedaechtnis', 'token', 'aufraeumen',
                          'code_stand', 'aufgaben', 'laeufe', 'hilfswerkzeuge', 'bausteine', 'info'})
HARNESS_UNTERWEGE = frozenset({'nachricht', 'export', 'strom', 'stopp', 'zuruecknehmen', 'antrag', 'entfernen', 'grenzen', 'neu', 'notizen', 'wissen'})
# In GESCHUETZT (S7), aber heute nur mit GET geroutet – keine schreibende Route (harness/api.py, Weg `token`)
HARNESS_GESCHUETZT_OHNE_SCHREIBEN = {'token': 'nur GET token_stand'}

# ---------------------------------------------------------------- Stellen, die `approve` rufen (G11-01)
# Schlüssel 'datei:funktion:aufruf' (Aufruf wie im Quelltext). tuer: ob die Stelle hinter der Tür aus G9 liegt (heute keine).
APPROVE_STELLEN = {
    'cli.py:main:rt.guard.approve': {'guard': True, 'kanal': 'konsole', 'tuer': False,
                                     'grund': '`guppi approve` – außerhalb des Browsers; braucht keine Tür'},
    'agent_manager/cli.py:approve:self.guard.approve': {'guard': True, 'kanal': 'konsole', 'tuer': False,
                                                        'grund': 'Konsole des Agent Manager – außerhalb des Browsers'},
    'agent_manager/cli.py:main:manager.approve': {'guard': False, 'kanal': 'konsole', 'tuer': False,
                                                  'grund': 'ruft die Stelle darüber'},
    'devenv/lesson_store.py:manage:cards.approve': {'guard': False, 'kanal': 'konsole', 'tuer': False,
                                                    'grund': 'Lernkarten des Coders, nur über `guppi lessons approve`'},
    'harness/freigabe.py:aufruf:self.guard.approve': {'guard': True, 'kanal': 'aufgabe|sitzung|katalog', 'tuer': False,
                                                      'grund': 'Ausführung unter einer schon erteilten Freigabe; die Erteilung selbst ist H (Aufgabe, Sitzungs-Erlaubnis)'},
    'harness/freigabe.py:beantworten:guard.approve': {'guard': True, 'kanal': 'seite|vorarbeiter', 'tuer': True,
                                                      'grund': 'hinter der Tür: harness/api.beantworten (Karte und Posteingang, F3)'},
    'uix_server.py:approve_gate:self.runtime.guard.approve': {'guard': True, 'kanal': 'seite', 'tuer': True,
                                                              'grund': 'hinter der Tür: /api/mission/approve über approve_gate_seite (F2), decide (F1)'},
    'desk/gated.py:decide:rt.guard.approve': {'guard': True, 'kanal': 'seite', 'tuer': True,
                                              'grund': 'hinter der Tür: Anträge des Desk über decide (F1, F7)'},
}

# Wege ohne guard.approve, die trotzdem erteilen (G11-04): nur aus decide erreichbar
ANTWORT_OHNE_GUARD = {'_answer_crossing': 'boundary', '_answer_scheduler': 'cloud_offload|slot_server', 'content_guard.answer': 'content'}

# Routen der Seite, die in G9 hinter die Tür kamen (E12, Befund N6): die Route ruft UIXHub.freigabe_tuer
HINTER_DER_TUER = {'/api/mission/approve': 'gate', '/api/cloud/save': 'route:cloud_save', '/api/cloud/key': 'route:cloud_key',
                   '/api/cloud/module-model': 'route:cloud_module_model', '/api/candidate': 'route:candidate_test'}
# Befund N6 (G11): Handlungen ohne Gate mit Wirkungen der Klasse H, die (noch) nicht hinter der Tür liegen. Nach G9 leer.
BEFUNDE_OHNE_GATE = tuple(sorted(r for r, (art, kl, _n) in ROUTEN_SERVER.items() if art == 'handlung' and kl == H and r not in HINTER_DER_TUER))
