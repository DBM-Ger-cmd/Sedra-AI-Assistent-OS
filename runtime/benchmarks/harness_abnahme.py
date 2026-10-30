r"""Abnahme der Harness-Shell Stufe 1 mit echtem Modell (SPEC_HARNESS_SHELL_v1_G3_STUFE1, T8). Nur nach Ja des Captains.

Voraussetzung: das Cockpit läuft (START_SEDRA harness) und ein Modell ist geladen. Das Skript lädt kein Modell und startet keinen Server;
es spricht nur die Wege unter /api/harness/ des laufenden Servers an (URL mit #token, wie START_SEDRA sie ausgibt).

    python benchmarks/harness_abnahme.py --url "http://127.0.0.1:PORT/#TOKEN"                 # Teil 1: Werkzeugzeile, HS-52, Stopp
    python benchmarks/harness_abnahme.py --url "http://127.0.0.1:PORT/#TOKEN" --sitzung S-…   # Teil 2 nach Neustart des Servers
    python benchmarks/harness_abnahme.py --url "http://127.0.0.1:PORT/#TOKEN" --stufe3        # Teil 3: Stufe 3 (S3-A bis S3-D), siehe unten

Teil 1 prüft: (a) die erste Antwort hat eine Werkzeugzeile, (b) erstes Wort < 1 s nach dem ersten Token (HS-52): gemessen wird, wie viel
später das erste Textstück beim Leser ankommt als es auf dem Server entstand – die Zeiten `t` im Strom sind Sekunden seit Beginn der
Antwort, der Abstand zu `zug.start` beim Leser zieht den Versatz der Uhren ab; (c) Stopp mitten in einer langen Antwort endet mit
`abgebrochen`. Im scharfen Modus des Inhaltsschutzes (nichts bestätigt) kommt Text erst nach dem Urteil (D-E2); dann misst (b) die Zeit
bis zum geprüften Text und sagt das dazu. Teil 2 prüft nach dem Neustart, dass die Sitzung mit beiden Antworten noch da ist.

Teil 3 (Stufe 3, G3 Stufe 3 N12, Szenarien S3-A bis S3-D; S3-E läuft ohne Modell in test_harness_herkunft, S3-F ist der Pilot N8). Voraussetzungen, die der Captain
schafft: ein geladenes Modell (Qwen3.6-35B-A3B) und in `local_config/freigabe_katalog.yaml` die Regel
    - {id: abnahme-s3, werkzeug: [datei_schreiben, datei_aendern], muster: ['docs/abnahme_stufe3/**'], stufe: vorarbeiter, begruendung: Abnahme Stufe 3}
(fehlt sie, nennt das Skript sie und bricht ab). Das Skript **ernennt, legt Aufgaben an und beantwortet Karten als Captain**: Es muss vom Captain oder von Claude im
Terminal laufen, **nie als Lauf der Harness** (die Herkunftsprüfung S7 lehnt das ab). Es schreibt nur nach docs/abnahme_stufe3/ und startet nur den Lauf
run_tests (Gruppe harness, ohne Modell). Nur nach Ja des Captains (P-14).

Teil 4 (Stufe 4, G3 Stufe 4 N8, Szenarien S4-A bis S4-D) läuft **ohne Modell** und mit dem Browser (Playwright, Chromium):

    python benchmarks/harness_abnahme.py --stufe4 [--shots docs/shots/harness_stufe4]            # eigener Server auf einem Prüfprojekt
    python benchmarks/harness_abnahme.py --stufe4 --url "http://127.0.0.1:PORT/#TOKEN"           # gegen ein laufendes SEDRA (S4-D dann nur Beobachtung)

S4-A Vollständigkeit des Start-Menüs gegen /api/uix/modules · S4-B App öffnen, Nachweise, schließen, 8er-Grenze · S4-C Wechsel ins Cockpit und
zurück mit Übernahme der Apps · S4-D Statusbereich mit drei Hardware-Fällen (LHM-Sensor, nur nvidia-smi, keine GPU) – als Attrappe des
Hardware-Managers, nur mit eigenem Server; gegen ein laufendes SEDRA wird nur gezeigt, was die Leiste sagt. Der echte Lauf mit RTX und
LibreHardwareMonitor ist die Prüfung des Captains auf seinem PC (D-T3).

Teil 5 (Stufe 5, G3 Stufe 5 N8, Szenarien S5-A bis S5-D, `--stufe5`) steht in `harness_abnahme_stufe5.py`: Einstellungen erreichbar, Katalog-Editor
mit Antrag/Ablehnen/Freigeben, Schalter, Grenzen – ohne Modell, nur im temporären Prüfprojekt."""
import argparse
import http.client
import json
import sys
import threading
import time
from urllib.parse import urlsplit


