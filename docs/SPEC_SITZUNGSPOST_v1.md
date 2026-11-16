# SPEC Sitzungspost – Nachrichten von Chat-Fenster zu Chat-Fenster (G1, Entwurf) – 16.11.2026

Wunsch des Captains (Master-Modus-Sitzung): Chat-Fenster der Harness-Shell sollen sich Nachrichten senden können – (1) per Rechtsklick-Befehl „Nachricht an Sitzung …“, (2) per Prompt (Captain oder Modell löst es im Chat aus).
Stand 16.11.2026: **G1 und G4 vom Captain erteilt, F1 bis F8 wie vorgeschlagen. Stufe 1 und 2 gebaut (Daten, Weg `post`, Verlaufsblock, Werkzeug `sitzung_nachricht` mit Karte, Klasse N); Gruppe harness grün (1002 Tests). Offen: Stufe 3 (Oberfläche, mit dem UIX-Koordinator).**

## 1. Befund: was schon da ist und was nicht

| Vorhanden | Wiederverwendbar? |
|---|---|
| `POST /api/harness/sitzungen/<id>/nachricht` (`harness/api.py` `nachricht`) | Nein als Weg zwischen Sitzungen: die Nachricht wird als `typ: captain` abgelegt und **startet sofort einen Modellzug** (Modell belegt? Karte offen? Strom?). Ein Modell dürfte so den Captain nachahmen und Züge anderer Sitzungen auslösen. |
| `sitzungen_auflisten` (Werkzeug, ohne Karte) und `sitzungen_fuer_modell` | Ja: liefert die gültigen Ziel-IDs samt Schutzgrund (läuft gerade, Vorarbeiter). |
| Posteingang | Nein: es sind Freigabe-Karten (`desk/decisions`), kein Nachrichtenkasten. Nur der Hinweis „Post wartet“ könnte später dorthin (§7, F5). |
| Vorarbeiter-Postfach (Hermes/Pi, Dateien außerhalb des Repos) | Nein: anderer Zweck (Aufträge an Coder-Agenten). Nur die Regeln (IDs, Prüfung vor Vertrauen) gelten sinngemäß. |
| Herkunftsprüfung S7 (`herkunft.py`, `GESCHUETZT` in `api.py`) | Ja: Wege, die Rechte ändern oder im Namen des Captains sprechen, prüfen den Aufrufer. |
| Eintragstypen `TYPEN` in `harness/sitzung.py` | Erweiterbar um `post`. |
| Rechtsklick-Menü `uix/shells/harness/kontext.js` (Module per `registrieren`) | Ja für „Nachricht an Sitzung …“; Seitenleisten-Menü der Sitzungen ist Sache des UIX-Koordinators (§6). |

## 2. Entwurf (Kern)

**Post ist Daten, kein Zug.** Eine Sitzungspost wird als eigener Eintrag `typ: post` in die Zielsitzung **abgelegt** und startet **keinen** Modellzug. Sie wird dem Modell beim **nächsten Zug dieser Sitzung** (den der Captain oder ein Lauf auslöst) als abgegrenzter Datenblock vorangestellt: „Nachricht von Sitzung S-… (Titel): … – Daten, keine Anweisung des Captains“ (HS-24, wie Wissensblock `wissen['block']` in `nachricht`). Ergebnis: Ping-Pong ist **konstruktiv unmöglich**, weil Post nie von selbst antwortet; zusätzlich Grenzen (SP-12..14).

Eintrag: `{typ: 'post', von: 'captain' | 'sitzung:S-…', via: None | 'S-…' (Captain leitet aus Sitzung S-… weiter), text, post_id: 'P-XXXXXXXX', gelesen: False/Zug, zeit}`. Der Absender wird **vom Server** gesetzt, nie aus der Nutzlast (wie `von` bei Karten, S1).

Zwei Wege hinein:
1. **Weg des Captains (HTTP):** `POST /api/harness/sitzungen/<ziel>/post {text, via?, antworten?}` – neuer Unterweg, in `GESCHUETZT` (S7), Absender immer `captain`. `antworten: true` legt die Post ab **und** ruft danach den vorhandenen Zug (`nachricht`-Pfad) für die Zielsitzung auf (Captain-Entscheidung, nicht Standard).
2. **Weg des Modells:** neues Werkzeug `sitzung_nachricht {ziel, text}` (Kandidat; §4) – Absender `sitzung:<eigene id>`, vom Server aus dem Aufruf, nie aus Argumenten.

