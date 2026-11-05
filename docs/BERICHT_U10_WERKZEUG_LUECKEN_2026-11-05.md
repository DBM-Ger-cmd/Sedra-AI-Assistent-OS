# Bericht U10 – Werkzeug-Lücken (W1), 05.11.2026

Basis: main d51083a. Auftrag: ROADMAP_ONE_SEDRA_UIX_WERKZEUGE_2026-11-05 §3, W1. Geändert: **nur Tests** (neu `runtime/tests/test_harness_werkzeug_vollstaendig.py`, 19 Tests) und dieser Bericht. `harness/werkzeuge.py`, `katalog.py`, `api.py`, `freigabe.py`, `schleife.py` und `desk/freigabeklasse.py` sind unverändert (paralleler Bau `wissen_suchen`/`wissen_beantragen`).

## Ergebnis zuerst

- **20 Harness-Werkzeuge** (`werkzeuge.NAMEN`), dazu 4 des Vorarbeiters, 11 Zustandswerkzeuge (`api.LESEN`) und das Bündel `zustand`.
- Alle 20 haben ein Schema, einen Zweig in `ausfuehren`, eine Einordnung und mindestens einen Test, der das Werkzeug aufruft. **Kein Werkzeug ohne Test** – deshalb keine zusätzlichen Einzeltests.
- Alle Werkzeug-IDs in den 7 Vorlagen (`runtime/config/harness_vorlagen/*.yaml`) gibt es; die Anweisungen (`*.md`) und das Arbeitsplatz-Wissen der Harness-Shell nennen kein unbekanntes Werkzeug.
- **6 Lücken**, davon 2 mit echtem Risiko für den parallelen Bau (L1, L3). Heute wirkt keine falsch; sie greifen, sobald ein neues Werkzeug an einer Stelle vergessen wird. Der neue Test findet beide Fälle (Mutationsprobe unten).

## Tabelle je Werkzeug

Legende: Zweig V/A = eigener Zweig in `vorbereiten`/`ausfuehren` (ja · Gruppe = über `LESEN`/`LAUF` · default = letzter Zweig ohne Namen). Einordnung: Katalog = in `katalog.WERKZEUGE`; OK = `OHNE_KARTE`. Klasse = `desk/freigabeklasse.py` (nur für Werkzeuge mit Karte).

