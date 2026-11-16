# Coder (App)

Die Sedra IDE: Aktivitätsleiste, Seitenleiste (Explorer, Suche, Quellcode, Ausführen, Erweiterungen, Agenten), Editor mit Reitern und geteilten Gruppen, Panel unten (Terminal, Ausgabe, Probleme, Debug, Live-Logs), Chat-Leiste rechts, Befehlspalette, Hell und Dunkel, Deutsch und Englisch.

- **Läuft im Rahmen** (`trust: CAPTAIN`, `/uix/frame/coder`, `sandbox="allow-scripts"`): kein Token, keine Route, kein Netz. Ohne `localStorage` im Rahmen merkt sie sich nichts; sie läuft trotzdem.
- **Eigener Editor** statt Monaco (Entscheidung des Captains 16.11.2026): `textarea` über einer gefärbten Ebene, Syntaxfarben für JS, Python, YAML, Markdown.
- **Alle Daten sind Beispieldaten** (`daten.js`, `daten_agenten.js`) und so gekennzeichnet. Terminal, Chat, Quellcode, Erweiterungen sind Attrappen.
- Nicht gebaut: Anbindung an Dateien, Terminal und Agenten (Runde 5 der Spec: nur Entwurf der Lese-Routen).
- Regeln: jede Datei höchstens 400 Zeilen, Farben nur in `tokens.css`, kein `eval`, kein `innerHTML`. Test: `tests/test_uix_coder_app.py`.
