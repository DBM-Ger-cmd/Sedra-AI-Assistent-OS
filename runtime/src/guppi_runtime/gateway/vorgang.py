"""Ein GateWay-Vorgang nach dem Studio Flow (SPEC_GATEWAY_VORGANG_v1 §4).

  01 Wunsch (lokal / Cloud simuliert)                    – nur ein Wunsch
  02 Anfrage + ein .md/.txt → prüfen                      – Scan, Merkmale, Klasse, Übergabeprompt mit Platzhaltern (Recheck 1)
  03 Empfehlung → Freigabe                                – ein Gate mit Bindung über alles, was entschieden wurde
  04 Entwurf                                              – lokal: das Modell durch den Inhaltsschutz; Cloud: ein eingeschalteter Anbieter
                                                            (sonst Simulation);
                                                            Recheck 2 vor, Recheck 3 nach der Rückübersetzung; dann menschliche Prüfung

Das Mapping (Platzhalter → Original) lebt **nur in diesem Prozess** und wird nach der Rückübersetzung gelöscht, ebenso bei Abbruch
und Fehler. Entwürfe liegen getrennt unter `entwuerfe/` mit Löschdatum (F-04); der Vorgang selbst trägt keinen Entwurfstext.
Ein gesperrter Vorgang (Hard Block) speichert keinen Text – nur Hashes und Gründe.

Ticket B6-G-01 (15.10.2026): (G-01) Pseudonymisiert wird nur, was in die Cloud dürfte. Lässt sich ein Text nicht vollständig durch
Platzhalter ersetzen (z. B. Bankverbindung – b6core.pseudo kennt keinen Typ dafür) und ist ohnehin nur der lokale Weg erlaubt, geht
der Text ohne Platzhalter an das lokale Modell, und das steht dabei. Dürfte er in die Cloud, bleibt es ein Fehler (fail-closed).
(G-05) Jeder Vorgang trägt Zweck und verantwortliche Person; beide sind Teil der Bindung der Freigabe."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import secrets
import threading
import time

import yaml

from ..core.b6core import pseudo as b6pseudo
from ..core.b6core.normalize import normalize
from ..core.b6core.privacy import scan_text
from ..core.content_policy import ScanFailure, scan_content
from ..util import atomic_write_json, load_json
from . import klassen, zusatz

LESBAR = ('.md', '.txt', '.docx')            # Anhänge: Text und Word (gateway/dokumente.py); PDF/DOC sind MVP 2
MAX_DOKUMENT = 200_000
MAX_ANFRAGE = 20_000
MAX_VORGAENGE = 200
ZUSTAENDE = ('NEU', 'GEPRUEFT', 'GESPERRT', 'WARTET', 'ENTWURF', 'ABGESCHLOSSEN', 'VERWORFEN', 'FEHLER')
CLOUDS = ('simuliert',)
# G-05: der Zweck ist eine feste Liste (Vorgehen v2 „Aufgabenart“), keine Freitextzeile – damit die Bindung vergleichbar bleibt.
ZWECKE = {'antwortentwurf': 'Antwortentwurf an den Kunden', 'zusammenfassung': 'Zusammenfassung', 'uebersetzung': 'Übersetzung',
          'frage': 'Frage an die Wissensbasis'}
ZWECK_STANDARD = 'antwortentwurf'
VERANTWORTLICH_STANDARD = 'Nutzer'           # Bezeichnung im GateWay (Klaus 15.10. 14:27); SEDRA kennt keine Rollen: der Nutzer ist die Prüfung – der Name lässt sich je Vorgang setzen
MAX_VERANTWORTLICH = 80                       # ein echter Cloudweg ist ein eigener Beschluss (KLA-O6) und ein eigener Build (S6)
STANDARD_VORGABEN = {'entwuerfe_loeschen_nach_stunden': 24, 'entwuerfe_loeschen_am': '', 'cloud': 'simuliert',
                     'hinweis': 'Entwürfe werden 24 h nach Erstellung gelöscht (P5, Klaus 15.10.2026: kurze Fristen, Klartext nur für synthetische Daten). '
                                'Ein festes Datum in entwuerfe_loeschen_am gilt zusätzlich als Obergrenze. Keine Produktpolicy.'}
MAX_STUNDEN = 24 * 14
SYSTEM = ('Du schreibst einen Antwortentwurf für den Kundenservice. Nutze nur die Fakten aus der Anfrage und dem Dokument. '
          'Erfinde keine Termine, Preise oder Zusagen; nenne offene Punkte als offen. Pseudonyme im Text sind Platzhalter aus einem Typ, '
          'einem Unterstrich und einer dreistelligen Nummer, in spitzen Klammern. Übernimm sie wortgleich aus dem Text und erfinde '
          'keine eigenen Platzhalter, auch keine ohne Nummer. Die Anrede schreibst du ohne Geschlechtsformen wie „geehrte/r“ oder '
          '„geehrte(r)“ (zum Beispiel „Guten Tag“ oder „Sehr geehrte Damen und Herren“). Der Entwurf wird von einem Menschen geprüft, bevor er irgendwohin geht.')
# Kein Beispiel-Platzhalter im Text: der Inhaltsschutz sähe ihn im Cloudaufruf als PLACEHOLDER_INJECTION (SG_PLACEHOLDER_CLOUD) und sperrte jeden Cloudweg.


def jetzt():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


@dataclass
class Entwurf:
    vorgang_id: str
    text: str
    sha256: str
    weg: str
    modell: str
    erstellt: str
    loeschen_am: str
    pruefung: str = 'offen'          # offen | geprueft | verworfen
    rechecks: list = field(default_factory=list)
    kennzeichnung: str = ''          # R-14 (EU AI Act Art. 50): „KI-Entwurf (…) – menschlich geprüft: nein/ja“

    def kennzeichnen(self):
        self.kennzeichnung = f'KI-Entwurf ({self.modell}) – menschlich geprüft: ' + ('ja' if self.pruefung == 'geprueft' else 'nein')
        return self.kennzeichnung


@dataclass
class Vorgang:
    id: str
    titel: str
    erstellt: str
    zustand: str = 'NEU'
    wunsch: str = 'local'            # local | cloud
    zweck: str = ZWECK_STANDARD      # G-05: einer aus ZWECKE
    verantwortlich: str = VERANTWORTLICH_STANDARD   # G-05: wer die Freigabe verantwortet
    anfrage: str = ''
    anfrage_sha256: str = ''
    dokument: dict | None = None     # {name, sha256, chars}
    dokument_text: str = ''
    einstufung: dict | None = None
    uebergabe: dict | None = None    # {text, sha256, spans, counts}
    manuell: list = field(default_factory=list)
    weg: str = ''
    binding: str = ''
    mission_id: str = ''
    entwurf_sha256: str = ''
    entwurf_pruefung: str = ''
    fehler: str = ''
    verlauf: list = field(default_factory=list)

    def notiz(self, text):
        self.verlauf.append({'at': jetzt(), 'text': text})
        del self.verlauf[:-40]

    def oeffentlich(self):
        d = asdict(self)
        d.pop('dokument_text', None)
        d['anfrage'] = self.anfrage if self.zustand != 'GESPERRT' else ''
        d['zustand_wort'] = ZUSTAND_WORT.get(self.zustand, self.zustand)
        d['zweck_wort'] = ZWECKE.get(self.zweck, self.zweck)
        return d


ZUSTAND_WORT = {'NEU': 'Neu', 'GEPRUEFT': 'Geprüft – wartet auf Freigabe', 'GESPERRT': 'Gesperrt', 'WARTET': 'Freigabe liegt vor',
                'ENTWURF': 'Entwurf liegt vor – menschliche Prüfung', 'ABGESCHLOSSEN': 'Abgeschlossen', 'VERWORFEN': 'Verworfen', 'FEHLER': 'Fehler'}


class GatewayError(ValueError):
    pass


class GateWay:
    """Die Vorgänge eines Projekts. Persistenz unter local_config/gateway/; das Mapping nie."""

    def __init__(self, root: Path, audit=None, clock=time.time):
        self.root = Path(root) / 'local_config' / 'gateway'
        self.audit, self.clock = audit, clock
        self._lock = threading.RLock()
        self._vaults = {}                         # vorgang_id -> mapping (nur hier, nie auf der Platte)
        self.vorgaenge = {}
        self._load()

    # ------------------------------------------------------------------ Ablage
    def _load(self):
        folder = self.root / 'vorgaenge'
        if folder.is_dir():
            for p in sorted(folder.glob('*.json')):
                try:
                    d = json.loads(p.read_text(encoding='utf-8'))
                    self.vorgaenge[d['id']] = Vorgang(**{k: v for k, v in d.items() if k in Vorgang.__dataclass_fields__})
                except Exception:
                    continue
        self.aufraeumen()

    def _save(self, v: Vorgang):
        folder = self.root / 'vorgaenge'
        folder.mkdir(parents=True, exist_ok=True)
        atomic_write_json(folder / f'{v.id}.json', asdict(v))

    @staticmethod
    def zwecke():
        return [{'id': k, 'name': v} for k, v in ZWECKE.items()]

    def vorgaben(self):
        path = self.root / 'vorgaben.yaml'
        if not path.is_file():
            return dict(STANDARD_VORGABEN)
        try:
            raw = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
        except yaml.YAMLError:
            return dict(STANDARD_VORGABEN)
        out = dict(STANDARD_VORGABEN)
        if isinstance(raw, dict):
            if isinstance(raw.get('entwuerfe_loeschen_am'), str):
                out['entwuerfe_loeschen_am'] = raw['entwuerfe_loeschen_am']
            h = raw.get('entwuerfe_loeschen_nach_stunden')
            if isinstance(h, (int, float)) and not isinstance(h, bool) and 1 <= h <= MAX_STUNDEN:
                out['entwuerfe_loeschen_nach_stunden'] = h
            if raw.get('cloud') in CLOUDS:
                out['cloud'] = raw['cloud']
        return out

    def _log(self, event, **payload):
        if self.audit is not None:
            self.audit.append(event, component='gateway', payload=payload)

    # ------------------------------------------------------------------ Entwürfe (getrennt, mit Löschdatum)
    def _entwurf_pfad(self, vid):
        return self.root / 'entwuerfe' / f'{vid}.json'

    def entwurf(self, vid):
        p = self._entwurf_pfad(vid)
        if not p.is_file():
            return None
        try:
            return Entwurf(**json.loads(p.read_text(encoding='utf-8')))
        except Exception:
            return None

    def _entwurf_speichern(self, e: Entwurf):
        p = self._entwurf_pfad(e.vorgang_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(p, asdict(e))

    def _entwurf_loeschen(self, vid, grund):
        p = self._entwurf_pfad(vid)
        if p.is_file():
            p.unlink()
            self._log('GW_ENTWURF_GELOESCHT', vorgang=vid, grund=grund)
            return True
        return False

    def loeschen_am(self):
        """Löschzeitpunkt eines neuen Entwurfs: jetzt + Frist in Stunden; ein festes Datum in den Vorgaben ist die Obergrenze (P5)."""
        from datetime import timedelta
        vg = self.vorgaben()
        bis = datetime.now(timezone.utc).astimezone() + timedelta(hours=float(vg['entwuerfe_loeschen_nach_stunden']))
        fest = vg.get('entwuerfe_loeschen_am')
        if fest:
            try:
                f = datetime.fromisoformat(fest)
                if f.tzinfo is None:
                    f = f.replace(tzinfo=timezone.utc)
                bis = min(bis, f)
            except ValueError:
                pass
        return bis.isoformat(timespec='seconds')

    def aufraeumen(self):
        """F-04: Entwürfe über ihr Löschdatum hinaus gibt es nicht. Läuft beim Start und bei jedem Blick auf die Liste."""
        folder = self.root / 'entwuerfe'
        if not folder.is_dir():
            return 0
        now = datetime.now(timezone.utc)
        n = 0
        for p in folder.glob('*.json'):
            try:
                bis = datetime.fromisoformat(json.loads(p.read_text(encoding='utf-8'))['loeschen_am'])
                if bis.tzinfo is None:
                    bis = bis.replace(tzinfo=timezone.utc)
            except Exception:
                bis = now
            if now >= bis:
                vid = p.stem
                if self._entwurf_loeschen(vid, 'loeschdatum'):
                    n += 1
                v = self.vorgaenge.get(vid)
                if v and v.zustand == 'ENTWURF':
                    v.zustand = 'ABGESCHLOSSEN'; v.notiz('Entwurf am Löschdatum gelöscht.'); self._save(v)
        return n

    # ------------------------------------------------------------------ 01 neu
    def neu(self, titel, wunsch='local'):
        if wunsch not in ('local', 'cloud'):
            raise GatewayError('wunsch_invalid')
        if len(self.vorgaenge) >= MAX_VORGAENGE:
            raise GatewayError('zu_viele_vorgaenge')
        titel = str(titel or '').strip()[:120] or 'Vorgang'
        vid = 'GW-' + time.strftime('%Y%m%d') + '-' + secrets.token_hex(3).upper()
        v = Vorgang(vid, titel, jetzt(), wunsch=wunsch)
        v.notiz('Angelegt. Wunsch: ' + ('lokale KI' if wunsch == 'local' else 'Cloud-KI'))
        with self._lock:
            self.vorgaenge[vid] = v
            self._save(v)
        self._log('GW_VORGANG_NEU', vorgang=vid, wunsch=wunsch)
        return v

    def get(self, vid):
        v = self.vorgaenge.get(str(vid))
        if v is None:
            raise GatewayError('unbekannter_vorgang')
        return v

    def liste(self):
        self.aufraeumen()
        return [{'id': v.id, 'titel': v.titel, 'erstellt': v.erstellt, 'zustand': v.zustand, 'zustand_wort': ZUSTAND_WORT.get(v.zustand),
                 'klasse': (v.einstufung or {}).get('klasse'), 'policy': (v.einstufung or {}).get('policy'), 'weg': v.weg,
                 'entwurf': self._entwurf_pfad(v.id).is_file()}
                for v in sorted(self.vorgaenge.values(), key=lambda x: x.erstellt, reverse=True)]

    # ------------------------------------------------------------------ 02 prüfen
    def pruefen(self, vid, anfrage, dokument=None, manuell=(), zweck=None, verantwortlich=None):
        """`dokument` = (name, text) oder None. Liest nichts selbst – der Vermittler liest die Datei aus dem Projekt.
        `zweck` und `verantwortlich` (G-05): fehlen sie, bleibt, was der Vorgang hat; leer oder unbekannt ist ein Fehler."""
        v = self.get(vid)
        if v.zustand in ('WARTET', 'ENTWURF'):
            raise GatewayError('vorgang_laeuft')
        if zweck is not None:
            if zweck not in ZWECKE:
                raise GatewayError('zweck_unbekannt')
            v.zweck = zweck
        if verantwortlich is not None:
            verantwortlich = ' '.join(str(verantwortlich).split())[:MAX_VERANTWORTLICH]
            if not verantwortlich:
                raise GatewayError('verantwortlich_fehlt')
            v.verantwortlich = verantwortlich
        if v.zweck not in ZWECKE or not v.verantwortlich:
            raise GatewayError('zweck_oder_verantwortlich_fehlt')
        anfrage = str(anfrage or '')
        if not anfrage.strip():
            raise GatewayError('anfrage_leer')
        if len(anfrage) > MAX_ANFRAGE:
            raise GatewayError('anfrage_zu_lang')
        dok_name, dok_text = (dokument or (None, ''))
        if dok_name is not None:
            if not str(dok_name).lower().endswith(LESBAR):
                raise GatewayError('dokument_nur_md_txt')
            if len(dok_text) > MAX_DOKUMENT:
                raise GatewayError('dokument_zu_gross')
        manuell = [m for m in manuell if m in klassen.MANUELL]
        self._vaults.pop(vid, None)
        self._entwurf_loeschen(vid, 'neue_pruefung')
        anfrage_n = normalize(anfrage).clean
        dok_n = normalize(dok_text).clean if dok_text else ''
        scan_ok = True
        try:
            # Der B6-Scanner plus die Erkennung der Prüffälle (gateway/zusatz.py): Zugangsdaten, Konditionen, Gehalt, Personalnummern
            hits_a = [(h.rule_id, h.kind) for h in scan_content(anfrage_n)] + zusatz.treffer(anfrage_n)
            hits_d = [(h.rule_id, h.kind) for h in scan_content(dok_n)] + zusatz.treffer(dok_n) if dok_n else []
        except ScanFailure:
            hits_a, hits_d, scan_ok = [], [], False
        e = klassen.einstufen(hits_a, hits_d, scan_ok=scan_ok, manuell=manuell)
        v.wunsch = v.wunsch if v.wunsch in ('local', 'cloud') else 'local'
        v.anfrage_sha256 = sha256(anfrage_n.encode('utf-8')).hexdigest()
        v.dokument = {'name': dok_name, 'sha256': sha256(dok_n.encode('utf-8')).hexdigest(), 'chars': len(dok_n)} if dok_name is not None else None
        v.manuell = manuell
        v.einstufung = e.as_dict()
        v.weg, v.binding, v.mission_id, v.entwurf_sha256, v.entwurf_pruefung, v.fehler = '', '', '', '', '', ''
        if e.policy == 'BLOCKED':
            v.anfrage, v.dokument_text, v.uebergabe = '', '', None
            v.zustand = 'GESPERRT'
            v.notiz('Gesperrt: ' + ' '.join(e.gruende))
            self._save(v); self._log('GW_GESPERRT', vorgang=vid, merkmale=e.hard_block)
            return v
        v.anfrage, v.dokument_text = anfrage_n, dok_n
        # Übergabeprompt: Anfrage und Dokument zusammen pseudonymisiert, damit <PERSON_001> in beiden dieselbe ist; Recheck 1
        joined = anfrage_n + ('\n\n' + SEP + '\n\n' + dok_n if dok_n else '')
        if not scan_ok:
            v.uebergabe = None
        else:
            res = None
            nur_lokal = e.wege == ['LOCAL_ONLY']
            scan = scan_text('GW', joined)
            try:
                res = b6pseudo.pseudonymize(joined, scan)
                recheck = b6pseudo.recheck(res.text, res.mapping)
            except b6pseudo.PseudoError as exc:
                res, recheck = None, (str(exc),)
            if recheck and 'S02' in [m['id'] for m in v.einstufung['merkmale']] and recheck == ('B6_PSEUDO_HARD_BLOCK',):
                # Anweisungen an die KI in der eigenen Anfrage: kein Hard Block (K-04, Entscheidung P3 vom 15.10.: Review), aber B6
                # pseudonymisiert so etwas nie. Dann geht nach der Prüfung des Nutzers der Originaltext nur lokal – ohne Platzhalter.
                res = None
                self._ohne_platzhalter(v, anfrage_n, dok_n, joined, 'Die Anfrage enthält Anweisungen an die KI oder Steuerzeichen – so etwas wird '
                                       'nicht pseudonymisiert; nach deiner Prüfung geht der Text nur an das lokale Modell.')
            elif recheck and nur_lokal:
                # G-01: der Text lässt sich nicht vollständig durch Platzhalter ersetzen (etwa eine Bankverbindung), darf aber ohnehin
                # nur lokal verarbeitet werden. Dann ohne Platzhalter an das lokale Modell – das steht dabei. In die Cloud ginge so nichts.
                res = None
                self._ohne_platzhalter(v, anfrage_n, dok_n, joined, 'Nur lokal: ' + _was_bleibt(e) + ' lässt sich nicht durch Platzhalter ersetzen. '
                                       'Der Text geht ohne Platzhalter an das lokale Modell und verlässt den Rechner nicht.')
            elif recheck:
                grund = recheck[0] if recheck[0] != 'B6_PSEUDO_RECHECK_FAILED' else 'B6_PSEUDO_RECHECK_FAILED'
                v.zustand = 'FEHLER'; v.fehler = grund
                v.notiz(('Recheck 1 fehlgeschlagen' if grund == 'B6_PSEUDO_RECHECK_FAILED' else 'Pseudonymisierung fehlgeschlagen: ' + grund)
                        + ' – ein Cloudweg wäre erlaubt, ohne Platzhalter geht deshalb nichts.')
                self._save(v); self._log('GW_FEHLER', vorgang=vid, grund='recheck1' if grund == 'B6_PSEUDO_RECHECK_FAILED' else grund)
                return v
        if scan_ok and res is not None:
            parts = res.text.split('\n\n' + SEP + '\n\n')
            spans = b6pseudo.collect_spans(joined, scan)
            v.uebergabe = {'text': parts[0], 'dokument': parts[1] if len(parts) > 1 else '', 'sha256': res.sha256, 'counts': dict(res.counts),
                           'spans': [[a, b, t] for a, b, t in spans if b <= len(anfrage_n)],
                           'spans_dokument': [[a - len(anfrage_n) - len(SEP) - 4, b - len(anfrage_n) - len(SEP) - 4, t] for a, b, t in spans if a > len(anfrage_n)],
                           'platzhalter': sorted(res.mapping)}
            self._vaults[vid] = dict(res.mapping)
        v.zustand = 'GEPRUEFT'
        v.notiz(f'Geprüft: {e.klasse} ({klassen.KLASSE_WORT.get(e.klasse, "ungeklärt")}), {len(e.merkmale)} Merkmal(e), {e.policy}.')
        self._save(v)
        self._log('GW_GEPRUEFT', vorgang=vid, klasse=e.klasse, merkmale=e.merkmale, policy=e.policy, review=e.review,
                  anfrage_sha256=v.anfrage_sha256, dokument=bool(dok_name))
        return v

    @staticmethod
    def _ohne_platzhalter(v, anfrage_n, dok_n, joined, grund):
        v.uebergabe = {'text': anfrage_n, 'dokument': dok_n, 'sha256': sha256(joined.encode('utf-8')).hexdigest(), 'counts': {},
                       'spans': [], 'spans_dokument': [], 'platzhalter': [], 'unpseudonymisiert': True, 'grund': grund}

    # ------------------------------------------------------------------ 03 Freigabe: die Bindung
    def bindung(self, vid, weg):
        """Alles, was entschieden wurde, in einem Hash: ändert sich eines, passt die Freigabe nicht mehr (G3)."""
        v = self.get(vid)
        if v.zustand != 'GEPRUEFT' or not v.einstufung:
            raise GatewayError('nicht_geprueft')
        if weg not in v.einstufung['wege']:
            raise GatewayError('weg_nicht_erlaubt')
        if v.wunsch == 'local' and weg != 'LOCAL_ONLY':
            raise GatewayError('weg_offener_als_wunsch')          # K-03: nur restriktiver, nie offener
        return self._bindung(v, weg)

    @staticmethod
    def _bindung(v, weg):
        payload = {'vorgang': v.id, 'policy_version': klassen.POLICY_VERSION, 'anfrage': v.anfrage_sha256,
                   'dokument': (v.dokument or {}).get('sha256'), 'klasse': v.einstufung['klasse'],
                   'merkmale': [m['id'] for m in v.einstufung['merkmale']], 'policy': v.einstufung['policy'], 'review': v.einstufung['review'],
                   'weg': weg, 'uebergabe': (v.uebergabe or {}).get('sha256'), 'platzhalter': (v.uebergabe or {}).get('platzhalter', []),
                   'zweck': v.zweck, 'verantwortlich': v.verantwortlich}                       # G-05
        return payload, sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def vorgemerkt(self, vid, weg, mission_id, binding):
        v = self.get(vid)
        v.weg, v.mission_id, v.binding, v.zustand = weg, mission_id, binding, 'WARTET'
        v.notiz('Freigabe vorgelegt: ' + klassen.WEG_WORT[weg] + ('' if v.einstufung['review'] == 'NOT_REQUIRED' else ' – mit deiner Prüfung (R1)'))
        self._save(v)

    def abgelehnt(self, vid):
        v = self.get(vid)
        v.zustand, v.mission_id = 'GEPRUEFT', ''
        v.notiz('Freigabe abgelehnt – nichts ist gelaufen.')
        self._save(v)

    # ------------------------------------------------------------------ 04 ausführen
    def ausfuehren(self, vid, weg, binding, complete_local, modell='lokales Modell', complete_cloud=None):
        """Nach der Freigabe. `complete_local(messages)` ist der Weg zum lokalen Modell (durch den Inhaltsschutz).
        `complete_cloud(messages)` ist der Cloudweg über einen eingeschalteten Anbieter (Router, Inhaltsschutz, Regelwerk); fehlt er,
        bleibt es bei der Simulation, und die Antwort sagt das. Recheck 2 vor und Recheck 3 nach der Rückübersetzung.
        Das Mapping wird danach gelöscht."""
        v = self.get(vid)
        _, expected = self.bindung_wartend(v)
        if v.zustand != 'WARTET' or binding != expected or weg != v.weg:
            raise GatewayError('bindung_passt_nicht')
        mapping = self._vaults.get(vid)
        if mapping is None and (v.uebergabe or {}).get('platzhalter'):
            self._fehler(v, 'mapping_fehlt'); raise GatewayError('mapping_fehlt')      # Neustart dazwischen: neu prüfen
        text = nutzernachricht(v.uebergabe or {})
        rechecks = ['1: Übergabeprompt ohne Platzhalter – nur lokal, nichts verlässt den Rechner' if (v.uebergabe or {}).get('unpseudonymisiert')
                    else '1: Übergabeprompt ohne Originalwerte – ok']
        try:
            if weg == 'LOCAL_ONLY':
                reply = complete_local([{'role': 'system', 'content': SYSTEM, 'trust': 'system'},
                                        {'role': 'user', 'content': text, 'trust': 'captain'}])
            elif complete_cloud is not None:
                # Nur Rolle und Inhalt: ein Anbieter-Schema kennt die Zusatzfelder nicht
                reply = complete_cloud([{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': text}])
                modell = 'Cloud'                                    # der Aufrufer setzt Anbieter und Modell
            else:
                reply = cloud_simuliert(text, v.titel)
                modell = 'Cloud (simuliert)'
            if not isinstance(reply, str) or not reply.strip():
                raise GatewayError('antwort_leer')
            if mapping:
                b6pseudo.check_output(reply, mapping)                     # Recheck 2: keine Originale, keine fremden Platzhalter
                rechecks.append('2: Antwort vor der Rückübersetzung – ok')
                draft = b6pseudo.rehydrate(reply, mapping)
            else:
                draft = reply
            hits = scan_content(draft)                                   # Recheck 3: nichts Hartes in dem, was der Nutzer sieht
            hard = [h.rule_id for h in hits if klassen.merkmal_von(h.rule_id, h.kind) in ('S01', 'F03')]
            if hard:
                raise GatewayError('entwurf_zurueckgehalten:' + ','.join(sorted(set(hard))))
            rechecks.append('3: Entwurf nach der Rückübersetzung – ok')
        except (b6pseudo.PseudoError, GatewayError) as exc:
            self._fehler(v, str(exc)); raise
        except Exception as exc:
            # Anbieterfehler sind so gebaut, dass ihr Text keinen Schlüssel und keinen Prompt enthält (models/cloud_api.py): der Grund
            # ist dann hilfreich. Andere Ausnahmen zeigen nur ihren Typ.
            from ..models.base import ModelAdapterError
            self._fehler(v, str(exc)[:120] if isinstance(exc, ModelAdapterError) else type(exc).__name__); raise
        finally:
            self._vaults.pop(vid, None)                                 # Löschung nach Abschluss/Abbruch/Fehler (K04-PSEUDO-01)
        e = Entwurf(vid, draft, sha256(draft.encode('utf-8')).hexdigest(), weg, modell, jetzt(), self.loeschen_am(), rechecks=rechecks)
        e.kennzeichnen()
        self._entwurf_speichern(e)
        v.zustand, v.entwurf_sha256, v.entwurf_pruefung = 'ENTWURF', e.sha256, 'offen'
        v.notiz('Entwurf liegt vor (' + modell + '). Mapping gelöscht. Jetzt prüfen.')
        self._save(v)
        self._log('GW_ENTWURF', vorgang=vid, weg=weg, modell=modell, sha256=e.sha256, loeschen_am=e.loeschen_am)
        return e

    def bindung_wartend(self, v):
        return self._bindung(v, v.weg)

    def _fehler(self, v, grund):
        v.zustand, v.fehler = 'FEHLER', grund
        v.notiz('Fehler: ' + grund + ' – Mapping gelöscht, kein Entwurf.')
        self._save(v); self._log('GW_FEHLER', vorgang=v.id, grund=grund)

    # ------------------------------------------------------------------ 04 menschliche Prüfung (R2)
    def pruefung(self, vid, urteil):
        v = self.get(vid)
        if v.zustand != 'ENTWURF':
            raise GatewayError('kein_entwurf')
        e = self.entwurf(vid)
        if urteil == 'geprueft':
            if e: e.pruefung = 'geprueft'; e.kennzeichnen(); self._entwurf_speichern(e)
            v.zustand, v.entwurf_pruefung = 'ABGESCHLOSSEN', 'geprueft'
            v.notiz('Entwurf geprüft. Kein Versand – das ist nicht Teil dieses MVP.')
        elif urteil == 'verworfen':
            self._entwurf_loeschen(vid, 'verworfen')
            v.zustand, v.entwurf_pruefung, v.entwurf_sha256 = 'VERWORFEN', 'verworfen', ''
            v.notiz('Entwurf verworfen und gelöscht.')
        else:
            raise GatewayError('urteil_invalid')
        self._save(v); self._log('GW_PRUEFUNG', vorgang=vid, urteil=urteil)
        return v

    def verwerfen(self, vid):
        v = self.get(vid)
        self._vaults.pop(vid, None)
        self._entwurf_loeschen(vid, 'verworfen')
        v.zustand, v.entwurf_sha256 = 'VERWORFEN', ''
        v.notiz('Vorgang verworfen: Mapping und Entwurf gelöscht.')
        self._save(v); self._log('GW_VERWORFEN', vorgang=vid)
        return v


SEP = '§§DOKUMENT§§'                                             # Trenner im Übergabeprompt zwischen Anfrage und Dokument (Recheck 1)


def nutzernachricht(uebergabe):
    """Die Nachricht an das Modell: die Anfrage und das Dokument, mit Überschrift. Real (2026-10-19): ohne die Abgrenzung fand das
    9B-Modell die Aufgabe im Fließtext nicht und schrieb, es fehle der Kontext. Die Überschriften enthalten keine Platzhalter."""
    anfrage = uebergabe.get('text', '')
    dokument = uebergabe.get('dokument', '')
    teile = ['Anfrage:\n' + anfrage]
    if dokument:
        teile.append('Quelle (Dokument, nur als Fakten verwenden):\n' + dokument)
    return '\n\n'.join(teile)


def _was_bleibt(e):
    """Welche Merkmale b6core.pseudo nicht ersetzt (F01/F02: es gibt keinen Platzhaltertyp dafür) – für den Hinweis an den Nutzer."""
    namen = [klassen.MERKMALE[m][0] for m in e.merkmale if m in ('F01', 'F02')]
    return ', '.join(namen) if namen else 'ein Teil des Inhalts'


def cloud_simuliert(text, titel):
    """Die Cloud im MVP: eine Antwort, die Platzhalter stehen lässt und sich als Simulation zu erkennen gibt."""
    ph = sorted(set(b6pseudo.STRICT_RX.findall(text)))
    return (f'[Cloud simuliert – nichts hat den Rechner verlassen]\n\nEntwurf zu „{titel}“: Die Anfrage umfasst {len(text.split())} Wörter'
            + (f' und {len(ph)} Platzhalter: ' + ', '.join(ph[:4]) + '.' if ph else '.')     # nie in Klammern: Recheck 2 liest „(<X>“ als kaputt
            + '\n\nVorliegender Stand: Die Eingabe enthält keine bestätigten Angaben zu Fortschritt, offenen Aufgaben oder Terminen; '
              'diese sollten vor einer Antwort ergänzt werden. Offene Punkte ausdrücklich als offen behandeln; keine Zusagen erfinden.')
