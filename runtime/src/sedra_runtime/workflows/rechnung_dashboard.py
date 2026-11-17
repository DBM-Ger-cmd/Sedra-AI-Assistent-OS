"""Standalone invoice review report, populated only from actual workflow outputs."""
from datetime import datetime, timezone
from html import escape
import json
from math import isfinite
from pathlib import Path

REPORT = 'invoice-dashboard-v1'
FILENAME = 'rechnung-dashboard.html'


def output_path(folder, workflow):
    raw=(workflow.get('meta') or {}).get('sedra_report_dir') or ''
    if not isinstance(raw,str) or len(raw)>200:
        raise ValueError('dashboard_output_folder_invalid')
    parts=raw.replace('\\','/').split('/') if raw else []
    if any(p in ('','.','..') or any(c in p for c in ':<>"|?*') for p in parts):
        raise ValueError('dashboard_output_folder_invalid')
    root=Path(folder).resolve()
    candidate=root.joinpath(*parts,FILENAME)
    if not candidate.resolve().is_relative_to(root):
        raise ValueError('dashboard_output_outside_run')
    for part in [candidate,*candidate.parents]:
        if part==root:break
        if part.is_symlink():raise ValueError('dashboard_output_symlink_refused')
    return candidate


def collect(workflow, outputs, result):
    if (workflow.get('meta') or {}).get('sedra_report') != REPORT:
        return None
    records = [i.get('json', {}) for branches in outputs.values() for branch in branches for i in branch]
    records = [r for r in records if isinstance(r, dict)]
    extraction = next((r['output'] for r in records if isinstance(r.get('output'), dict)), {})
    records.append(extraction)
    comparison = next((r for r in records if isinstance(r.get('ergebnisse'), list)), {})
    parsed = next((r for r in records if isinstance(r.get('positionen'), list)), {})
    positions = {str(p.get('position')): p for p in parsed.get('positionen', []) if isinstance(p, dict)}
    rows = []
    for row in comparison.get('ergebnisse', []):
        if not isinstance(row, dict):
            continue
        original = positions.get(str(row.get('position')), {})
        rows.append({k: row.get(k, original.get(fallback)) for k, fallback in [
            ('position', 'position'), ('menge_rechnung', 'menge'), ('menge_auftrag', 'menge_auftrag'),
            ('einzelpreis_rechnung', 'einzelpreis'), ('einzelpreis_auftrag', 'einzelpreis_auftrag'),
            ('summe_rechnung', 'gesamtpreis'), ('summe_auftrag', 'summe_auftrag'), ('status', 'status')]})
    def field(*keys):
        for r in reversed(records):
            for key in keys:
                if isinstance(r.get(key), (str, int, float)):
                    return r[key]
        return None
    return {'schema': REPORT, 'workflow': workflow['name'], 'created_at': datetime.now(timezone.utc).isoformat(),
            'execution_status': result['status'], 'error': result.get('fehler_text') or result.get('error'),
            'invoice': field('rechnungsnummer', 'Rechnungsnummer'), 'order': field('auftragsnummer', 'Auftragsnummer'),
            'review_status': comparison.get('gesamtstatus'), 'rows': rows,
            'missing_positions': comparison.get('fehlende_auftragspositionen', []),
            'read_errors': parsed.get('lesefehler', []), 'notes': result.get('hinweise', []),
            'steps': [{k: n.get(k) for k in ('name', 'art', 'status')} for n in result.get('knoten', [])],
            'disconnected': result.get('uebersprungen', []), 'model_extraction': extraction,
            'model_selection': (workflow.get('meta') or {}).get('sedra_model'), 'test_mode':(workflow.get('meta') or {}).get('sedra_test_mode')}


def _number(value):
    if type(value) not in (int, float) or not isfinite(value):
        return None
    return value


def _fmt(value, money=False):
    value = _number(value)
    if value is None:
        return '–'
    s = f'{value:,.2f}' if money else f'{value:,.4f}'.rstrip('0').rstrip('.')
    return s.translate(str.maketrans({',': '.', '.': ','})) + (' €' if money else '')