def anfrage(url, method, path, body=None):
    parts = urlsplit(url)
    c = http.client.HTTPConnection(parts.hostname, parts.port, timeout=60)
    try:
        h = {'X-GUPPI-Token': parts.fragment}
        if body is not None: h['Content-Type'] = 'application/json'
        c.request(method, path, body=None if body is None else json.dumps(body), headers=h)
        r = c.getresponse()
        return r.status, json.loads(r.read().decode('utf-8') or 'null')
    finally:
        c.close()


def strom(url, aid, bei=None):
    """[(empfangen_s, event, data)] bis `ende`; `bei(event, data)` wird je Ereignis gerufen."""
    parts = urlsplit(url)
    c = http.client.HTTPConnection(parts.hostname, parts.port, timeout=600)
    c.request('GET', f'/api/harness/antworten/{aid}/strom', headers={'X-GUPPI-Token': parts.fragment})
    r = c.getresponse()
    if r.status != 200: raise RuntimeError(f'strom HTTP {r.status}')
    out, block, t0 = [], {}, time.monotonic()
    while True:
        line = r.fp.readline().decode('utf-8')
        if not line: break
        line = line.rstrip('\n')
        if not line:
            if 'event' in block:
                data = json.loads(block.get('data') or '{}')
                out.append((time.monotonic() - t0, block['event'], data))
                if bei: bei(block['event'], data)
                if block['event'] == 'ende': break
            block = {}
            continue
        if line.startswith(':'): continue
        k, _, v = line.partition(': ')
        block[k] = v
    c.close()
    return out


def teil1(url):
    ergebnis = {}
    code, projekte = anfrage(url, 'GET', '/api/harness/projekte')
    pid = projekte['projekte'][0]['id']
    code, kopf = anfrage(url, 'POST', '/api/harness/sitzungen', {'projekt': pid, 'titel': 'Abnahme Stufe 1'})
    sid = kopf['id']
    print('Sitzung', sid)
    code, out = anfrage(url, 'POST', f'/api/harness/sitzungen/{sid}/nachricht',
                        {'text': 'Welches Modell ist gerade geladen und mit welchem Kontext? Sieh mit einem Werkzeug nach und antworte in zwei Sätzen.'})
    if out.get('status') != 'laeuft':
        print('Nicht gestartet:', out); return 2
    print('Live-Text:', out.get('live'), '· Modell:', out.get('modell'))
    ev = strom(url, out['antwort_id'])
    namen = [e[1] for e in ev]
    ergebnis['werkzeugzeile'] = 'werkzeug.start' in namen and 'werkzeug.ende' in namen
    zug = next(e for e in ev if e[1] == 'zug.start')
    text = 'text.ungeprueft' if 'text.ungeprueft' in namen else 'text.geprueft'
    erstes = next((e for e in ev if e[1] == text), None)
    if erstes:
        verzug = (erstes[0] - zug[0]) - (erstes[2]['t'] - zug[2]['t'])         # beim Leser später als auf dem Server
        ergebnis['erstes_wort_verzug_s'] = round(verzug, 3)
        ergebnis['erstes_wort_ok'] = verzug < 1.0
        ergebnis['erstes_wort_art'] = text
    ende = ev[-1][2]
    ergebnis['ende_1'] = ende.get('ende')
    print('Antwort 1:', ende, '· Ereignisse', len(ev))
    # Stopp mitten in einer langen Antwort
    code, out = anfrage(url, 'POST', f'/api/harness/sitzungen/{sid}/nachricht',
                        {'text': 'Erkläre ausführlich in mindestens 600 Wörtern, wie ein Sprachmodell Text erzeugt. Kein Werkzeug nötig.'})
    # Stopp 4 s nach dem Start – im scharfen Modus gibt es vorher kein Teilstück, deshalb nach Zeit, nicht nach dem ersten Wort
    threading.Timer(4.0, lambda: anfrage(url, 'POST', f"/api/harness/antworten/{out['antwort_id']}/stopp", {})).start()
    ev2 = strom(url, out['antwort_id'])
    ergebnis['ende_2'] = ev2[-1][2].get('ende')
    ergebnis['stopp_ok'] = ergebnis['ende_2'] == 'abgebrochen'
    ergebnis['sitzung'] = sid
    print(json.dumps(ergebnis, ensure_ascii=False, indent=1))
    print('Jetzt den Cockpit-Server neu starten und Teil 2 mit --sitzung', sid, 'laufen lassen.')
    return 0 if ergebnis['werkzeugzeile'] and ergebnis.get('erstes_wort_ok') and ergebnis['stopp_ok'] else 1


