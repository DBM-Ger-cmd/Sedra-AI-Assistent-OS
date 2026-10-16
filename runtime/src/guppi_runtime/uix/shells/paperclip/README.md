# Shell D – Paperclip

Eine Firma statt eines Cockpits: Navigation links, Kopfzeile oben, Seiten in der Mitte, das Gespräch als Schublade rechts.
Die wichtigste Seite ist das **Dashboard**: Kennzahlen, Posteingang, Organigramm und Issues – vier Werkzeuge zu vier
verschiedenen Sammlungen zugleich. Das konnte keine der beiden anderen Shells prüfen (`docs/SPEC_SHELL_E_UND_MODULE_v1.md` §5).

## Umschalten

Im Werkzeug „Module“ auf „Diese Shell nehmen“, oder in `local_config/uix.yaml`: `uix: {shell: paperclip}`. Danach neu laden.

## Die Firmenwörter

| Hier heißt es | und ist | gezeichnet von |
|---|---|---|
| Posteingang | die Entscheidungsliste (`decision:alle`) | `decisions` |
| Issues | die Aufgaben (`task:alle`) | `task` |
| Ziele | die Vorhaben (`intent:alle`) | `intent` |
| Agenten / Organigramm | die Besatzung (`agent:alle`) | `crew` |
| Kosten | das Guppy-Meter | `meter` |

Die Shell benennt um, sie baut nichts nach. Jede Seite ist ein Objekt, das ein vorhandenes Werkzeug zeichnet.

## Wie sie die Teile des Vertrags abbildet

| Vertrag | Paperclip |
|---|---|
| Instrumente | die Kennzahl-Kacheln auf dem Dashboard, dieselbe Lesung aus `/api/strip` |
| Werkstück und Nachweise | Werkstück links, Nachweise als Karten in der Seitenleiste rechts (dritte Darstellung von `slot`) |
| Gespräch | eine Schublade; das Werkzeug bleibt gemountet, nur der Container wird gezeigt oder verborgen. Der Knopf rechts unten zählt, was ankam, solange sie zu war |
| Entscheidungen | der Posteingang **ist** das Werkzeug `decisions`; der Badge an der Navigation kommt aus derselben Route |
| Navigation | die Liste links, „Zurück“ in der Kopfzeile, das Suchfeld mit der Ortskunde (Strg+K) |
| Layout | der Verlauf (`sedra.paperclip.history`); die zuletzt besuchte Seite kommt beim Neuladen zurück |

**Das Suchfeld ist kein zweites Gespräch.** Ein Ort öffnet sich; ein Auftrag oder eine Frage wandert in die Schublade und wird
dort gesendet – derselbe Weg wie die Zeile „An GUPPI senden“ in der Palette des Cockpits.

## Dateien

| Datei | Inhalt |
|---|---|
| `pages.js` | Dashboard (Komposition), Sammlung, einzelnes Objekt mit Seitenleiste, Verlauf. `pageFor`/`pushHistory` sind rein. |
| `nav.js` | Navigation mit Badge. `activeIndex` ist rein. |
| `topbar.js` | Titel, Zurück, Verben des Werkstücks, Suchfeld. |
| `shell.js` | `registerShell`, Start, Schublade, `decide()`, `notify()`. |
| `arbeitsplatz.yaml` | Das Wissen über diese Oberfläche (Satz, Zonen, Firmenwörter mit dem Objekt dahinter, Begriffe) – SEDRA antwortet daraus im Gespräch (Build 24). |

## Abnahme

```
python benchmarks/uix_check.py --shell paperclip
```
