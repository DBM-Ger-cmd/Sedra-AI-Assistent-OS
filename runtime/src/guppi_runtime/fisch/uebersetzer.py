"""Übersetzer-Skill (Translator Fisch v0.1, PROMPT_SPEC A): eine Nachricht für eine andere Zielrolle neu formulieren.
Bedeutung vor Stil; nichts erfinden; Unsicherheit bleibt sichtbar. Hier nur der Systemsatz und das Lesen der Antwort – rein."""
from __future__ import annotations

import re

ROLLEN = {
    'alltag': ('Alltag', 'einfache, direkte Sprache; keine Fachwörter ohne Erklärung'),
    'business': ('Business', 'sachlich, knapp, auf Nutzen und nächste Schritte; keine leeren Floskeln'),
    'management': ('Management', 'Entscheidungsrelevanz zuerst: Ziel, Auswirkung, Risiko, Bedarf an Entscheidung; Details nachrangig'),
    'it_entwicklung': ('IT / Entwicklung', 'präzise technische Begriffe erhalten; Annahmen und Schnittstellen benennen'),
    'einkauf': ('Einkauf', 'Leistung, Menge, Konditionen, Termine, Verantwortliche – nur was der Text wirklich sagt'),
    'vertrieb': ('Vertrieb', 'Kundennutzen und Argumente; nichts versprechen, was der Text nicht hergibt'),
}
TOENE = ('klar', 'freundlich', 'formell')
TIEFEN = ('kurz', 'standard', 'ausfuehrlich')
MAX_TEXT = 6000

SYSTEM = ('Du bist der Übersetzer-Fisch. Du formulierst den Inhalt einer Nachricht für eine andere Zielrolle um – auf Deutsch. '
          'Regeln: 1. Bewahre Aussage, Absicht und Fakten. 2. Erfinde keine Budgets, Termine, Anforderungen, Risiken oder Entscheidungen. '
          '3. Passe Wortwahl, Struktur und Detailtiefe an die Zielrolle an; strukturiere neu, ersetze nicht nur Wörter. '
          '4. Erhalte Fachbegriffe, wenn die Zielrolle sie braucht; erkläre sie sonst kurz. 5. Kennzeichne Unsicherheit und fehlende Angaben. '
          '6. Verändere keine Entscheidung des Absenders. 7. Keine leeren Business-Floskeln. '
          'Antworte genau in diesem Format, ohne weitere Zeilen:\n'
          'ÜBERSETZUNG:\n<die neue Fassung>\n'
          'UNSICHERHEITEN:\n- <je Zeile eine, oder "- keine">\n'
          'HINWEISE:\n- <je Zeile einer, oder "- keine">')


def pruefen(payload):
    """Die Eingabe (rein): Text, Rollen, Ton, Tiefe – oder ValueError."""
    p = payload or {}
    text = str(p.get('text') or '').strip()
    if not text or len(text) > MAX_TEXT:
        raise ValueError('text_required')
    von, nach = str(p.get('von') or 'alltag'), str(p.get('nach') or 'business')
    if von not in ROLLEN or nach not in ROLLEN:
        raise ValueError('unknown_role')
    ton = str(p.get('ton') or 'klar'); tiefe = str(p.get('tiefe') or 'standard')
    if ton not in TOENE or tiefe not in TIEFEN:
        raise ValueError('unknown_style')
    return {'text': text, 'von': von, 'nach': nach, 'ton': ton, 'tiefe': tiefe}


def nachricht(e):
    """Die Nutzernachricht an das Modell (rein)."""
    return (f"Von-Rolle: {ROLLEN[e['von']][0]} ({ROLLEN[e['von']][1]}).\nZu-Rolle: {ROLLEN[e['nach']][0]} ({ROLLEN[e['nach']][1]}).\n"
            f"Ton: {e['ton']}. Detailtiefe: {e['tiefe']}.\n\nNachricht:\n{e['text']}")


def lesen(antwort):
    """Die Antwort des Modells in die drei Felder (rein). Fehlt das Format, ist alles die Übersetzung – nichts wird erfunden."""
    text = str(antwort or '').strip()
    m = re.search(r'ÜBERSETZUNG:\s*(.*?)\s*UNSICHERHEITEN:\s*(.*?)\s*HINWEISE:\s*(.*)$', text, re.S | re.I)
    if not m:
        return {'uebersetzung': text, 'unsicherheiten': [], 'hinweise': [], 'format_ok': False}
    def liste(block):
        items = [re.sub(r'^[-*•]\s*', '', z).strip() for z in block.splitlines() if z.strip()]
        return [i for i in items if i and i.lower() not in ('keine', 'keine.', '-')]
    return {'uebersetzung': m.group(1).strip(), 'unsicherheiten': liste(m.group(2)), 'hinweise': liste(m.group(3)), 'format_ok': True}