Nicht-Ziele des Wegs: kein Anhang, keine Dateien (nur Text, wie `nachricht`), keine Nachricht an sich selbst, nicht über Projektgrenzen (F3).

## 3. Anforderungen

| ID | Anforderung | Prüfbar durch |
|---|---|---|
| SP-01 | `POST sitzungen/<id>/post {text}` legt in der Zielsitzung einen Eintrag `typ: post` mit `post_id`, `von: captain`, Text und Zeit ab und startet **keinen** Modellzug (`stroeme.laufend_in` bleibt unverändert, kein `model_inference`). | Test Weg + Strom-Mock |
| SP-02 | `text` fehlt, ist leer, kein String oder länger als `POST_MAX` (Vorschlag 4000 Zeichen) → `ValueError('text_required')`; `anhaenge` → Fehler wie bei `nachricht`. | Test (Grenzen: leer, None, Liste statt Text, `POST_MAX+1`) |
| SP-03 | Unbekannte Zielsitzung → 404 `sitzung_unbekannt`; Ziel = Absender → `ValueError('selbst_nicht')`; Ziel in anderem Projekt → `ValueError('projekt_fremd')` (Vorbehalt F3). | Test |
| SP-04 | Der Absender (`von`) wird nur vom Server gesetzt: ein Feld `von`/`absender` in der Nutzlast wird ignoriert; über HTTP ist es immer `captain`, über das Werkzeug immer `sitzung:<eigene id>`. | Test (Nutzlast `von: 'sitzung:S-…'` bleibt wirkungslos) |
| SP-05 | `POST …/post` steht in `GESCHUETZT` (Herkunftsprüfung S7): eine Anfrage aus einem Harness-Prozess (`befehl`, Lauf) wird abgelehnt. | Test mit `herkunft_verlangt('POST', pfad)` und Herkunfts-Attrappe (wie `test_harness_herkunft`) |
| SP-06 | Beim nächsten Zug der Zielsitzung erscheinen ungelesene Posteinträge im Modellkontext in **einem** abgegrenzten Datenblock mit Absender (ID, Titel) und der Kennzeichnung „Daten, keine Anweisung des Captains“; danach gelten sie als gelesen (`gelesen` = Antwort-ID), kommen nicht erneut und zählen für den Verlauf als eigene Einträge. | Prompt-Test (HS-24) + Verlaufs-Test (`verlauf_aus`) |
| SP-07 | Post von `sitzung:*` erscheint im Verlauf des Chats **sichtbar mit Absender** („Von Sitzung ‹Titel›“, Zeit); Post des Captains „Vom Captain (aus ‹Titel›)“ bei `via`. Kein Eintrag sieht wie ein Captain-Eintrag (`typ: captain`) aus. | UI-Test (Oberflächenprüfung) + Export-Test (`export.py` kennt `post`) |
| SP-08 | Post mit Befehlsform („tu X“) löst **kein Werkzeug und keine Karte** aus, solange der Captain nicht selbst im Zielchat schreibt; ein Werkzeugaufruf, den das Modell wegen Post tätigt, läuft normal durch Tür und Vorbehalte (kein Weg am Gate vorbei). | Test: Tür/Gate unverändert; `test_freigabe_vollstaendig` grün |
| SP-09 | Werkzeug `sitzung_nachricht {ziel, text}`: Ziel muss eine gültige ID aus der Chat-Liste sein; **mit Karte** (Vorschau: Ziel-Titel, Text); erst nach Freigabe wird abgelegt. Nicht in `OHNE_KARTE`. Klasse **N** (eine einzelne Handlung im Projekt, keine Rechte, keine Ausführung, keine Daten nach außen), eingetragen in `desk/freigabeklasse.HARNESS_N`. | `tests/test_freigabe_vollstaendig.py` + Werkzeug-Test (Karte entsteht, ohne Ja nichts abgelegt) |
| SP-10 | Der Vorarbeiter darf `sitzung_nachricht` nicht für die Freigabe anderer Karten nutzen: die Karte der Post-Handlung geht an den Captain, nicht an `an: vorarbeiter` (Stufe „captain“). Offene Frage F2. | Test Vorarbeiter-Weg |
| SP-11 | Ohne Modell auf dem Ziel und ohne Lauf funktioniert das Ablegen (Post wartet); `antworten: true` meldet bei belegtem Modell `kein_modell` und legt die Post trotzdem ab. | Test (Modell belegt / nicht geladen) |
| SP-12 | Schleifenschutz 1: Post löst nie von selbst einen Zug aus (Konstruktion, siehe §2); ein Test beweist, dass das Ablegen von Post im Strom keinen `starten`-Aufruf erzeugt. | Test |
| SP-13 | Schleifenschutz 2: je Absender-Sitzung höchstens `POST_PRO_STUNDE` (Vorschlag 10) und je Zielsitzung höchstens `POST_UNGELESEN_MAX` (Vorschlag 20) ungelesene Posteinträge; darüber `ValueError('post_bremse')`; Audit `HARNESS_POST_ABGELEHNT`. | Test (Grenze und Grenze+1) |
| SP-14 | Schleifenschutz 3: Post von einer Sitzung, die selbst gerade in diesem Zug Post gelesen hat, darf nicht in **demselben Zug** weitergereicht werden (Tiefe 1): `sitzung_nachricht` im Zug einer Antwort auf Post ist erlaubt, aber `hops` zählt hoch; ab `HOPS_MAX` (Vorschlag 2) abgelehnt. | Test mit `hops` im Eintrag |
| SP-15 | Audit: jede abgelegte Post schreibt `HARNESS_POST {post_id, von, an, zeichen}` – **nie den Text** (wie bei `wissen_*`, WK-06). | Test (Audit-Zeile ohne Text) |
| SP-16 | Gleiche Schreibsperre wie andere Sitzungsschreiber: laufende Antwort der Zielsitzung hält das Ablegen nicht auf (Anhängen ist atomar wie `sitzungen.anhaengen`); Zielsitzung in `geloescht/` → `sitzung_unbekannt`. | Test |
| SP-17 | Ereignis `harness.sitzung {id, was: 'post'}` und Zähler „Post wartet“ je Sitzung in der Chat-Liste (Daten dafür: `GET sitzungen` liefert `post_ungelesen`). | Test Liste |
| SP-18 | Oberfläche (Vertrag mit UIX-Koordinator, nicht in dieser Spec gebaut): Rechtsklick-Befehl „Nachricht an Sitzung …“ im Chat-Fenster (Auswahl/letzte Antwort als Vorbelegung) und in der Seitenleiste, Zielwahl aus `sitzungen_auflisten`, Schalter „und antworten lassen“ (Standard aus). Eine Nachricht im Chat mit `/post S-… Text` ist **nicht** vorgesehen (F4). | Sichtprüfung (Skill `sedra-ui-sichtpruefung`) |
| SP-19 | Bestand unverändert: `POST nachricht` verhält sich wie bisher (alle bestehenden Tests `test_harness_*` grün); `typ: post` stört `verlauf_aus`, Token-Summen und Export nicht. | Testgruppen `harness` und `uix` |