def teil2(url, sid):
    code, s = anfrage(url, 'GET', f'/api/harness/sitzungen/{sid}')
    if code != 200:
        print('Sitzung fehlt nach Neustart:', code, s); return 1
    typen = [e['typ'] for e in s['eintraege']]
    modell = [e for e in s['eintraege'] if e['typ'] == 'modell']
    ok = typen.count('captain') == 2 and len(modell) == 2 and 'werkzeug' in typen and modell[-1].get('ende') == 'abgebrochen'
    print(json.dumps({'sitzung': sid, 'titel': s['titel'], 'eintraege': typen, 'enden': [m.get('ende') for m in modell], 'kaputt': s['kaputt'], 'ok': ok},
                     ensure_ascii=False))
    return 0 if ok else 1


# ---------------------------------------------------------------- Teil 3: Stufe 3
REGEL = {'id': 'abnahme-s3', 'werkzeug': ['datei_schreiben', 'datei_aendern'], 'muster': ['docs/abnahme_stufe3/**'], 'stufe': 'vorarbeiter'}


def abwarten(url, sid, grenze_s=240):
    """Wartet, bis die Sitzung nicht mehr antwortet; gibt ihren Verlauf zurück."""
    ende = time.monotonic() + grenze_s
    while time.monotonic() < ende:
        code, s = anfrage(url, 'GET', f'/api/harness/sitzungen/{sid}')
        if code == 200 and not s.get('laeuft'): return s
        time.sleep(1)
    raise RuntimeError(f'Sitzung {sid} antwortet nach {grenze_s} s noch')


def sagen(url, sid, text):
    abwarten(url, sid)                       # nach dem Ablehnen einer Karte setzt die Sitzung ihre Antwort noch fort
    code, out = anfrage(url, 'POST', f'/api/harness/sitzungen/{sid}/nachricht', {'text': text})
    if code != 200 or out.get('status') == 'kein_modell': raise RuntimeError(f'Nachricht nicht angenommen: {code} {out}')
    strom(url, out['antwort_id'])
    return abwarten(url, sid)


def offene_karten(url, sid):
    """Die offenen Karten einer Sitzung (aus dem Posteingang, dann die Karte selbst)."""
    _c, d = anfrage(url, 'GET', '/api/decisions')
    karten = []
    for x in d.get('items', []):
        if str(x.get('id', '')).startswith('harness:') and f'Sitzung {sid}' in str(x.get('note', '')):
            karten.append(anfrage(url, 'GET', '/api/harness/karten/' + x['id'].removeprefix('harness:'))[1])
    return karten


