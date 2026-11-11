# Konzept: Konsens-Bau (mehrere Läufe, ein Ergebnis)

Stand 11.11.2026, Entwurf. Anlass: Der Captain hat von einer Methode gelesen, bei der dieselbe Aufgabe mehrfach gelöst und aus den Ergebnissen das übereinstimmende, richtige herausgezogen wird: nicht einen Experten fragen, sondern fünf oder zehn. In der Literatur heißt das Self-Consistency (Mehrheit über Endantworten) und bei Code Best-of-N mit Verhaltensvergleich (Kandidaten laufen auf denselben Eingaben, gewählt wird das Verhalten, das die meisten teilen).

Nichts davon ist gebaut oder eingeschaltet. Der Prototyp `benchmarks/konsens.py` liest nur vorhandene Kandidaten und ändert keinen Lauf.

## 1. Die Idee in einem Satz

Ein Bau liefert mehrere Kandidaten für dieselbe Stufe; wir lassen alle auf denselben Eingaben laufen, nehmen bei jedem Fall die Antwort, auf die sich die Mehrheit einigt, und wählen den Kandidaten, der am wenigsten von dieser Mehrheit abweicht. Dazu kommt eine Liste der Streitfälle, bei denen die Kandidaten nicht einig sind.

Der Vorteil gegenüber unserem heutigen Differenztest: Er braucht keine Referenz und keine erwarteten Werte, nur Eingaben. Im echten Betrieb gibt es keine Referenz, im Vergleichslauf (`ab_bau.py`) schon.

## 2. Was Sedra schon hat

| Baustein | Wo | Rolle hier |
|---|---|---|
| Verhalten ausführen, Fehler und Mutation der Eingabe als Verhalten werten | `ab_bau._ruf` | Abdruck je Fall |
| Eingabenpool je Spec | `benchmarks/ab_diff/<spec>.py` (`faelle(ref)`) | Eingaben für den Vergleich, die Referenz wird dort nicht gebraucht |
| Kandidaten je Versuch | `runtime_data/devvm_candidates/<spec>/attempt_*` | die N Kandidaten |
| Mehrere Versuche je Stufe | `bau_schleife.stufe_bauen` | Einhängepunkt |
| Unterschiedliche Läufe (Seed, Anweisung an oder aus, Rezept) | `devvm_build.py`, `ab_bau.py` | Vielfalt der Kandidaten |

## 3. Entwurf

### 3.1 Eingaben
Der Vergleich braucht einen Pool von Eingaben je Funktion. Drei Quellen, in dieser Reihenfolge:
1. **Der Pool der Spec** (`ab_diff/<spec>.py`), sofern es einen gibt. Beste Qualität, weil von Hand auf Randfälle geschrieben.
2. **Beispielwerte aus der Signatur und den Tests der Spec**: die versteckten Tests nennen schon typische Eingaben; daraus Varianten bilden (leer, `None`, falscher Typ, doppelt, Unicode, Grenzwerte). Das ist die Checkliste aus `docs/CODER_PROFIL_UND_WORKFLOW_2026-11-11.md` Abschnitt 3 als Erzeuger.
3. **Ein Modellaufruf**, der Randfälle vorschlägt (nur Eingaben, keine Erwartung). Später, nur wenn 1 und 2 nicht reichen.

### 3.2 Abdruck und Mehrheit
- Abdruck eines Kandidaten = sein Verhalten auf jedem Fall (Ergebnis, Ausnahme mit Typ und Text, oder „hat die Eingabe verändert“).
- Je Fall zählt die Mehrheit. Gibt es bei einem Fall keine eindeutige Mehrheit (Gleichstand oder alle verschieden), ist es ein **Streitfall** und zählt nicht für die Wertung.
- Wertung eines Kandidaten = Zahl der Fälle mit Mehrheit, in denen er abweicht. Gewählt wird der Kandidat mit der kleinsten Zahl. Bei Gleichstand der früheste, das wird im Bericht genannt.
- Ausgabe: gewählter Kandidat, Wertung aller, Anteil einstimmiger Fälle, Liste der Streitfälle (höchstens 20, mit den Antworten).

Warum nicht „der Abdruck, der am häufigsten genau gleich vorkommt“: Bei unseren Specs haben die Läufe meist kleine, verschiedene Abweichungen. Genau gleiche Abdrücke sind selten, die Fallweise-Mehrheit ist robuster.