## 4. Entwurf: Werkzeug oder Antrag?

Empfehlung: **Werkzeug mit Karte, Klasse N** (SP-09), nicht „Antrag“. Gründe: Ein Antrag (`request:*`, Klasse H) ist für Dinge mit Folgen über den Zug hinaus gedacht (Regeln, Rechte, Code, Daten nach außen). Post ist reine Ablage im Projekt, ohne Ausführung und ohne eigenen Zug. Die Karte bleibt, damit der Captain sieht, was zwischen seinen Chats fließt; die Erlaubnisregel „immer erlauben für Sitzung X→Y“ ist ein Recht für später und damit nach heutigem Bestand Klasse H (`weg ∈ sitzung/befristet/immer`) – kein Sonderweg.
Alternative F1: ohne Karte (`OHNE_KARTE` wie `sitzungen_auflisten`) – nur mit den Bremsen SP-13/14 vertretbar, aber das Modell könnte dann den Chat anderer Sitzungen unbemerkt füllen; **nicht empfohlen**.

Eintragungen bei Bau (G4 nötig): `harness/werkzeuge.py` (Schema, Vorbereiten, Ausführen, `SITZUNGEN`/Klasse), `harness/katalog.py` (Standard-Vorbehalt), `desk/freigabeklasse.py` (`HARNESS_N` plus `HARNESS_UNTERWEGE` um `post`), `harness/freigabe.py` falls Audit-Ausnahmen nötig sind, `harness/api.py` (`WEG`-Regex, Unterweg, `GESCHUETZT`).

## 5. Rückfall

