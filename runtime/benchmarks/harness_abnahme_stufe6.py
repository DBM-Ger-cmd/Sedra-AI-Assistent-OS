r"""Abnahme der Harness-Shell Stufe 6 (SPEC_HARNESS_SHELL_v1_STUFE6_G1/G2, G3 N8) – ohne Modell, mit dem Browser (Playwright, Chromium).

    python benchmarks/harness_abnahme.py --stufe6 [--shots docs/shots/harness_stufe6]      # eigener Server auf einem Prüfprojekt (temporär)

S6-A Aufgaben: Zweckfeld im Formular, Karte mit Zweck, „Darf: …“ und eingeklappten Mustern · S6-B Projekte: Erklärsatz, Hilfe mit „?“ und Esc · S6-C Vorschau: folgt der Datei,
Tauschen, Zuklappen, Festhalten, unter 1100 px eine Fläche, 1024×700 ohne waagerechtes Rollen · S6-D Modell: im Hinweis steht die Steuerung (Rezeptwahl, Laden), kein Verweis ·
S6-E Anhängen: „+“ öffnet die Auswahl, ein Klick fügt `@pfad` ein, „@“ schlägt Dateien vor.
Das Prüfprojekt zeigt auf den Ordner dieses Checkouts: **gelesen** wird nur aus ihm (README.md); geschrieben wird nur in das temporäre Prüfprojekt (Sitzungen, Aufgaben)."""
import json
import sys
from pathlib import Path