### 3.3 Streitfälle sind der eigentliche Gewinn
Auch wenn die Wahl nur so gut ist wie die Mehrheit: Die Streitfälle zeigen an, wo die Spec Raum lässt oder das Modell unsicher ist. Das ist eine fertige Prüfliste für die Durchsicht durch Claude oder den Captain (Regel: bestanden heißt nicht richtig) und ein Hinweis, die Spec an dieser Stelle zu schärfen.

### 3.4 Billigste Stufe: Übereinstimmung zweier Läufe
Schon N=2 ist nützlich als Alarm: Weichen zwei unabhängige Läufe auf dem Pool voneinander ab, ist die Stufe unsicher; stimmen sie überein, steigt das Vertrauen (nicht auf 100 %, siehe Grenzen). Erst bei Abweichung wird ein dritter und vierter Lauf gebaut. So zahlt man die volle Zeit nur dort, wo es Streit gibt.

## 4. Einhängen in die Schleife (später, nur mit Ja)
- Option `--konsens N` an `bau_schleife.py`, Standard **aus**, wie die Arbeitsanweisung.
- In `stufe_bauen`: nach bestandener Stufe N−1 weitere Kandidaten für dieselbe Stufe bauen, Wahl nach 3.2, Streitfälle in den Kurzbericht.
- Der gewählte Kandidat geht weiter, die anderen bleiben als Beleg im Kandidatenordner.
- Übernommen wird wie bisher nichts ohne Gate G4 des Captains.

## 5. Kosten
Ein Bau der kleinen Specs dauert 2 bis 3 Minuten, die GPU bedient einen Lauf nach dem anderen. N=5 kostet also etwa das Fünffache (rund 12 Minuten). Mit der Alarmstufe aus 3.4 meist nur das Doppelte. Der Vergleich der Kandidaten selbst ist reine CPU-Arbeit (Sekunden). Der Prompt wächst nicht.

## 6. Grenzen (ehrlich)
- **Gemeinsame Fehler bleiben.** Bei `am3_berechtigung` machten alle Läufe in allen Armen denselben Fehler (Tupel wie Liste behandelt). Die Mehrheit stimmt dann für den Fehler. Konsens filtert Zufallsfehler, keine Denkfehler des Modells. Dagegen hilft nur Vielfalt: anderes Rezept oder Modell, andere Formulierung der Aufgabe, Arbeitsanweisung an und aus, mit der Referenz im Vergleichslauf.
- **Die Eingaben begrenzen, was sichtbar wird.** Ein Unterschied, den kein Eingabenpool auslöst, bleibt unsichtbar.
- **Kein Ersatz für Durchsicht und Gate.** Der Konsens wählt aus, er beweist nichts.
- **Wirkt vor allem bei größeren Aufgaben**, wo mehr Raum für Zufallsfehler ist (Hinweis des Captains). Bei kleinen Specs streuen die Läufe wenig, der Gewinn ist dort klein.

## 7. Messplan
1. **Rückblick ohne GPU** (Prototyp): auf den vorhandenen Läufen je Arm prüfen, ob die Wahl nach 3.2 besser ist als der Durchschnitt der Läufe, gemessen an der Referenz (Differenzzahl). Daten: `am3_berechtigung` (je 5 Läufe in drei Armen) und `am0_shell_regeln` (je 5).
2. **Zufallsvergleich:** Wahl nach Konsens gegen eine zufällige Wahl unter denselben Kandidaten, alle Teilmengen der Größe 3 und 5.
3. **Nur wenn 1 und 2 positiv sind:** `--konsens` bauen und an einer größeren Aufgabe messen (Dauer, Fehler gegen Referenz, Streitfälle).

Entscheidungsregel vorab: Der Konsens lohnt sich, wenn die gewählten Kandidaten im Mittel mindestens ein Drittel weniger Abweichungen von der Referenz haben als ein zufällig gewählter und die Mehrkosten in Minuten vertretbar sind. Sonst bleibt es ein Werkzeug für die Streitfallliste.

### 7.1 Ergebnis des Rückblicks (11.11.2026, ohne GPU, auf vorhandenen Läufen)

Gemessen mit `konsens.py` an den Kandidaten der A/B-Läufe: Wahl nach Konsens gegen den Durchschnitt aller Kandidaten der Teilmenge (entspricht einer zufälligen Wahl). Maß: Abweichungen von der Referenz auf dem Eingabenpool.