def teil3(url, projekt):
    _c, kat = anfrage(url, 'GET', '/api/harness/katalog')
    if not any(r['id'] == 'abnahme-s3' and r['stufe'] == 'vorarbeiter' for r in kat.get('regeln', [])):
        print('Dem Katalog fehlt die Regel für die Abnahme (der Captain trägt sie in local_config/freigabe_katalog.yaml ein):')
        print(json.dumps(REGEL, ensure_ascii=False))
        return 2
    ergebnis, ok = {}, True

    def pruefe(name, bedingung, **belege):
        nonlocal ok
        ergebnis[name] = dict(ok=bool(bedingung), **belege)
        ok = ok and bool(bedingung)
        print(json.dumps({name: ergebnis[name]}, ensure_ascii=False))

    def neu(vorlage):
        code, kopf = anfrage(url, 'POST', '/api/harness/sitzungen', {'projekt': projekt, 'vorlage': vorlage})
        if code != 200: raise RuntimeError(f'Sitzung {vorlage}: {code} {kopf}')
        return kopf['id']

    def ablehnen(karten, notiz):
        for x in karten: anfrage(url, 'POST', '/api/harness/karten/' + x['karte_id'], {'weg': 'ablehnen', 'notiz': notiz})

    v, b = neu('vorarbeiter'), neu('bauagent')
    anfrage(url, 'DELETE', f'/api/harness/vorarbeiter?projekt={projekt}')
    code, out = anfrage(url, 'POST', '/api/harness/vorarbeiter', {'projekt': projekt, 'sitzung_id': v})
    pruefe('ernennung', code == 200, antwort='ok' if code == 200 else out)

    # S3-A: die Karte des Agenten (Stufe vorarbeiter) geht an den Vorarbeiter; er entscheidet mit Begründung
    sagen(url, b, 'Lege die Datei docs/abnahme_stufe3/notiz.md an mit genau einer Zeile: Abnahme A')
    k = offene_karten(url, b)
    pruefe('S3-A karte an vorarbeiter', len(k) == 1 and k[0].get('an') == 'vorarbeiter', karten=[(x['karte_id'], x.get('an')) for x in k])
    if k:
        sagen(url, v, 'Prüfe die offenen Freigaben mit freigaben_offen und entscheide sie nach den Regeln, mit einer Begründung.')
        karte = anfrage(url, 'GET', '/api/harness/karten/' + k[0]['karte_id'])[1]
        # Entschieden heißt: vom Vorarbeiter erlaubt oder abgelehnt, oder mit Begründung dem Captain vorgelegt (weg vorlegen: die Karte liegt dann beim Captain).
        entschieden = (karte.get('status') == 'beantwortet' and str(karte.get('von', '')).startswith('vorarbeiter:')) or karte.get('an') == 'captain'
        pruefe('S3-A vom Vorarbeiter entschieden', entschieden, status=karte.get('status'), an=karte.get('an'), entscheidung=karte.get('entscheidung'),
               von=karte.get('von'), begruendung=karte.get('notiz'))
        if karte.get('status') == 'offen': ablehnen(k, 'Abnahme: der Vorarbeiter hat nicht entschieden')

    # S3-B: eine Karte der Stufe captain (kein Katalog-Treffer) bleibt beim Captain – der Vorarbeiter kann sie nicht entscheiden.
    # (Seine eigene Karte kann er nicht entscheiden, weil seine Sitzung bis zur Antwort auf sie keine Nachricht annimmt; das prüfen die Tests: selbstfreigabe.)
    sagen(url, b, 'Lege die Datei docs/abnahme_stufe3_captain/eigen.md an mit genau einer Zeile: Abnahme B')
    fremd = offene_karten(url, b)
    pruefe('S3-B Karte der Stufe captain', len(fremd) == 1 and fremd[0].get('an') == 'captain', karten=[(x['karte_id'], x.get('an'), x.get('stufe')) for x in fremd])
    sagen(url, v, 'Entscheide alle offenen Freigaben, die du darfst, mit freigaben_offen und freigabe_entscheiden.')
    nach = offene_karten(url, b)
    pruefe('S3-B Karte bleibt offen', len(nach) == len(fremd) and all(x['status'] == 'offen' for x in nach), status=[x['status'] for x in nach])
    ablehnen(nach, 'Abnahme S3-B')

    # S3-C: Aufgabe ohne Karte, Rücknahme, wieder Karte
    code, auf = anfrage(url, 'POST', '/api/harness/aufgaben', {'titel': 'Abnahme S3-C', 'zweck': 'Abnahme: Schreiben ohne Karte, dann Rücknahme', 'projekt': projekt, 'sitzungen': [b], 'ende': {'max_aufrufe': 3},
                                                              'erlaubt': [{'werkzeug': 'datei_schreiben', 'muster': 'docs/abnahme_stufe3/**'}]})
    pruefe('S3-C Aufgabe angelegt', code == 200, antwort=auf.get('id') if code == 200 else auf)
    if code == 200:
        sagen(url, b, 'Lege die Datei docs/abnahme_stufe3/aufgabe.md an mit genau einer Zeile: Abnahme C')
        pruefe('S3-C ohne Karte', not offene_karten(url, b), aufrufe=anfrage(url, 'GET', '/api/harness/aufgaben/' + auf['id'])[1].get('aufrufe'))
        anfrage(url, 'POST', f"/api/harness/aufgaben/{auf['id']}/zuruecknehmen", {'grund': 'Abnahme'})
        sagen(url, b, 'Lege die Datei docs/abnahme_stufe3/danach.md an mit genau einer Zeile: Abnahme C2')
        danach = offene_karten(url, b)
        pruefe('S3-C nach Rücknahme wieder Karte', len(danach) == 1, karten=[x['karte_id'] for x in danach])
        ablehnen(danach, 'Abnahme S3-C')

    # S3-D: Lauf run_tests (Gruppe harness, ohne Modell) mit Fortschritt; die Karte beantwortet der Captain
    sagen(url, v, 'Starte den Lauf run_tests mit der Gruppe harness und nenne mir die Lauf-ID.')
    karten = [x for x in offene_karten(url, v) if x.get('werkzeug') == 'lauf_starten']
    pruefe('S3-D Karte für den Lauf', len(karten) == 1, karten=[x['karte_id'] for x in karten])
    if karten:
        anfrage(url, 'POST', '/api/harness/karten/' + karten[0]['karte_id'], {'weg': 'erlauben', 'notiz': 'Abnahme S3-D'})
        ende, lauf = time.monotonic() + 600, None
        while time.monotonic() < ende:
            d = anfrage(url, 'GET', '/api/harness/laeufe')[1]
            lauf = next((l for l in d.get('laeufe', []) if l.get('karte_id') == karten[0]['karte_id']), None)
            if lauf and lauf['status'] != 'laeuft': break
            time.sleep(2)
        pruefe('S3-D Lauf endet ok', bool(lauf) and lauf['status'] == 'ok', status=lauf and lauf['status'], fortschritt=lauf and lauf.get('fortschritt'))
        sagen(url, v, 'Lies mit lauf_status das Ergebnis des Laufs und fasse es in einem Satz zusammen.')
    print(json.dumps({'stufe3': 'ok' if ok else 'FEHLER', 'sitzungen': {'vorarbeiter': v, 'bauagent': b}}, ensure_ascii=False))
    return 0 if ok else 1


