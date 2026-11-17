"""Prepare a repeatable presentation revision with separate synthetic tables."""
import argparse,json
from copy import deepcopy
from pathlib import Path
from sedra_runtime.workflows.store import WorkflowStore
from sedra_runtime.workflows.lokal_daten import Tabellen
from sedra_runtime.workflows import lokal


def prepare(project,wid):
    store=WorkflowStore(project);record=store.read(wid)
    doc=deepcopy(record['workflow'])
    if (doc.get('meta') or {}).get('sedra_demo_dataset')=='bausteinpruefung-2026-11-18':return record
    tables=Tabellen(project)
    datasets={'Demo Auftraege':[{'auftragsnummer':'AUF-2026-ST-17','gesamt_brutto':2510.90}],
              'Demo Auftragspositionen':[{'auftragsnummer':'AUF-2026-ST-17','lv_position':'01.01.0010','menge':1,'einzelpreis_netto':1200,'gesamtpreis_netto':1200},
                                        {'auftragsnummer':'AUF-2026-ST-17','lv_position':'01.01.0020','menge':20,'einzelpreis_netto':45.5,'gesamtpreis_netto':910}],
              'Demo Kostenuebersicht':[]}
    for name,rows in datasets.items():
        if tables._finden(name):raise ValueError('demo_table_already_exists:'+name)
    for name,rows in datasets.items():tables.importieren(name,json.dumps(rows))
    ref={'Auftragsdaten abrufen':'Demo Auftraege','Auftragspositionen abrufen':'Demo Auftragspositionen','Kostenübersicht':'Demo Kostenuebersicht'}
    for node in doc['nodes']:
        if node['name'] in ref:node['parameters']['dataTableId']={'__rl':True,'mode':'list','value':ref[node['name']],'cachedResultName':ref[node['name']]}
        if node['name']=='Lokales Chat-Modell':
            old=node['name'];node['name']='NVIDIA Chat-Modell';node['parameters']['model']={'__rl':True,'mode':'list','value':'nvidia/nemotron-3.5-bolt-e4b','cachedResultName':'NVIDIA Nemotron Bolt · Vorführung geprüft'}
            if old in doc['connections']:doc['connections'][node['name']]=doc['connections'].pop(old)
    doc['meta'].update(sedra_demo_dataset='bausteinpruefung-2026-11-18',sedra_test_mode='Vorführung mit synthetischer Testrechnung und separaten Demo-Tabellen',sedra_model={'provider':'nvidia','model':'nvidia/nemotron-3.5-bolt-e4b'})
    assert lokal.bewerten(doc)['executable']
    return store.save(doc,wid=wid,base_revision=record['revision'],change_note='Vorführung 18.11.: synthetische Rechnung, separate Demo-Tabellen, geprüftes NVIDIA-Nemotron-Bolt-Modell und fertige HTML-Datei. Bisherige Projekttabellen werden nicht verändert.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--workflow',required=True);a=p.parse_args();r=prepare(a.project,a.workflow);print(json.dumps({'id':r['id'],'revision':r['revision'],'name':r['workflow']['name']},ensure_ascii=True))
