r"""Abnahme der Harness-Shell Stufe 5 (SPEC_HARNESS_SHELL_v1_G2_STUFE5 §7, G3 N8) – ohne Modell, mit dem Browser (Playwright, Chromium).

    python benchmarks/harness_abnahme.py --stufe5 [--shots docs/shots/harness_stufe5]      # eigener Server auf einem Prüfprojekt (temporär)

S5-A jede Seite erreichbar (Seitenleiste, Start-Menü, /einstellungen, Zelle Zustand) · S5-B Katalog: Regel ändern → Antrag im Posteingang → Ablehnen:
Datei unverändert; Freigeben: Datei geschrieben, Sicherung da, Audit · S5-C Schalter `entwicklung` → Antrag → Freigeben → Hinweis Neustart ·
S5-D Grenzen: `max_zuege` der Vorlage `bauagent` auf 12 → Kopie in `local_config/harness_vorlagen/`, `GET vorlagen` zeigt Quelle `local_config`.
Alles schreibt nur in das temporäre Prüfprojekt – nie in `local_config/` des Captains (P5-3). Entschieden wird über `hub.decide` (derselbe Weg
wie der Posteingang, `/api/decisions/answer`), nie direkt über den Applier."""
import json
import sys
from pathlib import Path


def teil5(shots=None):
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
    offen = lambda kind: [d for d in hub.decisions_view()['items'] if d['kind'] == 'request:' + kind]
    audit = lambda: [json.loads(l)['event_type'] for l in hub.runtime.audit.path.read_text(encoding='utf-8').splitlines() if l.strip()]
    datei = hub.project_root / 'local_config' / 'freigabe_katalog.yaml'
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            page = b.new_page(viewport={'width': 1400, 'height': 860})
            page.on('console', lambda m: fehler.append(m.text) if m.type == 'error' else None)
            page.on('pageerror', lambda e: fehler.append('pageerror: ' + str(e)))
            page.goto(url); uix_check.wait_until_started(page); page.wait_for_timeout(1500)
            # S5-A: vier Wege, jeder landet im Reiter einstellungen:
            wege = {}
            aktiv = lambda: page.evaluate("()=>window.sedraHarness.reiter.aktiv(%s)" % S)
            zu = lambda: page.evaluate("()=>window.sedraHarness.reiter.schliessen(%s, 'einstellungen:')" % S)
            page.click('[data-marke="hs-einstellungen"]'); page.wait_for_timeout(500); wege['seitenleiste'] = aktiv(); foto(page, '01_einstellungen'); zu()
            page.click('.hs-start-knopf'); page.wait_for_timeout(300); page.fill('.hs-start-suche', 'einstell'); page.wait_for_timeout(300); page.keyboard.press('Enter'); page.wait_for_timeout(500)
            wege['startmenue'] = aktiv(); zu()
            page.evaluate("()=>window.sedraHarness.reiter.neu(%s)" % S); page.wait_for_timeout(200)
            page.fill('.hs-feld', '/einstellungen system/schalter'); page.press('.hs-feld', 'Enter'); page.wait_for_timeout(500)
            wege['befehl'] = aktiv(); wege['befehl_punkt'] = page.evaluate("()=>(document.querySelector('.hs-einst-punkt.on') || {}).dataset.punkt"); zu()
            page.evaluate("()=>{ const S = %s; S._leiste.zuletzt = 0; window.sedraHarness.taskleiste.status(S); }" % S); page.wait_for_timeout(800)
            zelle = page.query_selector('.hs-zelle[data-zelle="state"]')
            if zelle: zelle.click(); page.wait_for_timeout(500); wege['zustand'] = aktiv(); zu()
            else: wege['zustand'] = 'keine Zelle Zustand (ausgeblendet)'
            seiten = page.evaluate("""async ()=>{ const S = %s; const E = window.sedraHarness.einstellungen; E.oeffnen(S); await new Promise(r=>setTimeout(r, 300));
              const a = S.ansichten.get('einstellungen:'); const leer = []; let n = 0;
              for(const g of E.GRUPPEN) for(const p of Object.keys(g.punkte)){ a.zeigen(g.id + '/' + p); n += 1; await new Promise(r=>setTimeout(r, 300)); if(document.querySelector('.hs-einst-flaeche').textContent.trim().length < 20) leer.push(g.id + '/' + p); }
              return {punkte: n, leer}; }""" % S)
            pruefe('S5-A Seiten erreichbar', all(str(v) == 'einstellungen:' for k, v in wege.items() if k in ('seitenleiste', 'startmenue', 'befehl')) and wege.get('befehl_punkt') == 'system/schalter'
                   and (wege['zustand'] == 'einstellungen:' or 'Zelle' in str(wege['zustand'])) and not seiten['leer'], wege=wege, **seiten)
            # S5-B: Katalog – Regel ändern → Antrag; Ablehnen: Datei unverändert; Freigeben: geschrieben, Sicherung, Audit
            page.evaluate("()=>window.sedraHarness.einstellungen.oeffnen(%s, 'agent/freigabe')" % S); page.wait_for_timeout(900); foto(page, '02_katalog')
            vorher = datei.exists()
            page.select_option('.hs-katalog-zeile[data-regel="schreiben-docs"] select', 'frei'); page.wait_for_timeout(300)
            rot = page.evaluate("()=>({rot: document.querySelectorAll('.hs-katalog-befund.rot').length, zeile: document.querySelector('.hs-katalog-zeile[data-regel=\"schreiben-docs\"]').classList.contains('rot'), knopf: !document.querySelector('.hs-katalog-antrag').disabled})")
            foto(page, '03_katalog_lockerung')
            page.click('.hs-katalog-antrag'); page.wait_for_timeout(900)
            a1 = offen('harness_katalog')
            pruefe('S5-B Antrag', rot['rot'] >= 1 and rot['zeile'] and rot['knopf'] and len(a1) == 1 and not datei.exists() and not vorher
                   and any('Lockerung' in r for r in a1[0]['risks']), befunde=rot, antrag=a1 and a1[0]['id'], risiken=a1 and a1[0]['risks'], hinweis=page.evaluate("()=>(document.querySelector('.hs-einst-antrag') || {}).textContent"))
            hub.decide({'id': a1[0]['id'], 'way': 'ablehnen'}); page.wait_for_timeout(600)
            abgelehnt = not datei.exists() and not offen('harness_katalog')
            page.select_option('.hs-katalog-zeile[data-regel="schreiben-docs"] select', 'frei'); page.wait_for_timeout(300); page.click('.hs-katalog-antrag'); page.wait_for_timeout(900)
            a2 = offen('harness_katalog')
            out = hub.decide({'id': a2[0]['id'], 'way': 'freigeben_und_anwenden'}) if a2 else None; page.wait_for_timeout(900)
            geschrieben = datei.exists() and 'schreiben-docs' in datei.read_text(encoding='utf-8')
            # zweite Änderung: jetzt gibt es eine Sicherung
            page.select_option('.hs-katalog-zeile[data-regel="schreiben-docs"] select', 'captain'); page.wait_for_timeout(300); page.click('.hs-katalog-antrag'); page.wait_for_timeout(900)
            a3 = offen('harness_katalog')
            if a3: hub.decide({'id': a3[0]['id'], 'way': 'freigeben_und_anwenden'}); page.wait_for_timeout(900)
            sicherung = sorted((hub.project_root / 'local_config').glob('freigabe_katalog.yaml.bak-*'))
            foto(page, '04_katalog_geschrieben')
            kopf = page.evaluate("()=>document.querySelector('.hs-katalog-kopf').textContent")
            pruefe('S5-B Ablehnen und Freigeben', abgelehnt and geschrieben and out and out['result']['status'] == 'applied' and len(sicherung) >= 1 and 'HARNESS_KATALOG_WRITTEN' in audit()
                   and 'Datei des Captains' in kopf, abgelehnt_unveraendert=abgelehnt, geschrieben=geschrieben, sicherung=[s.name for s in sicherung], kopf=kopf[:80])
            # S5-C: Schalter entwicklung → Antrag → Freigeben → Hinweis Neustart
            page.evaluate("()=>window.sedraHarness.einstellungen.oeffnen(%s, 'system/schalter')" % S); page.wait_for_timeout(900); foto(page, '05_schalter')
            page.click('.hs-einst-zeile[data-schalter="entwicklung.enabled"] button'); page.wait_for_timeout(900)
            s1 = offen('switch')
            if s1: hub.decide({'id': s1[0]['id'], 'way': 'freigeben_und_anwenden'})
            page.evaluate("()=>{ const S = %s; const a = S.ansichten.get('einstellungen:'); a.zeigen('system/schalter'); }" % S); page.wait_for_timeout(900)
            hinweis = page.evaluate("()=>[...document.querySelectorAll('[data-flaeche=\"schalter\"] .hs-app-satz')].map(e=>e.textContent).join(' | ')")
            foto(page, '06_schalter_neustart')
            pruefe('S5-C Schalter', len(s1) == 1 and 'Neustart' in hinweis and 'SWITCH' in ' '.join(audit()).upper(), antrag=s1 and s1[0]['id'], hinweis=hinweis[:120])
            # S5-D: Grenzen – bauagent auf 12 → Kopie in local_config/harness_vorlagen, GET vorlagen zeigt local_config
            page.evaluate("()=>window.sedraHarness.einstellungen.oeffnen(%s, 'agent/grenzen')" % S); page.wait_for_timeout(900); foto(page, '07_grenzen')
            page.fill('.hs-einst-zeile[data-vorlage="bauagent"] input', '12'); page.click('.hs-einst-zeile[data-vorlage="bauagent"] button'); page.wait_for_timeout(900)
            g1 = offen('harness_vorlage')
            kopie = hub.project_root / 'local_config' / 'harness_vorlagen' / 'bauagent.yaml'
            vor_freigabe = kopie.exists()
            if g1: hub.decide({'id': g1[0]['id'], 'way': 'freigeben_und_anwenden'})
            page.wait_for_timeout(600)
            v = next((x for x in hub.harness.handle('GET', '/api/harness/vorlagen')[1]['vorlagen'] if x['id'] == 'bauagent'), {})
            pruefe('S5-D Grenzen', len(g1) == 1 and not vor_freigabe and kopie.exists() and v.get('quelle') == 'local_config' and v.get('max_zuege') == 12
                   and 'HARNESS_VORLAGE_WRITTEN' in audit(), antrag=g1 and g1[0]['id'], kopie=str(kopie), vorlage={k: v.get(k) for k in ('quelle', 'max_zuege')})
            pruefe('Konsole ohne Fehler', not fehler, fehler=fehler[:10])
            b.close()
    finally:
        stop()
    print(json.dumps({'stufe5': 'ok' if ok else 'nicht bestanden', 'szenarien': {k: v['ok'] for k, v in ergebnis.items()}}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(teil5(sys.argv[1] if len(sys.argv) > 1 else None))