def teil6(shots=None):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import uix_check
    from playwright.sync_api import sync_playwright
    url, stop = uix_check.start_server(lambda *a: None, shell='harness')
    hub = uix_check.LAST_HUB
    ergebnis, ok, fehler = {}, True, []

    def pruefe(name, bedingung, **belege):
        nonlocal ok
        ergebnis[name] = dict(ok=bool(bedingung), **belege); ok = ok and bool(bedingung)
        print(json.dumps({name: ergebnis[name]}, ensure_ascii=False, default=str))
    shots = Path(shots) if shots else None
    if shots: shots.mkdir(parents=True, exist_ok=True)
    foto = lambda page, name: page.screenshot(path=str(shots / (name + '.png'))) if shots else None
    S = "window.sedra.shells.get('harness')"
    H = "window.sedraHarness"
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            page = b.new_page(viewport={'width': 1400, 'height': 860})
            erwartet = []                           # die eine Anfrage, die dieser Lauf absichtlich ablehnen lässt (Aufgabe ohne Zweck): der Browser meldet sie als Konsolenfehler
            page.on('response', lambda r: erwartet.append(r.url) if r.status == 400 and r.url.endswith('/api/harness/aufgaben') and r.request.method == 'POST' else None)
            page.on('console', lambda m: fehler.append(m.text) if m.type == 'error' and not ('400' in m.text and erwartet) else None)
            page.on('pageerror', lambda e: fehler.append('pageerror: ' + str(e)))
            page.goto(url); uix_check.wait_until_started(page); page.wait_for_timeout(1500)
            api = lambda pfad, methode='GET', body=None: page.evaluate(
                "async ([p, m, b])=>{ const S = %s; return await S.api(p, m === 'GET' ? {} : {method: m, body: b}); }" % S, [pfad, methode, body])
            projekt = api('/api/harness/projekte')['projekte'][0]['id']
            sid = api('/api/harness/sitzungen', 'POST', {'projekt': projekt})['id']

            # S6-A: Aufgaben mit Zweck
            api('/api/harness/aufgaben', 'POST', {'titel': 'Abnahme S6', 'zweck': 'Testläufe der Gruppe harness starten und das Ergebnis lesen', 'projekt': projekt, 'sitzungen': [sid],
                                                  'erlaubt': [{'werkzeug': 'lauf_starten', 'muster': 'run_tests'}], 'ende': {'max_aufrufe': 5}})
            page.evaluate("()=>%s.reiter.oeffnen(%s, 'aufgaben:')" % (H, S)); page.wait_for_timeout(800)
            a = page.evaluate("""()=>({satz: (document.querySelector('.hs-aufgaben .hs-auf-satz')||{}).textContent, darf: (document.querySelector('.hs-aufgaben .hs-auf-darf')||{}).textContent,
              details: !!document.querySelector('.hs-aufgaben details.hs-auf-technik:not([open])'), feld: !!document.querySelector('.hs-auf-form input[aria-label="Zweck"]')})""")
            foto(page, '01_aufgaben')
            pruefe('S6-A Aufgaben mit Zweck', a['satz'] and a['satz'].startswith('Testläufe') and a['darf'] and a['darf'].startswith('Darf: Lauf') and a['details'] and a['feld'], **a)
            ohne = page.evaluate("""async ()=>{ const S = %s; try{ await S.api('/api/harness/aufgaben', {method: 'POST', body: {titel: 'x', projekt: %s, sitzungen: [%s], erlaubt: [{werkzeug: 'datei_lesen', muster: '**'}], ende: {max_aufrufe: 1}}}); return 'angelegt'; }catch(e){ return e.message; } }""" % (S, json.dumps(projekt), json.dumps(sid)))
            pruefe('S6-A ohne Zweck abgelehnt', 'zweck_fehlt' in str(ohne), antwort=str(ohne)[:120])
            page.evaluate("()=>%s.reiter.schliessen(%s, 'aufgaben:')" % (H, S))

            # S6-B: Projekte erklärt
            satz = page.evaluate("()=>(document.querySelector('.hs-projekte-satz')||{}).textContent")
            page.click('.hs-projekte-kopf .hs-sz-knopf'); page.wait_for_timeout(300)
            zeilen = page.evaluate("()=>document.querySelectorAll('.hs-projekte-hilfe .hs-hilfe-zeile').length")
            foto(page, '02_projekte_hilfe')
            page.keyboard.press('Escape'); page.wait_for_timeout(300)
            zu = page.evaluate("()=>!document.querySelector('.hs-projekte-hilfe')")
            tooltip = page.evaluate("()=>(document.querySelector('.hs-gruppe')||{}).title")
            pruefe('S6-B Projekte erklärt', satz and 'Arbeitsordner' in satz and zeilen == 4 and zu and 'Sitzungen' in str(tooltip), satz=satz, hilfe_zeilen=zeilen, tooltip=tooltip)

            # S6-D: Modell – Handlung statt Verweis
            page.evaluate("()=>%s.reiter.neu(%s)" % (H, S)); page.wait_for_timeout(500)
            m = page.evaluate("""()=>{ const k = document.querySelector('.hs-kein-modell'); return {sichtbar: !!k && !k.hidden, text: k ? k.textContent : '', wahl: !!(k && k.querySelector('select')),
              knopf: !!(k && [...k.querySelectorAll('button')].some(x=>x.textContent === 'Laden')), pfeil: !!(k && k.textContent.includes('→'))}; }""")
            foto(page, '03_modell')
            pruefe('S6-D Modell laden im Hinweis', m['sichtbar'] and m['wahl'] and m['knopf'] and not m['pfeil'], **m)
            satz = page.evaluate("""()=>({auswahl: %s.modell.auswahlText({lagen: 30, kontext: 32768, vram_gb: 9.8, ram_gb: 10.93, tokens_s: 43.35, quelle: 'gerechnet'}),
              ablehnung: %s.modell.fehlertext(new Error('recipe_not_usable:hardware_pressure:Es fehlen 0.60 GB VRAM und 0.00 GB RAM bei 40 Lagen im RAM und 8192 Kontext.'))})""" % (H, H))
            pruefe('S6-D Auswahl und Ablehnung mit Zahlen', 'mit 30 Lagen im RAM' in satz['auswahl'] and '9,8 GB VRAM' in satz['auswahl'] and satz['ablehnung'].startswith('Es fehlen 0.60 GB VRAM'), **satz)

            # S6-E: Dateien anhängen
            page.evaluate("()=>%s.anhang.oeffnen(%s)" % (H, S)); page.wait_for_timeout(800)
            e = page.evaluate("()=>({offen: !!document.querySelector('.hs-anhang'), zeilen: document.querySelectorAll('.hs-anhang-zeile').length})")
            page.fill('.hs-anhang input', 'README'); page.wait_for_timeout(900)
            treffer = page.evaluate("()=>[...document.querySelectorAll('.hs-anhang-zeile')].map(z=>z.title)")
            foto(page, '04_anhang')
            if treffer:
                page.click('.hs-anhang-zeile.datei'); page.wait_for_timeout(300)
            feld = page.evaluate("()=>document.querySelector('.hs-feld').value")
            page.keyboard.press('Escape'); page.wait_for_timeout(200)
            page.fill('.hs-feld', 'Lies @READ'); page.dispatch_event('.hs-feld', 'input'); page.wait_for_timeout(900)
            vorschlag = page.evaluate("()=>[...document.querySelectorAll('.hs-vorschlag-zeile')].map(z=>z.textContent)")
            pruefe('S6-E Dateien anhängen', e['offen'] and e['zeilen'] > 0 and any(t.lower().endswith('readme.md') for t in treffer) and '@README.md' in feld.upper().replace('README.MD', 'README.md')
                   and any('@README.md' in v or '@readme.md' in v.lower() for v in vorschlag), auswahl=e, treffer=treffer[:3], feld=feld, vorschlag=vorschlag[:3])
            page.fill('.hs-feld', '')

            # S6-C: Vorschau neben dem Gespräch (gelesen wird README.md des Prüfprojekts)
            hub.harness.sitzungen.anhaengen(sid, {'typ': 'captain', 'text': 'Lies README.md', 'zeit': '2026-10-30T12:00:00+01:00'})
            hub.harness.sitzungen.anhaengen(sid, {'typ': 'werkzeug', 'antwort_id': 'A-00000000', 'name': 'datei_lesen', 'args': {'pfad': 'README.md'}, 'stufe': 'frei', 'regel': 'lesen-alles',
                                                  'status': 'ok', 'dauer_s': 0.01, 'ergebnis': 'README.md · Zeilen 1–1', 'wirkung': False, 'zeit': '2026-10-30T12:00:01+01:00'})
            page.evaluate("()=>%s.sitzungenLaden()" % S); page.wait_for_timeout(500)
            page.evaluate("()=>%s.reiter.oeffnen(%s, %s)" % (H, S, json.dumps(sid))); page.wait_for_timeout(1500)
            v = page.evaluate("""()=>{ const t = document.querySelector('.hs-teilung'); return {da: !!t, offen: !!t && !t.classList.contains('hs-fl-ohne'), seite: t && t.dataset.seite,
              inhalt: (document.querySelector('.hs-fl-inhalt')||{}).textContent, titel: (document.querySelector('.hs-fl-titel')||{}).textContent}; }""")
            foto(page, '05_vorschau')
            page.click('.hs-fl-kopf button[title^="Seiten tauschen"]'); page.wait_for_timeout(200)
            getauscht = page.evaluate("()=>document.querySelector('.hs-teilung').dataset.seite")
            page.click('.hs-fl-kopf button[aria-label="Vorschau zuklappen"]'); page.wait_for_timeout(200)
            zugeklappt = page.evaluate("()=>document.querySelector('.hs-teilung').classList.contains('hs-fl-ohne')")
            auf = page.evaluate("()=>{ const b = document.querySelector('.hs-fl-auf'); return !!b && !b.hidden; }")
            page.click('.hs-fl-auf'); page.wait_for_timeout(200)
            page.click('.hs-fl-pin'); page.wait_for_timeout(200)
            fest = page.evaluate("()=>document.querySelector('.hs-fl-pin').classList.contains('on')")
            page.set_viewport_size({'width': 1024, 'height': 700}); page.wait_for_timeout(500)
            schmal = page.evaluate("()=>({klein: document.querySelector('.hs-teilung').classList.contains('hs-fl-klein'), ueberhang: document.documentElement.scrollWidth - window.innerWidth})")
            foto(page, '06_vorschau_schmal')
            page.set_viewport_size({'width': 1400, 'height': 860}); page.wait_for_timeout(300)
            pruefe('S6-C Vorschau im Reiter', v['offen'] and 'README.md' in str(v['titel']) and len(str(v['inhalt'])) > 10 and v['seite'] == 'links' and getauscht == 'rechts'
                   and zugeklappt and auf and fest and schmal['klein'] and schmal['ueberhang'] <= 0, **v, getauscht=getauscht, zugeklappt=zugeklappt, auf_knopf=auf, festgehalten=fest, **schmal)
            pruefe('Konsole ohne Fehler', not fehler, fehler=fehler[:5])
            b.close()
    finally:
        stop()
    print(json.dumps({'stufe6': 'ok' if ok else 'nicht bestanden', 'szenarien': {k: v['ok'] for k, v in ergebnis.items()}}, ensure_ascii=False))
    return 0 if ok else 1