| Werkzeug | Schema | Zweig V | Zweig A | Einordnung | Freigabeklasse | Test (Aufruf) |
|---|---|---|---|---|---|---|
| datei_lesen | ja | Gruppe LESEN | ja | Katalog, Karte je Regel | **implizit H** (L2) | ja – test_harness_werkzeuge |
| dateien_auflisten | ja | Gruppe LESEN | ja | Katalog, Karte je Regel | **implizit H** (L2) | ja – test_harness_werkzeuge |
| suchen | ja | Gruppe LESEN | ja | Katalog, Karte je Regel | **implizit H** (L2) | ja – test_harness_werkzeuge |
| datei_schreiben | ja | ja | ja | Katalog | HARNESS_SCHREIBEN (N/H nach Vorbehalt) | ja – test_harness_werkzeuge, _warnung |
| datei_aendern | ja | **default** (Schreibpfad, else in `_fsargs`) | ja | Katalog | HARNESS_SCHREIBEN | ja – test_harness_werkzeuge, _code_stand |
| befehl | ja | ja | ja | Katalog | HARNESS_AUSFUEHREN (H) | ja – test_harness_werkzeuge, _code_stand |
| lauf_starten | ja | ja | ja | Katalog | HARNESS_AUSFUEHREN (H) | ja – test_uix_harness_lauf |
| lauf_stoppen | ja | ja | ja | Katalog | HARNESS_N | ja – test_uix_harness_lauf |
| lauf_status | ja | ja | ja | **nicht im Katalog** – immer frei (freigabe.py Z. 202) | – (keine Karte) | ja – test_uix_harness_lauf |
| modell_laden | ja | Gruppe LAUF | Gruppe LAUF | Katalog | HARNESS_N | ja – test_uix_harness_lauf |
| modell_entladen | ja | Gruppe LAUF | Gruppe LAUF | Katalog | HARNESS_N | ja – test_uix_harness_lauf |
| sitzungen_aufraeumen | ja | ja | ja | **nicht im Katalog** – fester Vorbehalt, immer Karte | HARNESS_N | ja – test_harness_sitzungen_aufraeumen |
| app_oeffnen | ja | **default** (else, Z. 235) | ja | OHNE_KARTE | – | ja – test_harness_app_oeffnen |
| projekt_beantragen | ja | ja | ja | OHNE_KARTE | – | ja – test_harness_app_oeffnen |
| erinnern | ja | ja | ja | OHNE_KARTE | – | ja – test_harness_gedaechtnis, _gedanken |
| sitzungen_auflisten | ja | ja | ja | OHNE_KARTE | – | ja – test_harness_sitzungen_aufraeumen |
| youtube_transkript | ja | ja | ja | OHNE_KARTE | – | ja – test_harness_uebersetzen, _youtube_transkript |
| vorlage_beantragen | ja | ja | ja | OHNE_KARTE | – | ja – test_harness_uebersetzen |
| desktop_lesen | ja | ja | ja | OHNE_KARTE | – | ja – test_harness_desktop |
| belohnungen_lesen | ja | ja | ja | OHNE_KARTE | – | ja – test_harness_belohnung |
| freigaben_offen, freigabe_entscheiden, aufgabe_vorschlagen, aufgabe_beenden (Vorarbeiter) | ja (vorarbeiter.SCHEMAS) | `call` (aufgabe_beenden = default) | – | eigene Rechte der Vorlage, Kiste fragt `extra` zuerst | – (keine Karte) | ja – test_uix_harness_vorarbeiter, _wege |
| 11 Zustandswerkzeuge + `zustand` | ja (chat_tools) | – | – | frei, nur lesen | – | ja – test_harness_zustand |

Vorlagen: bauagent 8, desktop-designer 7, masterchat 28 (davon 11 Zustand), modellierer 7, pruefer 5, rueckblick 8, vorarbeiter 16 Werkzeuge – alle vorhanden. Erlaubnisse nur im masterchat (12, alle Werkzeuge stehen in der Liste der Vorlage).
Wege/Routen (`WEG`, `GESCHUETZT`, `HARNESS_WEGE`, `HARNESS_UNTERWEGE`, `ROUTEN_HARNESS`): stimmen überein; das prüft schon `test_freigabe_vollstaendig` (17 Tests grün). Kein Chat-Werkzeug hat einen eigenen HTTP-Weg.

## Lücken mit Vorschlag

**L1 – `vorbereiten` hat zwei stille Default-Zweige (Risiko für den parallelen Bau).** `harness/werkzeuge.py`
- Z. 235: im Block `FREI_OHNE_KATALOG` ist `else` der Zweig von `app_oeffnen`. Ein neues Werkzeug in `OHNE_KARTE` ohne eigenen `elif` meldet „argument_fehlt: ort“.
- Z. 262: nach allen Zweigen folgt der Schreibpfad. Ein neues Werkzeug, das weder in `OHNE_KARTE` noch in `LESEN`/`LAUF` steht und keinen Zweig hat, wird **wie `datei_aendern` vorbereitet** (Plan mit `fsargs`, Gate `overwrite_existing`). Belegt mit der Mutationsprobe.
- Vorschlag: Z. 235 `elif name == 'app_oeffnen':` und danach `else: raise WerkzeugFehler(f'werkzeug_ohne_zweig: {name}')`; vor Z. 262 `if name not in ('datei_schreiben', 'datei_aendern'): raise WerkzeugFehler(f'werkzeug_ohne_zweig: {name}')`. Danach in den Ausnahmelisten im Test `VORBEREITEN_DEFAULT` leeren.

