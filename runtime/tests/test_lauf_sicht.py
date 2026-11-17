"""Lauf-Sicht (Schritte 5 und 6): gemeinsames Lauf-Schema, offene Gates, nur lesen, Endpunkt."""
from datetime import datetime, timedelta, timezone

from sedra_runtime.workflows import live, lauf_sicht


def _vor(minuten):
    return (datetime.now(timezone.utc) - timedelta(minutes=minuten)).isoformat(timespec='seconds')


def test_zustaende_werden_im_schema_abgebildet(tmp_path):
    live.melde(tmp_path, 'wf-rechnung', 's1', 'laeuft', lauf='M-AAAA0001')
    live.melde(tmp_path, 'wf-rechnung', 'freigabe', 'wartet', lauf='M-BBBB0002', captain=True)
    live.melde(tmp_path, 'wf-rechnung', 's3', 'fehler', lauf='M-CCCC0003')
    live.melde(tmp_path, 'wf-rechnung', 's4', 'fertig', lauf='M-DDDD0004')
    status = {z['id']: z['status'] for z in lauf_sicht.laeufe(tmp_path)}
    assert status == {'M-AAAA0001': 'RUNNING', 'M-BBBB0002': 'WAITING_APPROVAL', 'M-CCCC0003': 'FAILED', 'M-DDDD0004': 'COMPLETED'}


def test_veraltete_meldung_ist_unknown_und_nicht_aktiv(tmp_path):
    live.melde(tmp_path, 'wf-rechnung', 's2', 'laeuft', lauf='M-EEEE0005', zeit=_vor(10))
    z = lauf_sicht.laeufe(tmp_path)[0]
    assert z['status'] == 'UNKNOWN'
    assert z['active'] is False


def test_aktiv_nur_bei_laufend_oder_wartend(tmp_path):
    live.melde(tmp_path, 'wf-rechnung', 's1', 'laeuft', lauf='M-FFFF0006')
    live.melde(tmp_path, 'wf-rechnung', 's4', 'fertig', lauf='M-GGGG0007')
    aktiv = {z['id']: z['active'] for z in lauf_sicht.laeufe(tmp_path)}
    assert aktiv == {'M-FFFF0006': True, 'M-GGGG0007': False}


def test_offene_gates_aus_dem_gate_speicher():
    missionen = [
        {'identity': {'mission_id': 'M-HHHH0008'},
         'human_gates': {'pending': [{'gate_id': 'HG-1', 'request': {'exact_action': 'run_sedra_workflow', 'targets': ['sedra-lokal://w'], 'risks': ['lokal'], 'rollback_available': False}}],
                         'resolved': []}},
        {'identity': {'mission_id': 'M-IIII0009'}, 'human_gates': {'pending': [], 'resolved': []}},
    ]
    gates = lauf_sicht.gates(missionen)
    assert [(g['gate_id'], g['run'], g['action'], g['status']) for g in gates] == [('HG-1', 'M-HHHH0008', 'run_sedra_workflow', 'offen')]


def test_sicht_liest_nur_und_veraendert_nichts(tmp_path):
    live.melde(tmp_path, 'wf-rechnung', 's1', 'laeuft', lauf='M-JJJJ0010')
    vorher = sorted(p.name for p in (tmp_path / 'runtime_data' / 'live').iterdir())
    lauf_sicht.sicht(tmp_path, [])
    assert sorted(p.name for p in (tmp_path / 'runtime_data' / 'live').iterdir()) == vorher


def test_endpunkt_liefert_laeufe_und_gates(tmp_path):
    from types import SimpleNamespace
    from sedra_runtime.workflows import desk
    live.melde(tmp_path, 'wf-rechnung', 's1', 'laeuft', lauf='M-KKKK0011')
    hub = SimpleNamespace(project_root=tmp_path, runtime=SimpleNamespace(missions=SimpleNamespace(list=lambda: [])))
    antwort = desk._laeufe(hub, None, {})
    assert [z['id'] for z in antwort['laeufe']] == ['M-KKKK0011']
    assert antwort['gates'] == []