# ---- Teil 4: Stufe 4 ohne Modell (Start-Menü, Apps, Statusbereich)
def _probe(lhm=None, smi=None, vram=(3.2, 12.0), ram=(9.5, 31.0), thermal='NORMAL', lhm_fehlt=False):
    m = lambda v, u='°C': {'value': v, 'unit': u, 'source': 'attrappe', 'state': 'valid' if v is not None else 'unavailable'}
    sensors = [{'sensor_id': '/gpu/0/temperature/0', 'name': 'GPU Core', 'type': 'Temperature', 'reading': m(lhm)}] if lhm is not None else []
    gpus = [{'device_id': 'GPU-1', 'temperature_core': m(smi), 'vram_used': m(vram[0], 'GiB'), 'vram_total': m(vram[1], 'GiB')}] if vram else []
    return {'gpus': gpus, 'sensors': sensors, 'memory': {'total': m(ram[1] if ram else None, 'GiB'), 'available': m(ram[0] if ram else None, 'GiB')},
            'provider_status': {'gpu': None, 'sensors': 'LibreHardwareMonitor_WMI_not_running_or_not_available' if lhm_fehlt else None}, 'thermal_state': thermal}


class _Attrappe:
    """Nur die Probe ist Attrappe; alles andere (Inventar, Profil, Fähigkeiten) bleibt der echte Hardware-Manager des Prüfprojekts."""
    def __init__(self, probe, echt=None): self.probe = probe; self.aufrufe = 0; self._echt = echt
    def get_state(self, fresh=False): self.aufrufe += 1; return self.probe
    def __getattr__(self, name): return getattr(self._echt, name)