| Spec | Kandidaten | N | Abweichungen gewählt | zufällig | weniger | sauberer Kandidat gewählt (zufällig) |
|---|---|---|---|---|---|---|
| `am3_berechtigung` (1044 Fälle) | 20, davon 10 ohne Abweichung | 3 | 1,9 | 3,1 | 38 % | 68 % (50 %) |
| `am3_berechtigung` | 20 | 5 | 1,3 | 3,1 | 58 % | 78 % (50 %) |
| `am0_shell_regeln` (8430 Fälle) | 10, keiner ohne Abweichung | 3 | 81,0 | 93,9 | 14 % | 0 % (0 %) |
| `am0_shell_regeln` | 10 | 5 | 78,2 | 93,9 | 17 % | 0 % (0 %) |

- **`am3_berechtigung`:** Hier streuen die Läufe zufällig (0, 2, 6 oder 12 Abweichungen). Der Konsens erfüllt die Entscheidungsregel aus Abschnitt 7 (mindestens ein Drittel weniger) schon bei N=3 und deutlich bei N=5.
- **`am0_shell_regeln`:** Acht von zehn Kandidaten machen denselben Fehler (Einträge in `dateien`, die keine Texte sind, lösen eine Ausnahme aus); drei weitere behandeln `entry: ()` als nicht gesetzt. Das ist systematisch, die Mehrheit stimmt dafür, der Konsens kann ihn nicht ausräumen. Er vermeidet nur die Ausreißer (146 und 168 Abweichungen) und liegt knapp unter der Regel. Das ist genau die Grenze aus Abschnitt 6.
- **Innerhalb eines Arms** (je 5 Läufe) wählt der Konsens in beiden Specs den häufigsten, besseren Kandidaten.
- **Vorsicht:** Zwei Specs, kleine Zahlen, die Teilmengen überlappen sich und sind nicht unabhängig. Das ist ein Hinweis, kein Beweis. Gemeinsame Fehler, die auch die Referenz teilt, sieht diese Messung nicht.
- **Folgerung:** Konsens lohnt sich dort, wo die Läufe zufällig streuen, und hilft nicht gegen einen Fehler, den das Modell immer macht. Für den zweiten Fall ist Wissen (Abschnitt 8.1) der Weg: ein Eintrag „Listenelemente, die keine Texte sind, ignorieren und keine Ausnahme werfen“ würde den Fehler in `am0_shell_regeln` beheben.

## 8. Andere Rollen: wo Konsens hilft und wie

Der Verhaltensvergleich aus Abschnitt 3 passt nur zu Code. Für Rollen, die Text liefern, gilt derselbe Gedanke, aber man stimmt über **ausgezogene Aussagen** ab, nicht über den Fließtext. Vier Arten:

| Art | Abgestimmt wird über | Passt zu Vorlage | Beispiel |
|---|---|---|---|
| **Verhalten** | Antworten auf gleichen Eingaben | `bauagent` (Coder) | Abschnitt 3 |
| **Befunde** | Schnittmenge: ein Befund zählt, wenn mindestens 2 von N Läufen ihn nennen | `pruefer`, `rueckblick` | N Durchsichten eines Kandidaten, nur gemeinsame Mängel werden gemeldet; die Einzelnen bleiben als „unsicher“. Das hebt die Treffsicherheit und kostet nur Zeit. |
| **Auswahl** | Entscheidung aus festem Satz (ja/nein, Rolle A oder B, Reihenfolge) | `manager`, `vorarbeiter` | Zerlegung in Teilaufträge und Zuteilung (`auftraege_verteilen`): N Vorschläge, die häufigste Zerlegung gilt, bei Streit geht es an den Captain |
| **Rückprobe** | Rückübersetzung stimmt mit dem Original überein | Übersetzer der Arbeitsanweisungen | N Übersetzungen, jede zurückübersetzt und per Strukturprüfung gemessen; gewählt wird die mit der treuesten Rückübersetzung (heute nur ein Versuch, drei bei Ablehnung) |

Für freie Texte (Chat, Zusammenfassung) gibt es „Universal Self-Consistency“: Ein weiterer Aufruf bekommt die N Antworten und wählt die konsistenteste. Das ist schwächer als die obigen Arten, weil dasselbe Modell urteilt; sinnvoll nur, wo es nichts Ausziehbares gibt.

**Vorlagenfeld (Vorschlag, noch nicht gebaut):** `konsens: {n: 3, art: verhalten|befunde|auswahl}` in `config/harness_vorlagen/<name>.yaml`, Standard aus, wie `arbeitsanweisung`. Der Hash der Vorlage nimmt es auf. Die Arbeitsanweisung und die Gesetze gelten für jeden der N Läufe unverändert; Konsens darf keine Werkzeuge oder Rechte erweitern.