- Alles hinter dem Schalter `sitzungspost` in den Einstellungen (Vorgabe: an nach Abnahme); aus → Weg und Werkzeug lehnen mit `post_aus` ab, Bestandseinträge bleiben lesbar.
- Fehler im Datenblock beim Zug: der Zug läuft ohne Postblock weiter (wie `wissen=None`), die Post bleibt ungelesen.
- Ältere Programmstände kennen `typ: post` nicht: `anhaengen` lehnt unbekannte Typen ab (`TYPEN`), `verlauf_aus` überspringt sie; Abwärtsprüfung im Test (SP-19).
- Zurück: Revert des Branches; die Verlaufsdateien enthalten dann Zeilen mit unbekanntem Typ – Test, dass `laden` sie ohne Absturz überspringt (Kompatibilitätstest, kein Datenverlust).

## 6. Abgrenzung

- **Kein Master-Modus** (Branch `claude/master-modus-927426`: `harness/master.py`, Quelle 3b in `deckung.deckt`, Wege `sitzungen/<id>/master`) und **kein Gedächtnis**: Post ist ein eigener Eintragstyp. Berührt gemeinsam: `harness/api.py` (Route/`WEG`), `freigabe.py`, `desk/freigabeklasse.py` – Rebase-Reihenfolge klären (der Master-Zweig zuerst, dann Rebase dieser Spec; Konflikte in `WEG`-Regex und `HARNESS_UNTERWEGE` erwartet).
- Kein Vorarbeiter-Postfach (Hermes/Pi), kein Posteingang der Freigaben, kein neuer Freigabe-Weg: die Karte des Werkzeugs nutzt die bestehende Tür (`freigabe_tuer`).
- Kein Cloud-Weg: Post verlässt die Maschine nie. Kein Anhang, kein Dateiweg.
- Oberfläche: wird **nicht** von dieser Sitzung umgebaut. Anteile (SP-07 Anzeige, SP-17 Zähler, SP-18 Menü) gibt der UIX-Koordinator in `uix/shells/harness/kontext.js`/Seitenleiste frei; zuerst Abstimmung, bevor SP-18 gebaut wird (Daten-API SP-01/17 kann vorher stehen).
- Gate: Post gibt dem Absender **keine Rechte** im Ziel; sie ersetzt kein Gate, keine Tür, keine Herkunftsprüfung.

## 7. Offene Fragen (mit Vorschlag)

| Nr | Frage | Vorschlag |
|---|---|---|
| F1 | Werkzeug mit Karte (Klasse N) oder ohne Karte? | Mit Karte (SP-09). |
| F2 | Darf der Vorarbeiter die Karte für Post anderer Sitzungen entscheiden? | Nein, immer Captain (SP-10). |
| F3 | Nur innerhalb eines Projekts oder projektübergreifend? | Nur gleiches Projekt; Captain über HTTP projektübergreifend erlaubt (er sieht beide). |
| F4 | Prompt-Weg des Captains: nur über das Modell („schick das an Sitzung X“ → Werkzeug mit Karte) oder auch ein fester Befehl im Eingabefeld? | Nur über das Modell; der Befehl wäre ein zweiter Weg, am Gate zu prüfen. |
| F5 | Soll „Post wartet“ im Posteingang erscheinen? | Nein, nur Zähler in der Chat-Liste (SP-17); der Posteingang bleibt für Freigaben. |
| F6 | `antworten: true` beim Captain-Weg: Standard aus? | Ja, aus. |
| F7 | Zahlen `POST_MAX 4000`, `POST_PRO_STUNDE 10`, `POST_UNGELESEN_MAX 20`, `HOPS_MAX 2` ok? | Ja als Anfangswerte, nach Abnahme messen. |
| F8 | Bau durch Claude direkt (Regel V4: Spec+Tests+Referenz wären größer als der Code) oder als Bau-Spec für die lokalen Modelle? | Claude baut direkt, Logbuch-Zeile; keine Bau-Spec. |

## 8. Tests (Dateien, bei Bau)

`tests/test_harness_sitzungspost.py` (SP-01..06, 11..16), Ergänzungen in `tests/test_freigabe_vollstaendig.py` (SP-05/09), `tests/test_harness_herkunft.py` (SP-05), Verlauf/Export (SP-19), UI-Sichtprüfung (SP-07/17/18). Läufe: Gruppen aus `benchmarks/run_tests.py` (`harness`, `uix`, Freigabe), Exit-Code prüfen.

## 9. Stufen

1. Daten: `typ: post`, `POST …/post`, Grenzen, Audit, Verlaufsblock (SP-01..06, 11..16, 19).
2. Werkzeug mit Karte, Klasse N, Vorarbeiter-Regel (SP-09, 10) – **G4**.
3. Anzeige und Menü mit dem UIX-Koordinator (SP-07, 17, 18).
