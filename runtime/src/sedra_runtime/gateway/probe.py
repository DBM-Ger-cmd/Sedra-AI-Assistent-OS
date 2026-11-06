"""„Selbst ausprobieren“ (Werkzeug schutz): was würde der Inhaltsschutz mit diesem Text tun? Ruft kein Modell, speichert nichts,
zählt nicht mit. Port der Probe aus der 0.3.0-Lieferung (`sedra_gateway/desk.py`) auf den Guard von Build 16 (core/content_guard)."""
from __future__ import annotations

from ..core.b6core import pseudo as b6pseudo
from ..core.b6core.normalize import normalize
from ..core.b6core.privacy import scan_text
from ..core.content_policy import (ALWAYS, BLOCK, GROUPS, INJECTION, KEY_FORMATS, PSEUDO, REVIEW, SOFT_SECRETS, TEMPLATE_INJECTION,
                                   TRUST_LEVELS, SegmentScan, effective, evaluate, group_of, judge, reason_text, scan_content)

PROBE_MAX = 20_000
_TONE = {'bad': 3, 'warn': 2, 'watch': 1, 'info': 0}


def group_name(g):
    return (GROUPS.get(g) or ALWAYS.get(g) or (g, ''))[0]


def label_of(rule_id):
    r = rule_id.split(':', 1)[0]
    if r in KEY_FORMATS: return 'Schlüssel'
    if r in SOFT_SECRETS: return 'Passwort oder Zugangswert'
    if r == TEMPLATE_INJECTION: return 'Steuermarke für die KI'
    if r in INJECTION: return 'Anweisung an die KI'
    if r.startswith('INVISIBLE'): return 'unsichtbares Zeichen davor'
    if r.startswith('EMAIL'): return 'E-Mail-Adresse'
    if r.startswith('PHONE'): return 'Telefonnummer'
    if r.startswith(('PERSON', 'FILTER')): return 'Name'
    if r.startswith('ADDRESS'): return 'Adresse'
    if r.startswith('IBAN'): return 'Bankverbindung'
    if r.startswith('PAN'): return 'Kartennummer'
    if r.startswith('CUSTID'): return 'Kundennummer'
    if r == 'CTX_P02_V1': return 'Gesundheit oder andere besondere Daten'
    if r == 'CTX_P03_V1': return 'Strafsache'
    if r.startswith('CTX_P04'): return 'Ausweis- oder Steuernummer'
    if r == 'CTX_V01_V1': return 'Minderjährige'
    if r.startswith('CTX_G01'): return 'Kalkulation oder Geschäftsgeheimnis'
    if r == 'CTX_G02_V1': return 'Geheimhaltungsvereinbarung'
    if r.startswith('PLACEHOLDER'): return 'Platzhalter'
    return 'unbekannter Fund'


def merge_spans(spans):
    out = []
    for s in sorted(spans, key=lambda x: (x['start'], -x['end'])):
        if out and s['start'] < out[-1]['end']:
            prev = out[-1]
            if _TONE[s['tone']] > _TONE[prev['tone']]:
                prev.update(label=s['label'], tone=s['tone'], group=s['group'])
            prev['end'] = max(prev['end'], s['end'])
        else:
            out.append(dict(s))
    return out


def probe(guard, text, trust='untrusted', route='local'):
    if not isinstance(text, str) or not text.strip() or len(text) > PROBE_MAX:
        raise ValueError('SG_PROBE_INVALID')
    if trust not in TRUST_LEVELS or route not in ('local', 'cloud'):
        raise ValueError('SG_PROBE_INVALID')
    clean = normalize(text).clean
    hits = scan_content(clean)
    seg = SegmentScan(0, 'user', trust, '', len(clean), hits)
    verdict = evaluate([seg], route, 'probe', guard.cloud_enabled)
    outcome, sharp, watched = effective(verdict, lambda g: guard.enforced(g, route))
    spans = []
    for h in hits:
        level, code = judge(h.rule_id, trust, route)
        g = group_of(code) if level != 'NOTE' else ''
        tone = 'info' if level in ('NOTE', PSEUDO) else ('bad' if level == BLOCK else 'warn') if guard.enforced(g, route) else 'watch'
        spans.append({'start': h.start, 'end': max(h.end, h.start + 1), 'label': label_of(h.rule_id), 'tone': tone, 'group': group_name(g) if g else ''})
    spans = merge_spans(spans)
    preview = None
    if route == 'cloud' and outcome in ('ALLOW', PSEUDO):
        preview = clean
        if outcome == PSEUDO:
            try:
                res = b6pseudo.pseudonymize(clean, scan_text('PROBE', clean))
                preview = None if b6pseudo.recheck(res.text, res.mapping) else res.text
            except Exception:
                preview = None
    head = {'ALLOW': 'Würde durchgelassen', PSEUDO: 'Würde pseudonymisiert an die Cloud gehen',
            REVIEW: 'Würde auf deine Entscheidung warten', BLOCK: 'Würde angehalten'}[outcome]
    if outcome == 'ALLOW' and watched:
        head = 'Würde durchgelassen – im Modus Sandbox würde ich anhalten'
    return {'outcome': outcome, 'head': head, 'text': clean, 'spans': spans,
            'why': [reason_text(r) for r in sharp], 'watched': [reason_text(r) for r in watched],
            'notes': sorted({s['label'] for s in spans if s['tone'] == 'info'}),
            'route': route, 'cloud_preview': preview, 'cloud_failed': route == 'cloud' and outcome == PSEUDO and preview is None}
