"""Prepare the user's invoice workflow for local execution and data minimization."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from sedra_runtime.workflows.store import WorkflowStore
from sedra_runtime.workflows.lokal_daten import Tabellen
from sedra_runtime.workflows.lokal import bewerten

PRIVACY_CODE = r'''
const source = $input.first().json;
const safe = {};
for (const key of ['Rechnungsnummer','Auftragsnummer']) {
  const v = source[key];
  if (typeof v === 'string' && /^[A-Z0-9][A-Z0-9._/-]{2,63}$/.test(v)) safe[key] = v;
}
if (typeof source.Rechnungsbetrag === 'number' && Number.isFinite(source.Rechnungsbetrag)) safe.Rechnungsbetrag = source.Rechnungsbetrag;
const date = String(source.Rechnungstext || '').match(/Rechnungsdatum\s*:\s*(\d{2})\.(\d{2})\.(\d{4})/i);
if (date) safe.Rechnungsdatum = date[3]+'-'+date[2]+'-'+date[1];
if (!safe.Rechnungsnummer || safe.Rechnungsbetrag === undefined) throw new Error('Datenschutz: Rechnungsnummer oder Betrag nicht eindeutig. Lokal prüfen; keine Weitergabe.');
return [{json:{Rechnungstext_Bereinigt:JSON.stringify(safe),Datenschutz:{verfahren:'Feldfreigabeliste v1',freitext_weitergegeben:false,original_bleibt_lokal:true,anonymitaet_garantiert:false,hinweis:'Nur Rechnungsreferenzen, Betrag und Datum. Kein Name, keine Anschrift, keine Kontakt- oder Bankdaten. Referenzen können weiterhin identifizieren; Workflow bleibt lokal.'}}}];
'''


def prepare(project, wid):
    store = WorkflowStore(project)
    rec = store.read(wid)
    if rec['workflow'].get('meta', {}).get('sedra_local_privacy_v1'):
        return rec
    doc = deepcopy(rec['workflow'])
    doc['name'] = 'Lokale Rechnungsprüfung'
    meta = doc.setdefault('meta', {})
    meta.update(sedra_model={'provider': 'llama-cpp-server', 'model': None}, sedra_local_privacy_v1=True,
                sedra_test_mode='Lokale Prüfung der ausgewählten Kursrechnung; keine Cloudübertragung')
    meta.pop('sedra_demo_dataset', None)
    nodes = {n['name']: n for n in doc['nodes']}
    cleaner = 'Datenschutz – Rechnungsdaten minimieren'
    doc['nodes'].append({'id': 'sedra-local-invoice-privacy-v1', 'name': cleaner,
                         'type': 'n8n-nodes-base.code', 'typeVersion': 2, 'position': [540, 0],
                         'parameters': {'mode': 'runOnceForAllItems', 'jsCode': PRIVACY_CODE},
                         'notes': 'Lokal: nur freigegebene Rechnungsfelder weitergeben. Keine garantierte Anonymisierung; lokale Modellwahl bleibt Pflicht für diesen Ablauf.'})
    prior = doc['connections']['Rechnungstext vorbereiten']['main'][0]
    for edge in prior:
        if edge['node'] == 'Information Extractor':
            edge['node'] = cleaner
    doc['connections'][cleaner] = {'main': [[{'node': 'Information Extractor', 'type': 'main', 'index': 0}]]}
    nodes['Information Extractor']['parameters']['text'] = '={{ $json.Rechnungstext_Bereinigt }}'
    tables = Tabellen(project)
    names = {t['name'] for t in tables.liste()}
    if 'LokalePruefergebnisse' not in names:
        tables.importieren('LokalePruefergebnisse', '[]')
    for node, table in [('Auftragsdaten abrufen', 'Auftraege'), ('Auftragspositionen abrufen', 'Auftragspositionen'), ('Kostenübersicht', 'LokalePruefergebnisse')]:
        nodes[node]['parameters']['dataTableId'] = {'__rl': True, 'mode': 'list', 'value': table, 'cachedResultName': table}
    check = bewerten(doc)
    if not check['executable']:
        raise ValueError(check)
    return store.save(doc, wid, rec['revision'], 'Lokale Rechnungsprüfung: Datenminimierung vor KI, lokale Modellwahl und vorhandene Auftragstabellen; eigene Ergebnistabelle')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--project', type=Path, required=True)
    p.add_argument('--workflow', required=True)
    args = p.parse_args()
    rec = prepare(args.project, args.workflow)
    print(json.dumps({'id': rec['id'], 'revision': rec['revision'], 'name': rec['workflow']['name']}, ensure_ascii=False))
