# Baubericht: Wissen im Kern, K1 und K2 (05.11.2026)

Bau G3-1 bis G3-5 zu `docs/SPEC_WISSEN_KERN_v1.md` (G1 freigegeben 14:01) und `docs/SPEC_WISSEN_KERN_v1_G2_K1K2.md` (G2 freigegeben 14:15).
Basis `main` `d51083a`. Kein Commit (Captain 14:40: Übergabe als ZIP, Einspielen nach `main` durch den Captain).

## 1. Ergebnis

| Schritt | Inhalt | Dateien |
|---|---|---|
| G3-1 Kerndienst | `wissen.dienst`: `fragen`, `block`, `systemsatz`, `nachbereiten`, `route_aus_anbieter`. `wissen/lauf.py` ist nur noch ein dünner Anschluss daran (gleiches Verhalten). | `wissen/dienst.py` (neu), `wissen/lauf.py` |
| G3-2 Standard an, Grundfunktion | Schalter `wissen` ist ohne Eintrag **an**. Abschalten nur mit `wissen: {enabled: false}`. `wissen` steht in `GRUND_START` (Server und Client). Alte Zuschnitte, die Wissen ausblendeten, werden beim Laden still bereinigt statt verworfen. Das Testlabor wird erst geöffnet, wenn `testlab.db` existiert (`VerzoegertesLabor`), sonst legte der Start die Datei an. | `runtime.py`, `config/wissen.yaml`, `local_switches.py`, `harness/desktop.py`, `uix/shells/harness/desktop.js`, `wissen/embed.py`, Vorlage `desktop-designer.md`, README |
| G3-3 Werkzeuge | `wissen_suchen` (frei, Leser Captain Stufe 6, Route lokal, Filter quelle/art/seit, k ≤ 10, Auszug 600 Zeichen, Grenze `lese_grenze`) und `wissen_beantragen` (nur Antrag `request:wissen_quelle`, nur `projekt`/`repo`, doppelt erkannt). `gateway_status`, `gateway_vorgang`, `gateway_regel` lesbar über das Zustandswerkzeug (Schema bekommt `id` und `frage`). | `harness/werkzeuge.py`, `harness/katalog.py` (`OHNE_KARTE`), `harness/api.py` (`LESEN`, `wissen_werkzeug`, `wissen_antrag`), `harness/freigabe.py` |
| G3-4 Zug | Option `wissen_zuerst` (an/aus, Vorgabe an), je Sitzung über `PATCH sitzungen {wissen_zuerst}`. Fester Systemsatz in jedem Zug. Block mit der Frage in **einer** Nachricht (manche Chat-Vorlagen verlangen den Rollenwechsel). Im Verlauf später nur `[Wissen dazu: W…]` (Möglichkeit C). Zitatprüfung ohne Textänderung: `wissen: {ids, belegt, fremd, hinweis}` am Antwort-Eintrag und im `ende`-Ereignis, Audit `WIS_ZITAT_FREMD`/`WIS_ZITAT_FEHLT`. Ohne Modell: Trefferliste (`wissen_antwort`), in der Sitzung als Eintrag `wissen`. | `harness/api.py`, `harness/schleife.py`, `harness/sitzung.py` |
| G3-5 Anzeige | Zeile „▣ Aus dem Wissen: n Fundstellen“ unter der Antwort (Kennungen, genannte grün, fremde gelb markiert, Hinweis, „Im Wissen öffnen“ → App Wissen · Suche). Block ohne Modell. Schalter „Wissen zuerst“ in den Gesprächsoptionen unter dem Schild. Eine bestehende Sitzung sendet auch ohne geladenes Modell (sonst käme WK-15 nie an). | `uix/shells/harness/zeilen.js`, `verlauf.js` (399 Zeilen), `gespraechsoptionen.js`, `shell.css` |

## 2. Tests

Neu: `test_wissen_dienst.py`, `test_harness_wissen.py`, `test_harness_wissen_zug.py` (mit **Präfix-Test**), `test_uix_harness_wissen.py`.
Angepasst: `test_wissen_desk.py` (ohne Eintrag an), `test_harness_desktop.py`, `test_uix_harness_desktop.py` (Wissen ist Grundfunktion, alter Zuschnitt), `test_desk_decisions.py` (Schnappschuss enthält `wissen`), `test_harness_optionen.py` (Option `wissen_zuerst`).

