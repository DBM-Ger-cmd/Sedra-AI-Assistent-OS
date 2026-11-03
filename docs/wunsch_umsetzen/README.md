# Wunsch aus dem Chat umsetzen – der Weg des MasterChat

Hier liegen die festen Wege, auf denen der **MasterChat** (Vorlage `masterchat`) neue Funktionen für SEDRA aus dem Chat heraus umsetzt – vom Wunsch des Captains bis zum
Nachweis. Der Ordner liegt im Schreibbereich des Projekts „Sedra Entwicklung“ (`docs/**`), damit der MasterChat hier ohne Karte schreiben darf.

| Schritt | Ordner | Was dort liegt |
|---|---|---|
| 1 Wunsch | `01_wuensche/` | `W-<JJJJ-MM-TT>-<kurz>.md` nach `00_vorlagen/WUNSCH_VORLAGE.md`: der Wunsch in den Worten des Captains |
| 2 Auftrag | `02_auftraege/` | `A-<JJJJ-MM-TT>-<kurz>.md` nach `00_vorlagen/AUFTRAG_VORLAGE.md`: Ziel, höchstens 6 Schritte, Abnahme, Status |
| 3 Ergebnis | `03_ergebnisse/<Auftrag>/` | `Bericht.md`: was geändert wurde, Dateien, Testausgabe wortgetreu, was **nicht** geprüft wurde |
| 4 Lücken | `04_luecken/` | `L-<JJJJ-MM-TT>-<kurz>.md` nach `00_vorlagen/LUECKE_VORLAGE.md`: fehlt ein Werkzeug oder eine Berechtigung, steht es hier – nie ein Umweg |

Vorschläge für Stellen, die dem MasterChat verboten sind (Kern, Freigabe-Code der Harness, Vorlagen, `local_config`), schreibt er als Datei in `04_luecken/` oder `03_ergebnisse/`;
der Captain setzt sie selbst oder mit Claude um.

Weg im Einzelnen: `runtime/config/harness_vorlagen/masterchat.md`. Aufbau und Gründe: `docs/ARBEITSWEG_WUNSCH_UMSETZEN.md`.
