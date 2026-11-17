"""Eine Live-Datei je Lauf, Captain-Wartezeit ohne Veraltung, Workflow-Gate im Gate-Speicher der Mission."""
from datetime import datetime, timedelta, timezone

from sedra_runtime.workflows import live
from sedra_runtime.workflows.execution import _gate_merken


def test_zwei_laeufe_desselben_prozesses_bleiben_getrennt(tmp_path):
    live.melde(tmp_path, 'wf-rechnung', 's1', 'laeuft', lauf='M-AAAA0001')
    live.melde(tmp_path, 'wf-rechnung', 's4', 'wartet', lauf='M-BBBB0002', captain=True)
    laeufe = {s['lauf']: s for s in live.lesen(tmp_path)}
    assert laeufe['M-AAAA0001']['schritt'] == 's1'
    assert laeufe['M-BBBB0002']['schritt'] == 's4'
    assert (tmp_path / 'runtime_data' / 'live' / 'wf-rechnung--m-aaaa0001.json').exists()
    assert (tmp_path / 'runtime_data' / 'live' / 'wf-rechnung--m-bbbb0002.json').exists()


def test_alte_datei_ohne_lauf_wird_weiter_gelesen(tmp_path):
    live.melde(tmp_path, 'vollautomatischer-bau', 'bauen', 'laeuft', text='alt')
    assert (tmp_path / 'runtime_data' / 'live' / 'vollautomatischer-bau.json').exists()
    assert [s['prozess'] for s in live.lesen(tmp_path)] == ['vollautomatischer-bau']


def test_wartender_captain_wird_nicht_veraltet(tmp_path):
    vor_zehn_min = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(timespec='seconds')
    live.melde(tmp_path, 'wf-rechnung', 'freigabe', 'wartet', lauf='M-CCCC0003', captain=True, zeit=vor_zehn_min)
    satz = next(s for s in live.lesen(tmp_path) if s['lauf'] == 'M-CCCC0003')
    assert satz['veraltet'] is False


def test_wartender_lauf_ohne_captain_wird_veraltet(tmp_path):
    vor_zehn_min = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(timespec='seconds')
    live.melde(tmp_path, 'wf-rechnung', 's2', 'wartet', lauf='M-DDDD0004', captain=False, zeit=vor_zehn_min)
    satz = next(s for s in live.lesen(tmp_path) if s['lauf'] == 'M-DDDD0004')
    assert satz['veraltet'] is True


def test_gate_landet_im_gate_speicher_der_mission():
    mission = {'identity': {'mission_id': 'M-EEEE0005'}}
    gate = {'gate_id': 'HG-TEST0001', 'mission_id': 'M-EEEE0005'}
    _gate_merken(mission, gate)
    assert mission['human_gates']['pending'] == [gate]
    assert mission['human_gates']['resolved'] == []