| Lauf | Ergebnis |
|---|---|
| alle Wissenstests | 151 + neue, grün |
| `run_tests.py harness uix desk orchestra` nach G3-4 | 1522 Tests, 2 rot → beide behoben (Optionenliste; `verlauf.js` lag zwischendurch bei 404 Zeilen) |
| `test_freigabe_vollstaendig` | grün, keine neue Route der Harness |
| Gesamtlauf `run_tests.py all` | siehe §5 |
| Browser an eigener Testinstanz (Modell-Attrappe, 1400×860) | Frage → Antwort mit `[W…]` → Zeile „1 Fundstelle · 1 Kennung nicht aus dem Wissen“ → „Im Wissen öffnen“ öffnet „Wissen · Suche“; Schalter steht auf „an“; 0 Konsolenfehler |

**Präfix-Test (§3.4a, ohne GPU):** Drei Züge (mit, ohne, mit Treffern). Der Systemprompt ist in allen gleich. Jeder Zug beginnt genau wie der vorige bis vor dessen Frage. Damit rechnet der Cache durch das Wissen nur die vorige Frage neu, wie in §3.4a erwartet. Am echten Sedra bestätigt die Cache-Zahl das, noch ungemessen.

## 3. Abweichungen vom G2

1. **Schild-Zeichen je Sitzung** (G2 §3.4 „▣ Wissen“ am Schild): nicht gebaut. Der Schalter steht global in den Gesprächsoptionen; je Sitzung geht es über `PATCH sitzungen`. Grund: `eingabe.js` kennt den Sitzungsstand nicht ohne einen weiteren Abruf. Vorschlag: kommt mit U13 (App-Rahmen).
2. **„Im Wissen öffnen“** öffnet die Suche, nicht den einzelnen Abschnitt. Die App Wissen nimmt eine Abschnitts-Kennung heute nicht an. Gehört zu K3 (App Wissen).
3. **Zitatprüfung** hängt nichts an den Text an (`lauf.nachbereite` tut das bei Agenten). Begründung: Der Text bleibt so, wie das Modell ihn schrieb. Das hält den Verlauf und den Cache stabil; die Prüfung steht in der Zeile darunter.
4. **Leser** in allen Harness-Sitzungen ist der Captain (D2), auch in Vorarbeiter-Sitzungen. Die Stufe je Vorlage kommt mit K5 bzw. den Rollen (U6).
5. Bleibt eine Antwort bei `wartet` stehen (Karte), bleiben ihre Kennungen aus `wissen_suchen` im Speicher, bis die Antwort endet. Das ist klein; eine Fortsetzung mit neuer Antwort-ID verliert sie.

## 4. Für das Einspielen nach `main`

- Wirkung auf bestehende Installationen (D3): Das Wissen ist nach dem Update an. Ohne `local_config/wissen.yaml` läuft nur die Volltextsuche. Freigegebene Quellen werden alle 600 s abgeglichen; ohne freigegebene Quelle tut der Takt nichts.
- Danach im echten Sedra (Strg+F5): eine Frage, zu der es eine freigegebene Quelle gibt → Zeile „Aus dem Wissen“; Cache-Zahl über drei Züge beobachten; im Posteingang prüfen, dass `wissen_beantragen` einen Antrag anlegt.

## 5. Gesamtlauf

- `run_tests.py all` (Linux-Testumgebung, Python 3.13): **4037 Tests, 0 rot, 80 übersprungen**, 1131 s. 16 Dateien brechen beim Import ab (DevVM, Skill-Library u. a., fehlende Abhängigkeiten); das war schon vor dem Bau so.
- Danach (Nachtrag L3 und U10-Test): `run_tests.py harness desk` 959 Tests, 0 rot; `test_freigabe_vollstaendig` und `test_harness_werkzeug_vollstaendig` grün.
- Nicht unter Windows gelaufen; dort einmal `python benchmarks/run_tests.py harness uix desk` und `test_freigabe_vollstaendig` nach dem Einspielen.

## 6. Nachtrag aus U10 (Werkzeug-Lücken)

- **L3 behoben:** `harness/freigabe.py` schrieb für jedes Werkzeug aus `OHNE_KARTE`, das nicht in einer festen Liste stand, `HARNESS_PROJEKT_BEANTRAGT` mit dem Ziel ins Audit. Für `wissen_suchen` wäre das der Fragetext gewesen (gegen WK-06). Beide Wissenswerkzeuge stehen jetzt in der Liste; Test `test_kein_fragetext_im_audit_der_harness`.
- L1 (stille Default-Zweige in `vorbereiten`) betrifft die neuen Werkzeuge nicht, beide haben eigene Zweige. Der Test `test_harness_werkzeug_vollstaendig` aus U10 prüft das künftig für jedes Werkzeug.