### 8.1 Zusammenspiel mit der Wissensdatenbank

Die Schleife nutzt die Wissensdatenbank schon (`wissen_treffer`, `merke_fehler`, `merke_loesung`, Fingerabdruck der Fehler). Konsens und Wissen ergänzen sich, weil sie verschiedene Fehlerarten treffen: **Konsens gegen Zufallsfehler, Wissen gegen systematische Fehler** (die Lücke aus Abschnitt 6, in der alle Läufe denselben Fehler machen). Fünf Anknüpfungen:

1. **Streitfälle werden Wissen.** Entscheidet die Durchsicht oder die Referenz einen Streitfall, wird daraus ein Eintrag „Fall, uneinige Antworten, richtige Antwort“ im Muster der bestehenden Fehlerlösungen. Der nächste Bau einer ähnlichen Aufgabe bekommt ihn als Hinweis. So wird aus der teuren Mehrfach-Berechnung ein einmal bezahltes Wissen, und der Konsens braucht mit der Zeit weniger Läufe.
2. **Gemeinsame Fehler werden Muster.** Machen alle N Kandidaten denselben Fehler und fängt ihn die Durchsicht, ist das genau das, was die Mehrheit nicht sehen kann: ein Eintrag mit Fingerabdruck (wie `fingerabdruck_aus`) und der Lösung. Das ist der Weg, wie der Tupel-Fehler aus `am3_berechtigung` künftig verschwindet.
3. **Wissen als Quelle der Vielfalt.** Jeder der N Läufe bekommt andere Treffer (zum Beispiel Rang 1 bis 3 gegen 4 bis 6) oder eine andere Umformulierung der Suchfrage. Das macht die Fehler unabhängiger als bloßes Würfeln mit dem Seed. Gegenprobe: Widerspricht die Mehrheit einem bestätigten Wissenseintrag, wird das gemeldet.
4. **Abfragen selbst abstimmen.** Suche mit mehreren Umformulierungen der Frage und die Treffer vereinigen, die in mehreren Suchen vorkommen (Rangfusion). Antworten im Chat aus dem Wissen: nur Aussagen übernehmen, die in mindestens 2 von N Läufen mit derselben Quelle stehen. Das senkt erfundene Angaben.
5. **Vertrauensstufe im Wissen.** Ein Eintrag gilt als „bestätigt“, wenn er in mehreren unabhängigen Läufen oder durch Durchsicht bestätigt wurde, vorher als „Vorschlag“. Das ändert nichts an der Regel: **Wissen schreiben bleibt ein Antrag, den der Captain freigibt.** Konsens verbessert den Vorschlag, er schreibt nie selbst.

### 8.2 Reihenfolge nach Nutzen und Aufwand
1. **Befunde bei der Durchsicht** (`pruefer`): billig, kein neuer Eingabenpool, sofort nützlich gegen Fehlalarme.
2. **Coder mit Verhalten** (Prototyp `konsens.py`, Rückblick zuerst): Abschnitt 7.
3. **Streitfälle und gemeinsame Fehler als Wissen** (8.1 Nr. 1 und 2): hier entsteht der dauerhafte Gewinn. Setzt 2 voraus.
4. **Manager-Zerlegung** und **Übersetzer** (Auswahl und Rückprobe): erst wenn 1 bis 3 sich gelohnt haben.
5. **Wissensabfragen mit Rangfusion** (8.1 Nr. 4): klein, kann früh einzeln erprobt werden.

### 8.3 Kosten und Slots (zu messen, nichts davon geprüft)
Mit einem Slot laufen die N Läufe nacheinander. Die Profile mit mehreren Slots und der gemeinsame KV-Pool (`kv_unified`, Profil `bau-4x32k`, Team-Rezepte) würden mehrere Kandidaten gleichzeitig erlauben, jeder aber mit kleinerem Fenster und langsamer. Ob N parallele Läufe schneller fertig sind als N nacheinander, muss gemessen werden, bevor es in ein Profil kommt.

## 9. Offene Fragen
- Gewichtung: sollen Kandidaten mit weniger Nacharbeiten oder kürzerem Code bei Gleichstand bevorzugt werden?
- Ab welcher Aufgabengröße soll die Alarmstufe automatisch greifen?
- Wie viel Vielfalt (Seed, Rezept, Anweisung) bringt wirklich andere Fehler? Das lässt sich im Rückblick an den gemeinsamen Fehlern ablesen.
