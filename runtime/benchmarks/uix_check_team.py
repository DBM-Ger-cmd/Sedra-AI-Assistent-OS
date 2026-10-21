"""Die Prüfzeilen von Shell D für das Agenten-Team (Spec 4, D4.4, G2-S4-17), aufgerufen von `uix_check.py --shell paperclip`.

  nav       jeder Eintrag der Navigation wird angeklickt: die Seite ist gefüllt, die Zeile leuchtet, kein Konsolenfehler, und jedes
            Werkzeug, das die Registrierung für das Objekt nennt, hängt dort (UIX-02). Fehlt das Werkzeug aus dem Design (D4.1),
            nennt der Bericht den Ersatz oder den Leerzustand – das ist kein Fehler, sondern der Zwischenstand.
  windows   zwei Agentenfenster öffnen, nach dem Neuladen sind beide wieder da; ein fünftes und sechstes Fenster verkleinern die
            ältesten zu Reitern (höchstens 4 offen). Zwei verschiedene Verläufe misst die Zeile erst, wenn ein Werkzeug `agent:*`
            zeichnet (UIX-04).
  idle      nach dem Öffnen jeder Seite des Teams 10 Sekunden Leerlauf: höchstens ein Aufruf je Pfad (UIX-05). Ausnahmen bis zu
            ihrer Spec: `workshop`, `rekorder`, `labor` (G2-S4-22)."""
from __future__ import annotations

# Was das Design je Eintrag vorsieht (D4.1); fehlt das Werkzeug, zeichnet der Ersatz, den die Registrierung nennt
DESIGN = {'Issues': 'board', 'Routinen': 'routines', 'Organigramm': 'org', 'Agenten': 'crew', 'Modelle und Slots': 'slots',
          'KI-Labor': 'labor', 'Posteingang': 'decisions', 'Ziele': 'intent', 'Kosten': 'meter'}
IDLE_PAGES = ('Issues', 'Routinen', 'Organigramm', 'Modelle und Slots')
IDLE_EXCEPT = ('workshop', 'rekorder', 'labor')
IDLE_SECONDS = 10
TEAM = [('A-UA', 'Unterarbeiter'), ('A-CO', 'Coder'), ('A-PL', 'Planer'), ('A-RE', 'Reviewer'), ('A-X1', 'Gast 1'), ('A-X2', 'Gast 2')]

NAV_MEASURE = """(i) => {
  const ctx = window.sedraBoot.ctx, N = window.sedraPcNav;
  const n = N.NAV.filter(x=>x.object)[i];
  const target = N.target(n, ctx.tools);
  const kind = window.sedraPcPages.pageFor(target).kind;
  const want = kind === 'dashboard' ? [] : ctx.tools.forObject(target).filter(m=>m.slot !== 'nachweis').map(m=>m.id);
  const have = [...document.querySelectorAll('.pc-page .pc-tool')].filter(s=>!s.closest('.pc-side')).map(s=>s.dataset.tool);
  const row = document.querySelectorAll('.pc-nav .pc-nav-row')[i];
  return {label: n.label, type: target.type + ':' + target.id, kind, want, have, lit: !!(row && row.classList.contains('on')),
          text: (document.querySelector('.pc-page') || {innerText: ''}).innerText.trim().length,
          empty: !!document.querySelector('.pc-page .s-empty')};
}"""

STACK = """() => {
  const shell = window.sedra.shells.get('paperclip');
  const wins = [...document.querySelectorAll('.pc-stack .pc-win')].filter(w=>!w.hidden);
  return {visible: !document.querySelector('.pc-stack').hidden, list: shell.windows.list(),
          open: wins.map(w=>({id: w.dataset.agent, text: (w.querySelector('.pc-win-body') || {innerText: ''}).innerText.trim()})),
          tabs: document.querySelectorAll('.pc-stack .pc-tab').length,
          ownTool: window.sedraBoot.ctx.tools.all().some(t=>(t.handles || []).indexOf('agent:*') >= 0)};
}"""

FILLED = "() => { const b = [...document.querySelectorAll('.pc-stack .pc-win:not([hidden]) .pc-win-body')]; return b.length > 0 && b.every(x=>x.innerText.trim()); }"
CLOSE_ALL ="() => { const w = window.sedra.shells.get('paperclip').windows; w.list().forEach(x=>w.close(x.id)); }"
OPEN = "(o) => window.sedraBoot.ctx.bus.emit('object.open', o)"


def check_nav(page, check, errors, console):
    """UIX-02: jeder Eintrag öffnet etwas, und es hängt das Werkzeug dort, das die Registrierung nennt."""
    labels = page.evaluate("()=>window.sedraPcNav.NAV.filter(x=>x.object).map(x=>x.label)")
    bad, notes = [], []
    for i, label in enumerate(labels):
        before = len(errors) + len(console)
        page.evaluate("(i)=>document.querySelectorAll('.pc-nav .pc-nav-row')[i].click()", i)
        page.wait_for_timeout(900)
        m = page.evaluate(NAV_MEASURE, i)
        missing = [t for t in m['want'] if t not in m['have']]
        if m['text'] < 10 or missing or not m['lit'] or len(errors) + len(console) > before:
            bad.append(f"{label} ({m['type']}): " + ', '.join(filter(None, [
                'Seite leer' if m['text'] < 10 else '', ('fehlt ' + '/'.join(missing)) if missing else '',
                'Zeile leuchtet nicht' if not m['lit'] else '', 'Konsolenfehler' if len(errors) + len(console) > before else ''])))
        soll = DESIGN.get(label)
        if soll and soll not in m['have']:
            notes.append(f"{label}: " + ('/'.join(m['have']) + f' statt {soll}' if m['have'] else f'Leerzustand, {soll} fehlt'))
    check('nav', not bad, '; '.join(bad) or f'{len(labels)} Einträge geöffnet' + (' · Zwischenstand: ' + '; '.join(notes) if notes else ''))