def render(data):
    e = lambda v: escape(str(v if v is not None else 'Nicht übermittelt'), quote=True)
    rows = data.get('rows', [])
    deviations = sum(r.get('status') != 'OK' for r in rows)
    failed = data.get('execution_status') != 'completed'
    clear = not failed and bool(rows) and not deviations and not data.get('missing_positions') and not data.get('read_errors') and data.get('review_status') == 'ALLE POSITIONEN STIMMEN ÜBEREIN'
    headline = 'Technischer Lauf fehlgeschlagen' if failed else 'Prüfung ohne Positionsabweichung' if clear else 'Klärung erforderlich'
    tone = 'bad' if failed else 'ok' if clear else 'warn'
    tr = []
    for r in rows:
        a, b = _number(r.get('summe_rechnung')), _number(r.get('summe_auftrag'))
        difference = a - b if a is not None and b is not None else None
        vals = [r.get('position'), _fmt(r.get('menge_rechnung')), _fmt(r.get('menge_auftrag')),
                _fmt(r.get('einzelpreis_rechnung'), True), _fmt(r.get('einzelpreis_auftrag'), True),
                _fmt(a, True), _fmt(b, True), _fmt(difference, True), r.get('status') or 'UNGEPRÜFT']
        tr.append('<tr data-state="%s">%s</tr>' % ('ok' if r.get('status') == 'OK' else 'issue',
                  ''.join('<td>%s</td>' % e(v) for v in vals)))
    def total(key):
        values = [_number(r.get(key)) for r in rows]
        return sum(values) if values and all(v is not None for v in values) else None
    invoice_total, order_total = total('summe_rechnung'), total('summe_auftrag')
    difference = invoice_total - order_total if invoice_total is not None and order_total is not None else None
    warnings = []
    if data.get('error'):
        warnings.append('Lauffehler: ' + str(data['error']))
    if data.get('missing_positions'):
        warnings.append('Auftragspositionen fehlen in der Rechnung: ' + ', '.join(map(str, data['missing_positions'])))
    for item in data.get('read_errors', []):
        warnings.append('Lesefehler: ' + (str(item.get('position', '')) + ' · ' + str(item.get('grund', '')) if isinstance(item, dict) else str(item)))
    if not rows:
        warnings.append('Keine auswertbaren Positionsvergleiche übermittelt. Es wird kein Prüferfolg angenommen.')
    warnings.extend(map(str, data.get('notes', [])))
    flow = ''.join('<li><span class="step-index">%d</span><div><b>%s</b><small>%s · %s</small></div></li>' %
                   (i + 1, e(s.get('name')), e(s.get('art')), e({'ok': 'Durchlaufen', 'uebersprungen': 'Ohne Daten übersprungen'}.get(s.get('status'), s.get('status'))))
                   for i, s in enumerate(data.get('steps', [])))
    payload = json.dumps(data, ensure_ascii=False, allow_nan=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    values = {'TITLE': e(data.get('workflow')), 'INVOICE': e(data.get('invoice')), 'ORDER': e(data.get('order')),
              'DATE': e(data.get('created_at')), 'RUN': e(data.get('run_id')), 'REVISION': e(data.get('revision')),
              'HEADLINE': headline, 'TONE': tone, 'COUNT': str(len(rows)), 'ISSUES': str(deviations + len(data.get('missing_positions', []))),
              'INVOICE_TOTAL': _fmt(invoice_total, True), 'ORDER_TOTAL': _fmt(order_total, True), 'DIFFERENCE': _fmt(difference, True),
              'ROWS': ''.join(tr), 'WARNINGS': ''.join('<li>%s</li>' % e(w) for w in warnings) or '<li>Keine zusätzlichen Hinweise.</li>',
              'FLOW': flow or '<li>Für diesen Lauf liegen keine Schrittmeldungen vor.</li>',
              'DISCONNECTED': e(', '.join(map(str, data.get('disconnected', []))) or 'Keine'), 'DATA': payload,
              'TEST_NOTE':'<p class="status warn">'+e(data['test_mode'])+'</p>' if data.get('test_mode') else ''}
    html = TEMPLATE
    for key, value in values.items():
        html = html.replace('@@' + key + '@@', value)
    return html


TEMPLATE = '''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SEDRA · Rechnungsauswertung</title><style>
:root{color-scheme:dark;--bg:#0b0b0d;--panel:#161619;--line:#34343b;--text:#eaeaef;--muted:#aaaab4;--accent:#00d9a5;--ok:#60d58b;--warn:#ffbf60;--bad:#ff8278}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:1480px;padding:40px 32px 56px;margin:auto}h1,h2,p{margin:0}h1{font-size:clamp(25px,3vw,38px);letter-spacing:-.035em;line-height:1.2}h2{font-size:18px}header{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-bottom:28px}.brand{font-size:12px;letter-spacing:.16em;color:var(--accent);margin-bottom:10px}.muted,small{color:var(--muted)}.tools{display:flex;gap:8px;flex-wrap:wrap}button,input,select{font:inherit;border:1px solid var(--line);border-radius:7px;background:var(--panel);color:var(--text);padding:10px 14px}button{cursor:pointer}button:hover{border-color:var(--accent)}:focus-visible{outline:2px solid var(--accent);outline-offset:3px}.primary{background:var(--accent);border-color:var(--accent);color:#071a14;font-weight:650}.context{display:flex;flex-wrap:wrap;gap:12px 28px;margin-top:16px}.status{padding:22px 24px;border:1px solid var(--line);border-left:4px solid var(--warn);border-radius:10px;background:var(--panel);margin-bottom:20px}.status.ok{border-left-color:var(--ok)}.status.bad{border-left-color:var(--bad)}.status strong{font-size:20px}.metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;margin-bottom:26px}.metric{padding:20px;border:1px solid var(--line);border-radius:10px;background:var(--panel)}.metric span{display:block;color:var(--muted);font-size:13px}.metric b{display:block;margin-top:10px;font-size:25px;letter-spacing:-.03em}.panel{border:1px solid var(--line);border-radius:10px;background:var(--panel);padding:22px;margin-bottom:20px}.table-head{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:16px}.filters{display:flex;gap:8px;flex-wrap:wrap}.table-scroll{overflow:auto}table{border-collapse:collapse;width:100%;white-space:nowrap;font-size:13px}th,td{text-align:right;padding:13px 12px;border-bottom:1px solid var(--line)}th{font-size:11px;color:var(--muted);letter-spacing:.04em;text-transform:uppercase;cursor:pointer}th:first-child,td:first-child{text-align:left}th:last-child,td:last-child{text-align:left}tr[data-state=issue] td:last-child{color:var(--warn)}tr[data-state=ok] td:last-child{color:var(--ok)}tr:hover{background:var(--bg)}.two{display:grid;grid-template-columns:1fr 1fr;gap:20px}.two .panel{margin:0}.flow{padding:0;list-style:none;display:grid;gap:12px}.flow li{display:flex;gap:12px;align-items:center}.flow small{display:block}.step-index{display:grid;place-items:center;width:28px;height:28px;flex:none;border:1px solid var(--line);border-radius:50%;color:var(--accent);font-size:12px}footer{margin-top:28px;font-size:12px;color:var(--muted)}#empty[hidden],tr[hidden]{display:none}#empty{padding:20px 0;color:var(--muted)}.note{margin-top:12px;font-size:13px}.source{font-size:12px;margin-top:10px;overflow-wrap:anywhere}ul{padding-left:20px}li+li{margin-top:6px}
@media(max-width:1000px){.metrics{grid-template-columns:repeat(3,1fr)}.two{grid-template-columns:1fr}}@media(max-width:600px){main{padding:24px 16px}header{flex-direction:column}.metrics{grid-template-columns:repeat(2,1fr)}.metric{padding:14px}.metric b{font-size:21px}.panel{padding:16px}.filters input{width:100%}}@media print{:root{color-scheme:light;--bg:#fff;--panel:#fff;--line:#ccc;--text:#111;--muted:#555;--accent:#08765b;--ok:#08765b;--warn:#875400}body{font-size:10pt}main{padding:0}.tools,.filters{display:none}.metrics{grid-template-columns:repeat(5,1fr)}.table-scroll{overflow:visible}table{white-space:normal;font-size:8pt}.panel{break-inside:avoid}.two{display:block}}
</style></head><body><main><header><div><div class="brand">SEDRA · RECHNUNGSAUSWERTUNG</div><h1>@@TITLE@@</h1><div class="context"><span>Rechnung <b>@@INVOICE@@</b></span><span>Auftrag <b>@@ORDER@@</b></span></div><p class="source muted">Lauf @@RUN@@ · Workflow-Revision @@REVISION@@ · @@DATE@@</p></div><div class="tools"><button type="button" id="print">Drucken / PDF</button><button type="button" id="csv">Tabelle als CSV</button><button type="button" class="primary" id="json">Prüfdaten als JSON</button></div></header>
@@TEST_NOTE@@<section class="status @@TONE@@"><strong>@@HEADLINE@@</strong><p class="muted note">Fachliches Ergebnis des Positionsvergleichs. Ein abgeschlossener technischer Lauf ist keine Zahlungsfreigabe.</p></section>
<div class="metrics"><div class="metric"><span>Geprüfte Positionen</span><b>@@COUNT@@</b></div><div class="metric"><span>Auffällige / fehlende Positionen</span><b>@@ISSUES@@</b></div><div class="metric"><span>Verglichene Rechnung · netto</span><b>@@INVOICE_TOTAL@@</b></div><div class="metric"><span>Verglichener Auftrag · netto</span><b>@@ORDER_TOTAL@@</b></div><div class="metric"><span>Differenz · netto</span><b>@@DIFFERENCE@@</b></div></div>
<section class="panel"><div class="table-head"><div><h2>Positionsvergleich</h2><small id="count">@@COUNT@@ Positionen</small></div><div class="filters"><input type="search" id="search" aria-label="Positionen durchsuchen" placeholder="Position oder Status suchen …"><select id="filter" aria-label="Prüfstatus filtern"><option value="all">Alle Positionen</option><option value="issue">Nur Auffälligkeiten</option><option value="ok">Nur übereinstimmende</option></select></div></div>
<div class="table-scroll"><table id="positions"><thead><tr><th scope="col" tabindex="0">Position</th><th scope="col" tabindex="0">Menge Rechnung</th><th scope="col" tabindex="0">Menge Auftrag</th><th scope="col" tabindex="0">EP Rechnung</th><th scope="col" tabindex="0">EP Auftrag</th><th scope="col" tabindex="0">Summe Rechnung</th><th scope="col" tabindex="0">Summe Auftrag</th><th scope="col" tabindex="0">Differenz</th><th scope="col" tabindex="0">Status</th></tr></thead><tbody>@@ROWS@@</tbody></table></div><p id="empty" hidden>Keine Positionen für diese Auswahl.</p><p class="muted note">Summen umfassen ausschließlich übermittelte Vergleichspositionen. Fehlende Beträge werden nicht als null Euro gewertet. Spaltenüberschrift anklicken zum Sortieren.</p></section>
<div class="two"><section class="panel"><h2>Prüfhinweise &amp; Klärungsbedarf</h2><ul>@@WARNINGS@@</ul></section><section class="panel"><h2>Durchlaufener Prozess</h2><ol class="flow">@@FLOW@@</ol><p class="muted note">Nicht eigenständig ausgeführte Knoten / Modell-Symbole: @@DISCONNECTED@@</p></section></div><footer>Eigenständiger HTML-Bericht · Suche, Filter und Exporte arbeiten lokal im Browser. CSV exportiert die aktuell sichtbaren Positionen; JSON enthält die vollständigen Prüfdaten dieses Berichts.</footer>
</main><script type="application/json" id="report-data">@@DATA@@</script><script>
(()=>{const q=id=>document.getElementById(id),data=JSON.parse(q('report-data').textContent),body=q('positions').tBodies[0];
function filter(){let n=0;const term=q('search').value.toLocaleLowerCase('de'),state=q('filter').value;for(const row of body.rows){row.hidden=!(row.textContent.toLocaleLowerCase('de').includes(term)&&(state==='all'||row.dataset.state===state));if(!row.hidden)n++}q('count').textContent=n+' von '+body.rows.length+' Positionen';q('empty').hidden=n>0}q('search').oninput=filter;q('filter').onchange=filter;
function download(name,content,type){const url=URL.createObjectURL(new Blob([content],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
q('print').onclick=()=>window.print();q('json').onclick=()=>download('rechnung-pruefdaten.json',JSON.stringify(data,null,2),'application/json;charset=utf-8');
q('csv').onclick=()=>{const cell=s=>'"'+(/^[=+@\\-\\t\\r]/.test(s)?"'"+s:s).replaceAll('"','""')+'"',rows=[...q('positions').tHead.rows,...body.rows].filter(r=>!r.hidden);download('rechnung-positionen.csv','\\ufeff'+rows.map(r=>[...r.cells].map(c=>cell(c.textContent.trim())).join(';')).join('\\r\\n'),'text/csv;charset=utf-8')};
for(const [i,th] of [...q('positions').tHead.rows[0].cells].entries()){let asc=true;const sort=()=>{const val=c=>{const t=c.textContent.trim();if(t==='–')return null;return i>0&&i<8?Number(t.replaceAll('.','').replace(',','.').replace(' €','')):t};const rows=[...body.rows];rows.sort((a,b)=>{const x=val(a.cells[i]),y=val(b.cells[i]);if(x===null)return y===null?0:1;if(y===null)return -1;return(typeof x==='number'?x-y:x.localeCompare(y,'de',{numeric:true}))*(asc?1:-1)});rows.forEach(r=>body.append(r));for(const h of q('positions').tHead.rows[0].cells)h.removeAttribute('aria-sort');th.setAttribute('aria-sort',asc?'ascending':'descending');asc=!asc};th.onclick=sort;th.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();sort()}}}filter();})();
</script></body></html>'''
