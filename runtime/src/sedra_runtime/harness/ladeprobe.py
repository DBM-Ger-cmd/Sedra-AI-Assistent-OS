"""Ladeprobe (Captain 05.11.2026: „ich möchte nicht, dass nach jedem Update das Laden der Modelle nicht mehr funktioniert“): prüft ohne zu laden, ob jedes Rezept des llama-server
laden könnte, und sagt in Klartext, woran es scheitert – Rezept abgelehnt (Speicher, Fenster, Richtlinie), Modelldatei fehlt, Lader oder Router aus. Läuft beim ersten Aufruf der Harness
nach jedem Start (ein Ereignis `LADEPROBE` im Audit-Log, damit der Verlauf zeigt, was nach einem Update anders war) und jedes Mal, wenn die Info-Seite sich öffnet.
Reine Auswertung: die Zahlen kommen aus `HarnessApi.modelle()` (dieselbe Prüfung wie beim Laden), die Dateien aus der Konfiguration."""
from __future__ import annotations

from pathlib import Path

from .. import local_paths


def _datei(recipe):
    """(Pfad, da?) der GGUF-Datei des Rezepts; None, wenn das Rezept keine nennt (dann gibt es nichts zu prüfen)."""
    server = ((recipe.get('profile') or {}).get('server') or {})
    roh = server.get('gguf')
    if not roh:
        return None
    try:
        pfad = Path(local_paths.expand(str(roh)))
        return str(pfad), pfad.is_file()
    except Exception:
        return str(roh), False


def pruefen(sicht, rezepte):
    """`sicht`: Antwort von `HarnessApi.modelle()`; `rezepte`: die Rezepte des Routers. Ergebnis: {'ok', 'gesamt', 'loader', 'rezepte': [{id, ok, grund, fenster, datei}]}."""
    nach_id = {r.get('id'): r for r in rezepte or []}
    out = []
    for m in (sicht or {}).get('modelle') or []:
        datei = _datei(nach_id.get(m['id']) or {})
        grund = None
        if datei is not None and not datei[1]:
            grund = 'Modelldatei fehlt: ' + datei[0]
        elif m.get('passt') is False:
            grund = str(m.get('grund') or 'abgelehnt')
        elif m.get('passt') is None:
            grund = 'nicht prüfbar'
        out.append({'id': m['id'], 'modell': m.get('modell'), 'ok': grund is None, 'grund': grund, 'fenster': m.get('kontext'), 'geladen': bool(m.get('geladen')),
                    'bedarf_vram_gb': m.get('bedarf_vram_gb')})
    loader = bool((sicht or {}).get('loader'))
    return {'ok': sum(1 for x in out if x['ok']), 'gesamt': len(out), 'loader': loader, 'rezepte': out,
            'frei_vram_gb': (sicht or {}).get('frei_vram_gb'), 'frei_ram_gb': (sicht or {}).get('frei_ram_gb')}


def satz(probe):
    """Die Probe als ein Satz für das Betriebslog."""
    if not probe.get('loader'):
        return 'Ladeprobe: der Modell-Lader ist aus – es lässt sich nichts laden'
    kopf = 'Ladeprobe: %s von %s Rezepten bereit (frei: %s GB Grafik, %s GB RAM)' % (probe['ok'], probe['gesamt'], probe.get('frei_vram_gb'), probe.get('frei_ram_gb'))
    probleme = ['%s: %s' % (x['id'], x['grund']) for x in probe['rezepte'] if not x['ok']]
    return kopf + (' – Probleme: ' + '; '.join(probleme) if probleme else '')