**L2 – Lesen mit Karte hat keine entschiedene Klasse.** `desk/freigabeklasse.py` Z. 51–53 und 73: `datei_lesen`, `dateien_auflisten`, `suchen` stehen in keiner Menge und bekommen über den Rest von `_harness` die Klasse **H**. Das ist sicher, aber nicht entschieden: eine Karte zum Lesen geht damit nie an den Vorarbeiter (freigabe.py Z. 262) und braucht die Bestätigung der Klasse H.
- Vorschlag (Captain entscheidet): eine Menge `HARNESS_LESEN = frozenset({'datei_lesen', 'dateien_auflisten', 'suchen'})` mit ausdrücklicher Klasse. Wahrscheinlich H lassen, falls das Modell in der Cloud läuft (Daten nach außen), sonst N. Bis dahin stehen sie im Test in `IMPLIZIT_H`.

**L3 – falsches Audit für neue Werkzeuge ohne Karte (Risiko für den parallelen Bau).** `harness/freigabe.py` Z. 211: Das Literal `('erinnern', 'sitzungen_auflisten', 'youtube_transkript', 'vorlage_beantragen', 'desktop_lesen', 'belohnungen_lesen')` nimmt Werkzeuge vom Audit aus. Jedes andere Werkzeug in `OHNE_KARTE` schreibt `HARNESS_PROJEKT_BEANTRAGT`. Kommt `wissen_suchen` in `OHNE_KARTE` und fehlt hier, steht im Audit bei jeder Suche „Projekt beantragt“.
- Vorschlag: `AUDIT_OHNE_KARTE = {'app_oeffnen': 'HARNESS_APP_OEFFNEN', 'projekt_beantragen': 'HARNESS_PROJEKT_BEANTRAGT'}` und `if name in AUDIT_OHNE_KARTE: self._audit(AUDIT_OHNE_KARTE[name], …)`. Neue Werkzeuge sind dann ohne Zutun richtig.

**L4 – `Kiste.wirkung` als Literal.** `harness/freigabe.py` Z. 157 wiederholt die Werkzeuge mit Wirkung von Hand. Heute stimmt die Liste.
- Vorschlag: aus `werkzeuge` ableiten: `WIRKUNG + tuple(n for n in LAUF if n != 'lauf_status') + SITZUNGEN`, am besten als Konstante in werkzeuge.py.

**L5 – `katalog.WERKZEUGE` ohne `lauf_status` und `sitzungen_aufraeumen`** (`harness/katalog.py` Z. 21). Das ist richtig so (frei bzw. fester Vorbehalt), steht aber nirgends. Deshalb lehnt die Einstufungs-Vorschau (`api.py` Z. 1394) beide still ab.
- Vorschlag: ein Kommentar in katalog.py Z. 21, z. B. `AUSSER_KATALOG = ('lauf_status', 'sitzungen_aufraeumen')`. Der Test führt sie bis dahin mit Grund in `OHNE_KATALOG_REGEL`.

**L6 – Vorlagen dürfen Werkzeuge nennen, die die Harness nie anbietet.** `harness/vorlagen.py` Z. 40–41: `bekannte_werkzeuge()` lässt alle `chat_tools.SCHEMAS` zu. Die Kiste bietet davon aber nur `api.LESEN` an. 16 Namen sind so Phantome: propose_intent, propose_task, propose_switch, propose_routing_change, propose_action, open_object, open_place, list_places, list_actions, gateway_* (5), arbeitsplatz_wissen, test_cloud_connection. Auch `vorlage_beantragen` würde sie annehmen. Das Risiko ist klein: `Begrenzt` filtert sie weg, das Modell bekommt also keine zusätzliche Macht. Die Vorlage verspricht aber etwas, das es nicht gibt. `VORGESEHEN` (Z. 22) gibt es inzwischen vollständig; die Liste ist veraltet.
- Vorschlag: `bekannte_werkzeuge = NAMEN + vorarbeiter.SCHEMAS + LESEN` (LESEN aus api.py in ein kleines Modul ziehen, wegen des Import-Kreises) und `VORGESEHEN` streichen. Heute nennt keine Vorlage ein Phantom (Test `test_bekannte_werkzeuge_der_vorlagen`).

