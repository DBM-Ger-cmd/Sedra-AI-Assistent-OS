r"""Abnahme der Harness-Shell Stufe 1 mit echtem Modell (SPEC_HARNESS_SHELL_v1_G3_STUFE1, T8). Nur nach Ja des Captains.

Voraussetzung: das Cockpit läuft (START_SEDRA harness) und ein Modell ist geladen. Das Skript lädt kein Modell und startet keinen Server;
es spricht nur die Wege unter /api/harness/ des laufenden Servers an (URL mit #token, wie START_SEDRA sie ausgibt).

    python benchmarks/harness_abnahme.py --url "http://127.0.0.1:PORT/#TOKEN"                 # Teil 1: Werkzeugzeile, HS-52, Stopp
    python benchmarks/harness_abnahme.py --url "http://127.0.0.1:PORT/#TOKEN" --sitzung S-…   # Teil 2 nach Neustart des Servers

Teil 1 prüft: (a) die erste Antwort hat eine Werkzeugzeile, (b) erstes Wort < 1 s nach dem ersten Token (HS-52): gemessen wird, wie viel
später das erste Textstück beim Leser ankommt als es auf dem Server entstand – die Zeiten `t` im Strom sind Sekunden seit Beginn der
Antwort, der Abstand zu `zug.start` beim Leser zieht den Versatz der Uhren ab; (c) Stopp mitten in einer langen Antwort endet mit
`abgebrochen`. Im scharfen Modus des Inhaltsschutzes (nichts bestätigt) kommt Text erst nach dem Urteil (D-E2); dann misst (b) die Zeit
bis zum geprüften Text und sagt das dazu. Teil 2 prüft nach dem Neustart, dass die Sitzung mit beiden Antworten noch da ist."""
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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--url', required=True, help='die URL des laufenden Cockpits mit #token')
    ap.add_argument('--sitzung', help='Teil 2: diese Sitzung nach dem Neustart prüfen')
    a = ap.parse_args(argv)
    return teil2(a.url, a.sitzung) if a.sitzung else teil1(a.url)


if __name__ == '__main__':
    sys.exit(main())