def teil4(url=None, shots=None):
    import os
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import uix_check
    from playwright.sync_api import sync_playwright
    eigener = url is None
    stop = lambda: None
    if eigener:
        url, stop = uix_check.start_server(lambda *a: None, shell='harness')
    hub = uix_check.LAST_HUB if eigener else None
    ergebnis, ok, fehler = {}, True, []
    def pruefe(name, bedingung, **belege):
        nonlocal ok
        ergebnis[name] = dict(ok=bool(bedingung), **belege); ok = ok and bool(bedingung)
        print(json.dumps({name: ergebnis[name]}, ensure_ascii=False))
    shots = Path(shots) if shots else None
    if shots: shots.mkdir(parents=True, exist_ok=True)
    foto = lambda page, name: page.screenshot(path=str(shots / (name + '.png'))) if shots else None
    S = "window.sedra.shells.get('harness')"
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            page = b.new_page(viewport={'width': 1400, 'height': 860})
            page.on('console', lambda m: fehler.append(m.text) if m.type == 'error' else None)
            page.on('pageerror', lambda e: fehler.append('pageerror: ' + str(e)))
            page.goto(url); uix_check.wait_until_started(page); page.wait_for_timeout(1500)
            # S4-A: jeder Ort mit Werkzeug im Menü, keiner ohne; talk/instrument nie; kein Chip, kein Hub
            page.click('.hs-start-knopf'); page.wait_for_timeout(500); foto(page, '01_start_menue')
            a = page.evaluate("""()=>{ const S = %s; const P = window.sedraPlaces.PLACES;
              const mit = P.filter(p=>p.object.type !== 'talk' && S.ctx.tools.forObject(p.object).some(m=>m.kind !== 'instrument')).map(p=>p.id);
              const im = [...document.querySelectorAll('.hs-start-app')].map(e=>e.dataset.app);
              return {fehlt: mit.filter(id=>im.indexOf(id) < 0), zuviel: im.filter(id=>!id.startsWith('werkzeug-') && id !== 'einstellungen' && mit.indexOf(id) < 0), apps: im.length, einstellungen: im.indexOf('einstellungen') >= 0,
                      chip: !!document.querySelector('.sx-chip'), hub: !!document.querySelector('.sx-hub'), gruppen: [...document.querySelectorAll('.hs-start-gruppe .hs-ueber')].map(e=>e.textContent),
                      shells: [...document.querySelectorAll('.hs-start-shell')].map(e=>e.dataset.shell)}; }""" % S)
            # Stufe 5: der feste Eintrag „Einstellungen“ (System) ist kein Ort und kein Werkzeug – er gehört ins Menü, zählt aber nicht als „zu viel“
            pruefe('S4-A vollständig', not a['fehlt'] and not a['zuviel'] and not a['chip'] and not a['hub'] and a['apps'] > 0 and 'cockpit' in a['shells'] and a['einstellungen'], **a)
            # S4-B: Suche → Enter öffnet App; Werkzeug eingehängt; Nachweise; schließen → unmount; 8er-Grenze
            page.fill('.hs-start-suche', 'wissen'); page.wait_for_timeout(200); page.keyboard.press('Enter'); page.wait_for_timeout(800)
            foto(page, '02_app_wissen')
            b1 = page.evaluate("""()=>{ const S = %s; const R = window.sedraHarness.reiter; return {aktiv: R.aktiv(S), tools: [...document.querySelectorAll('.hs-app-box [data-tool]')].map(e=>e.dataset.tool),
              menueZu: document.querySelector('.hs-start-menue').hidden, nachweis: !!document.querySelector('.hs-app-nachweis-knopf')}; }""" % S)
            if b1['nachweis']: page.click('.hs-app-nachweis-knopf'); page.wait_for_timeout(300); foto(page, '03_nachweise')
            auf = page.evaluate("()=>document.querySelector('.hs-app-box').classList.contains('nachweis-auf')") if b1['nachweis'] else None
            n9 = page.evaluate("""()=>{ const S = %s; const P = window.sedraPlaces.PLACES.filter(p=>p.object.type !== 'talk' && S.ctx.tools.forObject(p.object).length);
              P.slice(0, 10).forEach(p=>window.sedraHarness.app.oeffnen(S, p)); return {offen: window.sedraHarness.app.liste(S).length, hinweise: [...document.querySelectorAll('.hs-hinweis')].length}; }""" % S)
            page.wait_for_timeout(500)
            zu = page.evaluate("""()=>{ const S = %s; const id = window.sedraHarness.app.liste(S)[0]; const a = S.ansichten.get(id); const m = a ? a.mounts.length : -1;
              window.sedraHarness.reiter.schliessen(S, id); return {vorher: m, nachher: a ? a.mounts.length : -1, offen: window.sedraHarness.app.liste(S).length}; }""" % S)
            pruefe('S4-B App-Leben', str(b1['aktiv']).startswith('app:wissen') and b1['tools'] and b1['menueZu'] and (auf is None or auf) and n9['offen'] == 8 and n9['hinweise'] >= 1 and zu['vorher'] >= 0 and zu['nachher'] == 0 and zu['offen'] == 7,
                   reiter=b1, nachweis_auf=auf, nach_zehn=n9, geschlossen=zu)
            # Alt+S und Esc
            page.keyboard.press('Alt+s'); page.wait_for_timeout(300)
            alt = page.evaluate("()=>!document.querySelector('.hs-start-menue').hidden")
            page.keyboard.press('Escape'); page.wait_for_timeout(200)
            esc = page.evaluate("()=>document.querySelector('.hs-start-menue').hidden")
            pruefe('S4-B Alt+S/Esc', alt and esc, alt_s_oeffnet=alt, esc_schliesst=esc)
            # S4-C: Wechsel ins Cockpit und zurück – die Apps kommen mit
            vorher = page.evaluate("()=>window.sedraHarness.app.liste(%s)" % S)
            page.wait_for_timeout(700)
            page.click('.hs-start-knopf'); page.wait_for_timeout(300); page.click('.hs-start-shell[data-shell="cockpit"]')
            page.wait_for_timeout(2500); uix_check.wait_until_started(page); page.wait_for_timeout(1500); foto(page, '04_cockpit')
            im_cockpit = page.evaluate("()=>({shell: window.sedraBoot.ctx.manifest.shell.id, offen: [...document.querySelectorAll('[data-tool]')].map(e=>e.dataset.tool).filter(t=>!t.startsWith('gauge-'))})")
            page.evaluate("()=>window.sedraWechsel.wechseln({shell: 'harness'})"); page.wait_for_timeout(2500); uix_check.wait_until_started(page); page.wait_for_timeout(2000)
            foto(page, '05_harness_zurueck')
            nachher = page.evaluate("()=>({shell: window.sedraBoot.ctx.manifest.shell.id, apps: window.sedraHarness.app.liste(%s)})" % S)
            pruefe('S4-C Wechsel', im_cockpit['shell'] == 'cockpit' and nachher['shell'] == 'harness' and len(nachher['apps']) == len(vorher) and set(nachher['apps']) == set(vorher),
                   vorher=vorher, cockpit=im_cockpit, zurueck=nachher)
            # S4-D: Statusbereich
            zellen = lambda: page.evaluate("()=>Object.fromEntries([...document.querySelectorAll('.hs-zelle')].map(e=>[e.dataset.zelle || 'fehler', {wert: (e.querySelector('b') || e).textContent, ton: e.className.replace('hs-zelle','').trim(), hinweis: e.title}]))")
            status = lambda: page.evaluate("()=>{ const S = %s; S._leiste.zuletzt = 0; window.sedraHarness.taskleiste.status(S); }" % S)
            if hub is not None:
                faelle = {}; echt = hub.runtime.hardware_manager
                for name, probe in (('lhm', _probe(lhm=58.0, smi=61.0)), ('nvidia-smi', _probe(smi=61.0, lhm_fehlt=True)), ('keine-gpu', _probe(smi=None, vram=None, ram=None, lhm_fehlt=True))):
                    att = _Attrappe(probe, echt); hub.runtime.hardware_manager = att; hub._hw_probe = None
                    status(); page.wait_for_timeout(600); faelle[name] = zellen(); faelle[name]['_aufrufe'] = att.aufrufe
                    foto(page, '06_status_' + name)
                g1, g2, g3 = faelle['lhm'].get('gpu', {}), faelle['nvidia-smi'].get('gpu', {}), faelle['keine-gpu']
                hub.runtime.hardware_manager = echt; hub._hw_probe = None
                pruefe('S4-D Statusbereich', '58' in g1.get('wert', '') and 'LHM' in g1.get('hinweis', '') and '61' in g2.get('wert', '') and 'nvidia-smi' in g2.get('hinweis', '')
                       and 'LibreHardwareMonitor nicht gestartet' in g2.get('hinweis', '') and 'ram' not in g3 and ('gpu' not in g3 or '°C' not in g3['gpu']['wert'])
                       and all(f['_aufrufe'] <= 2 for f in faelle.values()), **faelle)
            else:
                status(); page.wait_for_timeout(600); z = zellen(); foto(page, '06_status_live')
                pruefe('S4-D Statusbereich (Beobachtung, laufendes SEDRA)', True, zellen=z)
            pruefe('Konsole ohne Fehler', not fehler, fehler=fehler[:10])
            b.close()
    finally:
        stop()
    print(json.dumps({'stufe4': 'ok' if ok else 'nicht bestanden', 'szenarien': {k: v['ok'] for k, v in ergebnis.items()}}, ensure_ascii=False))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--url', help='die URL des laufenden Cockpits mit #token (Teil 1 bis 3: Pflicht; Teil 4: sonst eigener Server)')
    ap.add_argument('--sitzung', help='Teil 2: diese Sitzung nach dem Neustart prüfen')
    ap.add_argument('--stufe3', action='store_true', help='Teil 3: Szenarien S3-A bis S3-D der Stufe 3 (mit Modell, nur nach Ja)')
    ap.add_argument('--projekt', default='sedra-entwicklung', help='Harness-Projekt für Teil 3')
    ap.add_argument('--stufe4', action='store_true', help='Teil 4: Szenarien S4-A bis S4-D der Stufe 4 (ohne Modell, Browser)')
    ap.add_argument('--stufe5', action='store_true', help='Teil 5: Szenarien S5-A bis S5-D der Stufe 5 (ohne Modell, Browser; harness_abnahme_stufe5.py)')
    ap.add_argument('--shots', help='Teil 4/5: Ordner für Bildschirmfotos')
    a = ap.parse_args(argv)
    if a.stufe5:
        sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
        return __import__('harness_abnahme_stufe5').teil5(a.shots)
    if a.stufe4: return teil4(a.url, a.shots)
    if not a.url: ap.error('--url fehlt')
    if a.stufe3: return teil3(a.url, a.projekt)
    return teil2(a.url, a.sitzung) if a.sitzung else teil1(a.url)


if __name__ == '__main__':
    sys.exit(main())