## Der neue Test

`runtime/tests/test_harness_werkzeug_vollstaendig.py` (19 Tests, läuft über die Gruppe `harness`). Er kennt keine Werkzeugnamen außer in den begründeten Ausnahmelisten. Ein veralteter Eintrag in einer Ausnahmeliste lässt ihn ebenfalls fehlschlagen.
1. Schema: NAMEN = SCHEMAS, Name im Schema, Pflichtfelder ⊆ Eigenschaften; Vorarbeiter- und Zustandswerkzeuge haben ein Schema, keine Namen doppelt.
2. Einordnung: NAMEN ⊆ katalog.WERKZEUGE ∪ `OHNE_KATALOG_REGEL`; OHNE_KARTE ⊆ NAMEN und = FREI_OHNE_KATALOG; die Katalog-Vorlage lädt.
3. Zweige per AST (`name == …`, `name in (…)`, `name in LESEN/LAUF`) in vorbereiten (+ Helfer) und ausfuehren. Dazu ein Aufruf jedes Werkzeugs mit Schreib-Argumenten: kein Werkzeug darf im Zweig von `app_oeffnen` oder im Schreibpfad landen.
4. Freigabeklasse: jedes Werkzeug mit Karte (NAMEN − OHNE_KARTE − lauf_status) steht in HARNESS_AUSFUEHREN/SCHREIBEN/N oder in `IMPLIZIT_H`.
5. Kiste: `wirkung` und die Audit-Liste in `aufruf` (AST) passen zu werkzeuge/katalog.
6. Vorlagen: jede Werkzeug-ID gibt es (NAMEN ∪ Vorarbeiter ∪ api.LESEN ∪ zustand); `VORGESEHEN` gibt es; keine Vorlage nennt ein Phantom.
7. Texte: Wörter in `…` oder nach „Werkzeug“, die wie Werkzeugnamen aussehen (snake_case), in den Vorlagen-Anweisungen und in `uix/shells/harness/arbeitsplatz.yaml`. Schema-Argumente, Lauf-IDs, `test_*` und 3 begründete Wörter (`KEIN_WERKZEUG`) sind erlaubt. Das ist eine Heuristik: ein neues Fachwort in Backticks kann einen Eintrag in `KEIN_WERKZEUG` nötig machen.

**Mutationsprobe** (Skript, nicht im Repo): ein neues Werkzeug `wissen_xyz` mit Schema, aber ohne Zweige.
- In `OHNE_KARTE`: 4 Tests schlagen fehl – Zweig V, Zweig A, Aufruf landet bei app_oeffnen, Audit L3.
- Im Katalog mit Karte: 5 Tests schlagen fehl – dazu Freigabeklasse und `Kiste.wirkung`.
- Nirgends eingetragen: 6 Tests schlagen fehl.

Nach dem Bau von `wissen_suchen`/`wissen_beantragen` muss der Test also grün werden, ohne dass jemand ihn anfasst. Wird er rot, nennt er die vergessene Stelle.

`expectedFailure` war nicht nötig. Die echten Lücken (L1 Default-Zweige, L2 implizit H, L5 außer Katalog) stehen als begründete Ausnahmelisten im Test.

## Testergebnis

- `run_tests.py harness uix desk` vorher: 110 Dateien, 1205 Tests, 9 übersprungen, 0 rot. Nachher: 111 Dateien, **1224 Tests, 9 übersprungen, 0 rot** (611 s).
- `test_freigabe_vollstaendig`: 17 Tests OK. `test_harness_werkzeug_vollstaendig`: 19 Tests OK (0,3 s).
