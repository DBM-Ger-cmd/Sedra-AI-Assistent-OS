"""Add the connected extraction and HTML-report stage as a new immutable workflow revision."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL
from sedra_runtime.workflows.store import WorkflowStore
from sedra_runtime.workflows import lokal
from sedra_runtime.workflows.rechnung_dashboard import REPORT


def prepare(project, wid):
    store = WorkflowStore(project)
    record = store.read(wid)
    doc = deepcopy(record['workflow'])
    model_changed=False
    for node in doc['nodes']:
        if node['name']=='Anthropic Chat Model':
            old=node['name'];node['name']='Lokales Chat-Modell';node['type']='@n8n/n8n-nodes-langchain.lmChatOpenAi'
            node['parameters']={'model':{'__rl':True,'mode':'list','value':'loaded-local-model','cachedResultName':'Modellwahl im Workflow / Startassistent'},'options':{}}
            node.pop('credentials',None)
            if old in doc['connections']:doc['connections'][node['name']]=doc['connections'].pop(old)
            model_changed=True
    final_name='HTML-Dashboard als Datei ausgeben'
    if (doc.get('meta') or {}).get('sedra_report') == REPORT:
        final=next((n for n in doc['nodes'] if n['name'] in ('HTML-Auswertung bereitstellen',final_name)),None)
        if final and final['name']==final_name and doc['meta'].get('sedra_report_file')=='rechnung-dashboard.html' and not model_changed:return record
        if final:
            old=final['name'];final['name']=final_name;final['notes']='Ausgabe: fertige Datei rechnung-dashboard.html. Wird als Laufartefakt gespeichert und auf der Arbeitsfläche zum Download angeboten.'
            for types in doc['connections'].values():
                for branches in types.values():
                    for branch in branches:
                        for edge in branch:
                            if edge['node']==old:edge['node']=final_name
            doc['meta']['sedra_report_file']='rechnung-dashboard.html'
            return store.save(doc,wid=wid,base_revision=record['revision'],change_note='HTML-Dashboard ausdrücklich als fertige Datei rechnung-dashboard.html am Ende des Prozesses ausgeben.')
    by_name = {n['name']: n for n in doc['nodes']}
    names = ['Rechnungsprüfung', 'Extract from File', 'Rechnungstext vorbereiten', 'Information Extractor',
             'Rechnungspositionen auslesen', 'Auftragsdaten abrufen', 'Auftragspositionen abrufen',
             'Rechnung mit Auftrag vergleichen', 'Prüfung', 'Kostenübersicht', 'Klärung erforderlich']
    if any(n not in by_name for n in names):
        raise ValueError('invoice_workflow_shape_changed')
    doc.setdefault('meta', {}).update(sedra_report=REPORT, sedra_report_file='rechnung-dashboard.html',sedra_model={'provider': 'llama-cpp-server', 'model': None})
    # Der bestehende Parser bleibt für den rechnerischen Vergleich maßgeblich; das Modell extrahiert Dokumentdaten.
    by_name['Information Extractor']['parameters']['text'] = '={{ $("Rechnungstext vorbereiten").first().json.Rechnungstext }}'
    doc['connections']['Rechnungstext vorbereiten']['main'] = [[{'node': 'Information Extractor', 'type': 'main', 'index': 0}]]
    doc['connections']['Information Extractor']['main'] = [[{'node': 'Rechnungspositionen auslesen', 'type': 'main', 'index': 0}]]
    final = {'id': str(uuid5(NAMESPACE_URL, wid + '/html-dashboard')), 'name': final_name,
             'type': 'n8n-nodes-base.noOp', 'typeVersion': 1, 'position': [260, 720], 'parameters': {},'notes':'Ausgabe: fertige Datei rechnung-dashboard.html, gespeichert als Laufartefakt mit Download auf der Arbeitsfläche.'}
    doc['nodes'].append(final)
    for name in ['Kostenübersicht', 'Klärung erforderlich']:
        doc['connections'].setdefault(name, {})['main'] = [[{'node': final['name'], 'type': 'main', 'index': 0}]]
    positions = [[0, 80], [260, 80], [520, 80], [780, 80], [1040, 80], [1040, 400], [780, 400], [520, 400], [260, 400], [0, 300], [0, 540]]
    for name, position in zip(names, positions):
        by_name[name]['position'] = position
    for node in doc['nodes']:
        if '.lmChat' in node['type']:
            node['position'] = [780, -160]
    check = lokal.bewerten(doc)
    if not check['executable']:
        raise ValueError(json.dumps(check, ensure_ascii=False))
    return store.save(doc, wid=wid, base_revision=record['revision'],
                      change_note='Einheitliche Vorführung: KI-Extraktion über gewähltes lokales/NVIDIA-Modell, vollständiger Prüfpfad und HTML-Auswertung am Ende; kompakte Anordnung.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--workflow', required=True)
    args = parser.parse_args()
    result = prepare(args.project, args.workflow)
    print(json.dumps({'id': result['id'], 'revision': result['revision'], 'name': result['workflow']['name']}, ensure_ascii=False))
