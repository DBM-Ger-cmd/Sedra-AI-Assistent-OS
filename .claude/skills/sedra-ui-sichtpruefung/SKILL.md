---
name: sedra-ui-sichtpruefung
description: Eine geänderte SEDRA-Oberfläche in einem echten Browser durchspielen und per Screenshot ansehen (Wegwerf-Projekt, Edge über Playwright, Schritt für Schritt mit Bildern). Nutzen, nachdem JS/CSS unter uix geändert wurde und gezeigt werden soll, dass es aussieht und funktioniert, nicht nur dass Tests grün sind.
---

# Oberfläche ansehen, nicht nur testen

Grüne Tests sagen wenig über Aussehen und Bedienung; die Browser-Tests laufen ohne `SEDRA_BROWSER=1` übersprungen. Darum die Seite selbst durchspielen.

## Rezept (Skript mit dem Write-Werkzeug anlegen, nicht per Heredoc)
```python
import sys; sys.path[:0] = [RT/'benchmarks', RT/'src']          # RT = runtime-Ordner
from uix_check import start_server
from playwright.sync_api import sync_playwright

def prepare(hub):                      # Wegwerf-Projekt vorbereiten
    holder['rec'] = _save(hub, None, {'workflow': WF})          # z. B. Workflow speichern

url, stop = start_server(print, shell='harness', prepare=prepare)
with sync_playwright() as pw:
    page = pw.chromium.launch(channel='msedge', headless=True).new_page(viewport={'width': 1500, 'height': 1100})
    page.goto(url); page.wait_for_function('()=>window.sedraBoot && window.sedraBoot.ctx')
    page.evaluate("(id)=>window.sedraBoot.ctx.bus.emit('object.open', {type:'workflow',id:id,title:'Workflow'})", wid)
    page.wait_for_function("()=>{const e=document.querySelector('.t-workflow');return e && !e.inert;}")
    app = page.locator('.t-workflow').first
    app.get_by_role('tab', name='Ausführungen').click()
    page.screenshot(path=str(OUT/'schritt1.png'))
```
- Ausführen mit `SEDRA_BROWSER=1 runtime/.venv/Scripts/python.exe -X utf8 <skript>`. `stop()` im `finally`.
- Bedienen wie ein Mensch: `get_by_label(...).fill`, `set_input_files` (geht auch bei versteckten Dateifeldern), `get_by_role('button', name=...).click()`, nach Aktionen `wait_for_timeout(500-1500)`.
- Seitenfehler sammeln: `page.on('pageerror', ...)`, am Ende ausgeben. Leer = gut.
- Bilder mit dem Read-Werkzeug ansehen (Pfad im Scratchpad) und beurteilen: Ist klar, was als Nächstes zu tun ist? Lesbar? Passt es zum Rest?
- Locatoren auf die eigene Komponente begrenzen (`.t-wf-steps .t-wf-chip`), die Seite hat viele gleichnamige Chips.

## Grenzen nennen
- Das Wegwerf-Projekt ist nicht das Live-Projekt des Captains: Daten, Freigaben und Server dort sind anders. Im Bericht trennen, was dort lief und was beim Captain noch ein Neustart oder F5 braucht.
- Keine Freigabe im Browser selbst erteilen (Klasse H braucht den Systemdialog des Captains).
- Nach jeder JS-Änderung `node --check <datei>` und `test_uix_contract` (400 Zeilen je Datei, Farben nur als Token).
