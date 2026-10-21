# Shell D – Paperclip

Eine Firma statt eines Cockpits: Navigation links, Kopfzeile oben, Seiten in der Mitte, rechts daneben die Fenster der Agenten,
das Gespräch mit SEDRA als Schublade. Seit Version 1.2.0 (Spec 4, `docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md` D4.1) ist sie die
Arbeitsfläche des Agenten-Teams.
Die wichtigste Seite ist das **Dashboard**: Kennzahlen, Posteingang, Organigramm und Issues – vier Werkzeuge zu vier
verschiedenen Sammlungen zugleich. Das konnte keine der beiden anderen Shells prüfen (`docs/SPEC_SHELL_E_UND_MODULE_v1.md` §5).

## Umschalten

Im Werkzeug „Module“ auf „Diese Shell nehmen“, oder in `local_config/uix.yaml`: `uix: {shell: paperclip}`. Danach neu laden.

## Die Firmenwörter

| Hier heißt es | und ist | gezeichnet von |
|---|---|---|
| Abschnitt | Hier heißt es | und ist | gezeichnet von |
|---|---|---|---|
| – | Posteingang | die Entscheidungsliste (`decision:alle`) | `decisions` |
| Arbeit | Issues | die Aufgaben des Teams (`issue:alle`); solange kein Werkzeug `issue:alle` zeichnet, die Missionen (`task:alle`, `issuesTarget`) | `board`, bis dahin `task` |
| Arbeit | Ziele | die Vorhaben mit Stufen (`intent:alle`) – die erste Karte des Dashboards; eine Stufe wird ein Issue | `intent` |
| Arbeit | Routinen | wiederkehrende Aufgaben (`routine:alle`) | `routines` (fehlt noch: die Seite sagt es) |
| Team | Organigramm | das Team als Baum (`agent:alle`) | `org`, bis dahin `crew` |
| Team | Agenten | Rollen und Agenten des Agent Managers (`agent:rollen`) | `crew` |
| Betrieb | Kosten | das Guppy-Meter | `meter` |
| Betrieb | Modelle und Slots | Slots über der Werkstatt (`model:alle`) | `slots`, dann `workshop` |
| Betrieb | KI-Labor | Anbieter, Schlüssel, Modelle, Tests (`labor:labor`) | `labor` |
| Assistenten | Planungstisch | die Arbeitsumgebung der KI-Assistenten (`planung:tisch`): Ziele mit Stufen und Aufträge vorschlagen; „Übernehmen“ legt an | `planung` |

Die Shell benennt um, sie baut nichts nach. Jede Zeile ist ein Objekt; wer es zeichnet, sagt die Registrierung über das ganze
Objekt (`registry.forObject`, Vertragsnachtrag N1). Fehlt ein Werkzeug, bleibt die Zeile stehen und die Seite sagt, warum sie leer
ist – sie verschwindet nicht (UIX-02, UIX-10).

## Agentenfenster

Ein Agent (`agent:<id>`) ist keine Seite: die Shell öffnet sein Fenster im Stapel rechts (Zone `pc-stack`), die Seite darunter
bleibt stehen. Höchstens vier Fenster sind offen; ein fünftes verkleinert das älteste zum Reiter (geschlossen wird nur mit „✕“).
Welche Agenten offen sind, merkt sich die Shell im Browser (`sedra.paperclip.windows`); den Inhalt liest das Werkzeug vom Server.
Gezeichnet wird ein Fenster von dem Werkzeug, das `agent:*` handelt, je Fenster eine Instanz (Nachtrag N2). Die Verben eines
Fensters stehen im Fenster, nicht in der Kopfzeile.

## Ereignisse

Die Shell hört `agent.changed`, `issue.changed`, `budget.warning`, `slot.changed` (Nachtrag N3), dazu `decision.*`,
`task.changed`, `model.changed` und `desk.resync`, und frischt dann Badge, Kacheln und Fensterverben auf. Einen Zeitgeber hat sie
nicht; ein Schub von Ereignissen liest einmal und höchstens einmal nach (`coalesce`). Eine Budgetwarnung erscheint als Hinweis.

## Wie sie die Teile des Vertrags abbildet

| Vertrag | Paperclip |
|---|---|
| Instrumente | die Kennzahl-Kacheln auf dem Dashboard, dieselbe Lesung aus `/api/strip` |
| Werkstück und Nachweise | Werkstück links, Nachweise als Karten in der Seitenleiste rechts (dritte Darstellung von `slot`) |
| Gespräch | eine Schublade; das Werkzeug bleibt gemountet, nur der Container wird gezeigt oder verborgen. Der Knopf rechts unten zählt, was ankam, solange sie zu war |
| Entscheidungen | der Posteingang **ist** das Werkzeug `decisions`; der Badge an der Navigation kommt aus derselben Route |
| Navigation | die Liste links, „Zurück“ in der Kopfzeile, das Suchfeld mit der Ortskunde (Strg+K) |
| Layout | der Verlauf (`sedra.paperclip.history`, mit `view` im Schlüssel); die zuletzt besuchte Seite kommt beim Neuladen zurück, ebenso die offenen Agentenfenster (`sedra.paperclip.windows`) |

**Das Suchfeld ist kein zweites Gespräch.** Ein Ort öffnet sich; ein Auftrag oder eine Frage wandert in die Schublade und wird
dort gesendet – derselbe Weg wie die Zeile „An SEDRA senden“ in der Palette des Cockpits.

## Dateien

| Datei | Inhalt |
|---|---|
| `pages.js` | Dashboard (Komposition), Sammlung, einzelnes Objekt mit Seitenleiste, Seitenart `window`, Verlauf. `pageFor`/`pushHistory` sind rein. |
| `nav.js` | Navigation mit Abschnitten und Badge. `activeIndex`, `issuesTarget`, `coalesce` sind rein. |
| `topbar.js` | Titel, Zurück, Verben des Werkstücks, Suchfeld. |
| `windows.js` | Fensterstapel der Agenten. `openWindow`, `closeWindow`, `toggleWindow` sind rein. |
| `shell.js` | `registerShell`, Start, Zonen, Schublade, Ereignisse, `decide()`, `notify()`. |
| `arbeitsplatz.yaml` | Das Wissen über diese Oberfläche (Satz, Zonen, Firmenwörter mit dem Objekt dahinter, Begriffe) – SEDRA antwortet daraus im Gespräch (Build 24). |

## Abnahme

```
python benchmarks/uix_check.py --shell paperclip
```