def check_windows(page, check, wait_until_started):
    """UIX-04 (Shell-Teil): zwei Fenster, nach dem Neuladen gleich; höchstens 4 offen, der Rest als Reiter."""
    page.evaluate(CLOSE_ALL)
    for aid, title in TEAM[:2]:
        page.evaluate(OPEN, {'type': 'agent', 'id': aid, 'title': title})
        page.wait_for_timeout(900)
    first = page.evaluate(STACK)
    page.reload(); wait_until_started(page); page.wait_for_timeout(1500)
    try:                                               # die Werkzeuge lesen nach dem Neuladen selbst nach – warten, nicht raten
        page.wait_for_function(FILLED, timeout=8000)
    except Exception:
        pass
    again = page.evaluate(STACK)
    problems = []
    if not first['visible'] or len(first['open']) != 2:
        problems.append(f"{len(first['open'])} Fenster offen statt 2")
    if sorted(w['id'] for w in again['open']) != sorted(w['id'] for w in first['open']):
        problems.append('nach dem Neuladen andere Fenster')
    empty = [w['id'] for w in again['open'] if not w['text']]
    if empty:
        problems.append('nach dem Neuladen leer: ' + ', '.join(empty))
    verlauf = 'Verlauf nicht geprüft – kein Werkzeug mit agent:* (S4.8)'
    if first['ownTool']:
        texts = [w['text'] for w in sorted(first['open'], key=lambda w: w['id'])]
        if len(set(texts)) < 2:
            problems.append('beide Fenster zeigen denselben Verlauf')
        if texts != [w['text'] for w in sorted(again['open'], key=lambda w: w['id'])]:
            problems.append('Verlauf nach dem Neuladen anders')
        verlauf = 'zwei Verläufe, nach dem Neuladen gleich'
    for aid, title in TEAM[2:]:
        page.evaluate(OPEN, {'type': 'agent', 'id': aid, 'title': title})
        page.wait_for_timeout(500)
    many = page.evaluate(STACK)
    if len(many['open']) != 4 or many['tabs'] != len(TEAM) - 4:
        problems.append(f"{len(many['open'])} offen, {many['tabs']} Reiter bei {len(TEAM)} Fenstern")
    page.evaluate(CLOSE_ALL); page.wait_for_timeout(300)
    gone = page.evaluate(STACK)
    if gone['visible'] or gone['open']:
        problems.append('Stapel bleibt nach dem Schließen sichtbar')
    check('windows', not problems, '; '.join(problems) or f"2 Fenster überstehen das Neuladen, {len(TEAM)} Fenster: 4 offen und "
          f"{len(TEAM) - 4} Reiter; {verlauf}")


def check_idle(page, check, calls):
    """UIX-05: im Leerlauf keine wiederholte Abfrage desselben Pfads – gemessen je Seite des Teams und an einem Agentenfenster."""
    labels = page.evaluate("()=>window.sedraPcNav.NAV.filter(x=>x.object).map(x=>x.label)")
    stops = [(lbl, "(i)=>document.querySelectorAll('.pc-nav .pc-nav-row')[i].click()", labels.index(lbl)) for lbl in IDLE_PAGES if lbl in labels]
    stops.append(('Agentenfenster', OPEN, {'type': 'agent', 'id': TEAM[0][0], 'title': TEAM[0][1]}))
    bad = []
    for name, script, arg in stops:
        page.evaluate(script, arg)
        page.wait_for_timeout(1500)                    # das erste Lesen gehört zum Öffnen, nicht zum Leerlauf
        start = len(calls)
        page.wait_for_timeout(IDLE_SECONDS * 1000)
        seen = {}
        for method, url, tool, _shell in calls[start:]:
            if '/api/events' in url or tool in IDLE_EXCEPT:
                continue
            path = method + ' ' + url.split('?')[0].split('/api/', 1)[-1]
            seen[path] = seen.get(path, 0) + 1
        repeated = [f'{p} ×{n}' for p, n in seen.items() if n > 1]
        if repeated:
            bad.append(f"{name}: " + ', '.join(repeated))
    page.evaluate(CLOSE_ALL)
    check('idle', not bad, '; '.join(bad) or f"{len(stops)} Seiten je {IDLE_SECONDS} s ohne wiederholte Abfrage (ausgenommen: {', '.join(IDLE_EXCEPT)})")


def run(page, check, errors, console, calls, wait_until_started):
    check_nav(page, check, errors, console)
    check_windows(page, check, wait_until_started)
    check_idle(page, check, calls)
