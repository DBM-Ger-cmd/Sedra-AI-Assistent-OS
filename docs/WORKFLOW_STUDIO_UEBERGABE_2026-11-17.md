# SEDRA Workflow Studio – Übergabe vom 17.11.2026

## Aktueller Stand: Lokale Rechnungsprüfung, Revision 12

Der Workflow wurde auf Wunsch in **Lokale Rechnungsprüfung** umbenannt und verwendet ausschließlich den lokalen llama-Server. Der erfolgreiche echte Testlauf **M-986215C2** hat die vom Nutzer ausgewählte Datei `02_Eingangsrechnung_Steinbach.pdf` vollständig verarbeitet: **COMPLETE**, zwölf ausgeführte Schritte erfolgreich und ein Klärungszweig korrekt übersprungen. Alle **sechs Positionen** stimmen mit den vorhandenen Auftragstabellen überein (Positionssumme 56.336,66 EUR netto). Artefakt **ART-AB3EC2EE** ist die fertige HTML-Datei. Ergebnis und kompakter Nachweis liegen unter `E:\Sedra Umgebung\Vorführung Workflow Studio\Lokale Rechnungsprüfung`. Dieser Stand ersetzt für weitere lokale Vorführungen die früheren Hinweise auf Revision 9; die alten Revisionen bleiben erhalten.

Der neue Knoten **Datenschutz – Rechnungsdaten minimieren** steht vor dem Information Extractor. Er erzeugt dessen Eingabe aus einer festen Feldfreigabeliste: Rechnungsreferenz, Auftragsreferenz, Betrag und Datum. Personenbezogener Freitext, Adressen, Kontakt- und Bankdaten werden nicht in diese Modell-Eingabe übernommen. Die Originaldaten bleiben für den deterministischen Vergleich lokal erhalten. Das ist Datenminimierung und keine garantierte Anonymisierung; Referenzen können weiterhin identifizieren. Der Workflow bleibt daher ausdrücklich lokal, und der Inhaltsschutz ist weiter aktiv. Fehlende eindeutige Pflichtfelder führen zum Abbruch statt zu einer unkontrollierten Weitergabe.

Die ursprünglichen Tabellen **Auftraege** und **Auftragspositionen** enthalten die passenden Kursaufträge und werden nur gelesen. Ergebnisse schreibt dieser Workflow in die eigene Tabelle **LokalePruefergebnisse**. Die alten Demotabellen und gespeicherten Ergebnisse wurden nicht gelöscht.

Zwei technische Ursachen von `server_aus` wurden korrigiert: Der Starter erkannte Python-Aufrufe mit `-X utf8` nicht und ließ mehrere UIX-Instanzen parallel laufen. Die Erkennung berücksichtigt diese Option jetzt, sodass ein Neustart alte Instanzen tatsächlich ersetzt. Außerdem enthielt die automatische lokale Modellwahl auch ungeladene Router-Voreinstellungen. Sie berücksichtigt jetzt nur tatsächlich geladene bzw. schlafende Modelle, wenn der Router Statusangaben liefert. Das verhindert ein unbeabsichtigtes Laden des ersten Katalogmodells. Die parallelen alten Dienste wurden durch eine einzige Instanz ersetzt; das vorhandene Nemotron-Modell wurde über den regulären Scheduler angemeldet und wiederverwendet. Keine Sperre und kein Guard wurden deaktiviert.

Die sichtbare Fehlerdiagnose erklärt `SG_PERSONAL_CLOUD` jetzt am betroffenen Knoten und im Lauf. Ein zusätzlicher Fehler beim Modellwechsel wurde behoben: Die Auswahl ändert keine internen Knotennamen mehr, sodass Namensreferenzen und Verbindungen erhalten bleiben. Die sichtbare Modellbeschriftung folgt der tatsächlichen lokalen/Cloud-Auswahl.

Nachweise: 36 passende Python-Tests bestanden, einschließlich Starter mit UTF-8-Optionen, Modellwahl, Feldminimierung und strukturierter Extraktion. Der echte lokale Lauf mit der Steinbach-Rechnung ist abgeschlossen und wurde in Live & Debugger ausgewählt. Der Datenschutz-Fehlerzustand wurde zusätzlich im Browser mit simulierten Dienstantworten geprüft. Vorbereitung ist wiederholbar über `runtime/tools/prepare_local_invoice.py`; sie schreibt eine neue unveränderliche Revision und überschreibt keine alte Fassung.

## Stand und Einstieg

### Nachprüfung am 17.11., 08:19 Uhr

Ein tatsächlicher Browserdurchlauf im Benutzerprojekt wurde mit **Revision 9** abgeschlossen: PDF über den Kontext des Rechnungsknotens geladen, „Workflow starten“ gedrückt, vollständigen Lauf verfolgt und fertige HTML-Datei heruntergeladen. Lauf **M-86311DA5**, Artefakt **ART-442DDC70**. Elf Hauptschritte erfolgreich, Klärungszweig korrekt übersprungen. Zwei Positionen mit Status OK, zusammen 2.110,00 EUR netto. Der SHA256 des Downloads stimmt mit dem registrierten Bericht überein. Kopie und Ergebnisdaten: `E:\Sedra Umgebung\Vorführung Workflow Studio\Aktueller Test Revision 9`.

Dabei wurde ein echter Startfehler behoben: Nach dem Speichern einer Revision 10 blockierte der Startknopf die weiterhin geöffnete Revision 9 mit `workflow_revision_conflict`. Der Start liest jetzt genau die ausdrücklich angegebene unveränderliche Revision; Freigabe und Workflow-/Eingabe-Digest bleiben an diese Fassung gebunden. Im Eigenschaftenfenster öffnet **Revision zum Test öffnen** eine ältere gespeicherte Fassung, ohne sie als neue Revision zu speichern oder die neueste Fassung zu ersetzen. Der Regressionstest startet eine ältere Fassung nach dem Speichern einer abweichenden neueren Fassung und prüft den gebundenen Inhalt.

Die neue Ansicht **Logischer Ablauf** ordnet den Hauptweg von links nach rechts an, trennt Ja-/Nein-Zweige und stellt das Modell als gestrichelte Zulieferung unmittelbar unter dem Extraktor dar. Die Rechnungsprüfung hat damit keine rückwärts über den gesamten Graphen laufenden Leitungen mehr. Die Ansicht ist eine reine Leseprojektion: Revisionen, fachliche Verbindungen und Parameter werden dadurch nicht geändert. Für manuelles Verschieben bleibt **Gesamtprozess** verfügbar; Knoteneinstellungen sind per Rechtsklick erreichbar. Live verwendet die logische Projektion automatisch. Die Zeichenfläche wurde in der Höhe begrenzt, der Inspektor erscheint erst bei Knotenauswahl.

Verifikation nach der Änderung: 20 Rechnungs-/Starttests bestanden; 56 Layout-/Vertrags-/Showcase-Tests bestanden, davon 16 wegen fehlender Testvoraussetzungen übersprungen; 18 bestehende JavaScript-Tests und ein zusätzlicher Test für die unveränderliche logische Projektion bestanden. Der Browserdurchlauf Quelle bis HTML-Download wurde zusätzlich mit simulierten Dienstantworten geprüft. Die tatsächliche Modellinferenz im oben genannten Lauf lief über NVIDIA. Die Browseranzeige der lokalen HTML-Datei wurde durch die Protokollrichtlinie blockiert; die Datei selbst wurde erfolgreich heruntergeladen und anhand ihrer Prüfsumme geprüft.

Arbeitsstand: `codex/studio-bedienung-20261117` im Projekt **A1 Sedra Main Branch Entwicklungs umgebung**. Die Änderungen sind lokal vorbereitet, nicht in den Hauptzweig übernommen. Andere vorhandene Änderungen im Projekt wurden nicht zurückgesetzt.

**Vor der Vorführung SEDRA vollständig neu starten, einschließlich des Hintergrunddienstes.** Ein reines Neuladen der Oberfläche lädt die geänderten Python-Dienste nicht neu. Eigene ungespeicherte Arbeit vorher speichern. Danach im Workflow-Katalog **Rechnungsprüfung mit Claude, Revision 9** öffnen. Ein bereits offener alter Entwurf wechselt nicht automatisch auf die neue Revision.

Die fertigen Vorführdateien liegen unter `E:\Sedra Umgebung\Vorführung Workflow Studio`. `START_HIER.txt` enthält die kurze Bedienfolge.

## Einheitliches Bedienkonzept

Nachbesserung um 08:36 Uhr: **Workflow starten** sitzt dauerhaft in einer festen Aktionsleiste oben, auch in Live & Debugger und im Startassistenten. Fehlt eine PDF oder gibt es ungespeicherte Änderungen, zeigt die Leiste den Grund und die passende Aktion (PDF hinzufügen / Änderungen speichern). Nicht ausführbare Prozessentwürfe behalten einen sichtbaren, deaktivierten Startknopf mit Erklärung und Einstieg in die Einrichtung. Beim Start aus Live wird zuerst der erhaltene Editorentwurf wiederhergestellt, damit eine historische Laufansicht keine ungespeicherte Arbeit verdeckt ersetzt. „Rechnungsprüfung mit Claude“, Revision 9, wurde im Browser erneut geöffnet und mit `Testrechnung.pdf` startbereit hinterlassen; der sichtbare Startknopf war aktiviert. Browser-Regressionsprüfung von PDF bis HTML einschließlich Sichtbarkeit des Knopfs in Bearbeiten und Live erfolgreich; 17 Studio-/Harness-Tests bestanden.

Nachbesserung vom 17.11., nach Sichtung der Screenshots 07:37: Die Startansicht der Arbeitsfläche ist jetzt in **Einstieg** und **Zuletzt gespeichert** aufgeteilt. Es ist jeweils nur ein Abschnitt sichtbar. Import und KI-Entwurf öffnen sich bei Bedarf. Die gespeicherten Workflows nutzen die verfügbare Breite, sind durchsuchbar und werden in Seiten zu sechs Einträgen angezeigt. Die Suche durchsucht weiterhin den gesamten Bestand. Auf schmalen Flächen bleibt die Modusleiste horizontal bedienbar, statt den Einstieg nach unten zu verdrängen. Die Oberflächenänderung benötigt nur ein Neuladen, keinen erneuten Dienststart.

Geprüft: zwei getrennte Ansichten, Import öffnen/schließen, KI-Entwurf aufklappen, Suche einschließlich leerer Trefferliste, Blättern bei 18 Workflows, Tastaturwechsel und Layouts bei 1800/1280/768/390 Pixeln ohne Seitenüberlauf. Prüfung mit den echten Oberflächenmodulen und simulierten Dienstantworten; zusätzlich weiterhin erfolgreicher Browserdurchlauf von Quelle bis HTML-Download und 17 Studio-/Harness-Tests. Prüfbilder: `scratch/studio-vorschau/einstieg-*.png` und `gespeichert-*.png`; aktuelle Quellenprüfsummen: `scratch/studio-vorschau/pruefbericht-startansicht.json` (jeweils unter `E:\Sedra Umgebung`).

- Ein Einstieg **SEDRA Workflow Studio**. Alte Workflow-/n8n-/Szenario-Einstiege führen in dieselbe App; Menü und zuletzt benutzte Apps werden zusammengeführt.
- Eine **Arbeitsfläche** mit den Modi **Bearbeiten**, **Startassistent** und **Live & Debugger**. Der Live-Modus verwendet denselben Canvas und ist schreibgeschützt. Beim Wechsel zurück wird der Entwurf wiederhergestellt.
- Der Katalog bietet Suche, Bearbeiten und Start vorbereiten. Der Startassistent bezieht sich auf den gerade geöffneten Workflow, statt eine unabhängige allgemeine Auswahl zu zeigen.
- Rechtsklick auf einen Knoten öffnet passende Aktionen: Chat, Rechnung/PDF als Quelle, Extraktionsquelle mit Feldzuordnung, lokale/NVIDIA-Modellwahl, Tabelle oder Ausgabe-Unterordner. Technische Eigenschaften bleiben bei Bedarf erreichbar. Die Kontextaktionen sind auch über die Tastatur zugänglich.
- Quelle, Workflow-Modell und Ausgabe sind an der Arbeitsfläche zusammengefasst. Start, Freigabe, Laufstatus und Ergebnis gehören zum selben Ablauf.
- Live-Daten stammen aus dem tatsächlichen Lauf. Die ausdrücklich beschriftete Funktion **Gespeicherten Ablauf nachvollziehen** spielt vorhandene Ergebnisse ab; sie führt den Workflow nicht nochmals aus.
- Größere Schrift und Bedienelemente, sichtbare Tastaturfokusse, bessere Abstände und Anpassung an schmale Ansichten folgen dem dunklen SEDRA-Design. Auch der Factory-Leerzustand und doppelte Projektaktionen wurden bereinigt.

## Rechnungsprozess und Daten

Revision 9 enthält den verbundenen Ablauf:

1. Rechnungs-PDF hochladen.
2. PDF-Text lesen und vorbereiten.
3. Information Extractor mit dem ausgewählten Modell ausführen.
4. Rechnungspositionen auslesen.
5. Auftragsdaten und Auftragspositionen aus Tabellen lesen.
6. Rechnung mit Auftrag vergleichen.
7. Ergebnis verzweigen: Kostenübersicht oder Klärung erforderlich.
8. **HTML-Dashboard als Datei ausgeben** – ausdrücklich als letzter Prozessschritt gespeichert.

Der zuvor abseits stehende Information Extractor ist in den Hauptpfad eingebunden. Der sichtbare Modellknoten repräsentiert die gespeicherte Modellwahl; ein alter Anthropic-Schlüsselverweis wird hierfür nicht benötigt.

Die vorbereitete Revision verwendet getrennte, synthetische Vorführtabellen: **Demo Auftraege**, **Demo Auftragspositionen** und **Demo Kostenuebersicht**. Die bestehenden fachlichen Tabellen wurden bei der Vorbereitung nicht überschrieben. Die Demo enthält einen Auftrag mit zwei passenden Rechnungspositionen über zusammen **2.110,00 EUR netto**. Die HTML-Datei kennzeichnet diese Daten als Testdaten.

Revisionen 6–8 ergänzen schrittweise Extraktorverbindung, Bericht und Modellträger; Revision 9 ergänzt den getrennten Demodatensatz und die geprüfte NVIDIA-Auswahl. Vorherige gespeicherte Revisionen bleiben erhalten.

## Fertige HTML-Datei

Der Lauf erzeugt und registriert `rechnung-dashboard.html` als fertiges Artefakt. Der Download liest die tatsächlich gespeicherte Datei und prüft Pfad und Prüfsumme; er erzeugt keine nachträgliche Ersatzansicht.

Das Dashboard ist eigenständig und benötigt keine externen Bibliotheken oder Verbindung zu SEDRA. Es bietet Kennzahlen, Prüfstatus, Positionssuche, Filter, Sortierung, CSV der sichtbaren Zeilen, vollständigen JSON-Export und Druck/PDF. Fehlende Beträge werden nicht als Null ausgegeben. Technischer Laufabschluss und fachliche Abweichungen werden getrennt dargestellt; Daten und Modellherkunft bleiben nachvollziehbar.

Ein optionaler Ausgabe-Unterordner liegt innerhalb des geschützten Laufverzeichnisses. Beliebige externe Zielpfade werden nicht zugelassen. Die fertige Datei lässt sich anschließend über den Download an einem gewünschten Ort speichern.

Bereits erzeugte Dateien:

- `E:\Sedra Umgebung\Vorführung Workflow Studio\NVIDIA\rechnung-dashboard.html`
- `E:\Sedra Umgebung\Vorführung Workflow Studio\Lokal\rechnung-dashboard.html`

Beide Ordner enthalten außerdem `Testrechnung.pdf` und `pruefergebnis.json` mit den tatsächlichen Laufdaten.

## Modelle für Workflow und Chats

Der Workflow speichert seine eigene Modellwahl: lokaler llama-Server oder NVIDIA. Revision 9 ist auf **nvidia/nemotron-3.5-bolt-e4b** eingestellt. Eine NVIDIA-Ausführung sendet die benötigten Inhalte an diesen Anbieter; die Laufvorlage weist vor der Freigabe darauf hin. Es gibt keinen stillen Wechsel zwischen Cloud und lokalem Modell.

Jeder Chat kann unabhängig einen Anbieter und ein Modell speichern. Beim Chatwechsel wird dessen Auswahl wieder angezeigt. NVIDIA-Chats benötigen kein geladenes lokales Modell. Ein explizit gewähltes, nicht geladenes lokales Modell wird als nicht verfügbar gemeldet, statt ein anderes zu verwenden. Die globale lokale Modellverwaltung steuert weiterhin das Laden auf der Hardware; die Chat-Auswahl ist davon getrennt.

Die vorhandene NVIDIA-Konfiguration wurde verwendet. Zugangsschlüssel werden weder in Workflow-Dateien noch in der Dokumentation oder den Prüfergebnissen abgelegt.

## Prüfung und Ergebnisse

### Tatsächliche Modellläufe

Die vollständigen Tests liefen in getrennten temporären Projekten mit echter Modellinferenz, PDF-Eingabe, Tabellenabgleich, Freigabe und registrierter HTML-Ausgabe. Bestehende Nutzerdaten und Chats wurden dafür nicht geändert.

| Test | Modell | Ergebnis | Nachweis |
| --- | --- | --- | --- |
| Lokal, Vorlage Revision 8 | nemotron-3.5-bolt-e4b | COMPLETE / completed, HTML erzeugt | Lauf M-B2500244, Artefakt ART-790D9DA6 |
| NVIDIA, finale Vorlage Revision 9 | nvidia/nemotron-3.5-bolt-e4b | COMPLETE / completed, HTML erzeugt | Lauf M-AF7965BA, Artefakt ART-D1F8E6DF |
| Chat lokal | nemotron-3.5-bolt-e4b | Tatsächliche Antwort OK | Getrennte Testsitzung |
| Chat NVIDIA | nvidia/nemotron-3.5-bolt-e4b | Tatsächliche Antwort OK, ohne geladenes lokales Modell | Getrennte Testsitzung |

Im erfolgreichen NVIDIA-Lauf liefen alle elf Hauptknoten; der nicht gewählte Klärungszweig wurde korrekt übersprungen. Die zwei Positionen stimmen mit dem Auftrag überein. Die Testlauf-IDs gehören zu den isolierten Prüfprojekten, nicht zur Laufhistorie des geöffneten Benutzerprojekts.

### Automatisierte und visuelle Prüfung

- 121 Python-Tests: erfolgreich, zwei übersprungen. Geprüft wurden Bericht, Fehlerszenarien, Dateidownload, Modellrouting, getrennte Chat-Auswahl, Cloud-Adapter, Harness und Studio-Verbindungen.
- 18 JavaScript-Tests: erfolgreich. Unter anderem einheitliche App-Einstiege, Workflow-Metadaten, Verbindungen und Editorfunktionen.
- Browserprüfung der echten Oberflächenmodule mit simulierten Dienstantworten und gespeicherter Revision 9: Quelle hinzufügen, Extraktionsquelle, Speichern, Start, eine gemeinsame Zeichenfläche, kontextbezogener Assistent und HTML-Download. Ansichten mit 1800, 768 und 390 Pixeln ohne seitlichen Seitenüberlauf; keine Browserfehler.
- Beide tatsächlich erzeugten HTML-Dateien im Browser geöffnet: Suche, Filter, Sortierung, CSV- und JSON-Download sowie Testdatenkennzeichnung erfolgreich geprüft.
- Die Browserprüfung mit simulierten Antworten ersetzt keinen vollständigen Klicktest im neu gestarteten Desktop. Die tatsächliche Ausführung wurde separat über die realen Dienste und Modelle geprüft.

Prüfbilder und eine Prüfliste mit SHA256 der Quellen liegen unter `E:\Sedra Umgebung\scratch\studio-vorschau\pruefbericht.json`.

Wiederholbare Befehle aus dem Projektordner, mit dem verfügbaren Python und `PYTHONPATH=runtime/src;runtime/tests;runtime/.venv/Lib/site-packages`:

```text
python -m unittest test_workflow_showcase test_cloud_api test_model_structured test_uix_workflow_studio_app test_uix_harness_shell test_uix_harness_start test_harness_sitzung test_uix_harness_api test_uix_factory_studio_app -q
node --test runtime/tests/n8n_model.test.cjs runtime/tests/workflow_studio_unified.test.cjs runtime/tests/workflow_ui.test.cjs
```

Vorbereitungs- und Prüfwerkzeuge liegen unter `runtime/tools/prepare_invoice_showcase.py`, `runtime/tools/prepare_invoice_demo_data.py` und `runtime/tools/run_invoice_showcase.py`. Vor erneutem Aufruf deren Hilfe bzw. Zielparameter prüfen; der echte Modelltest nutzt den konfigurierten Anbieter.

## Grenzen und Hinweise für die Vorführung

- **google/gemma-4-31b-it** antwortete im API-Test nicht innerhalb des Zeitlimits. Für die Vorführung wurde deshalb das erfolgreich geprüfte NVIDIA-Nemotron-Modell gespeichert. Andere Katalogmodelle sind nicht pauschal als geprüft anzusehen.
- Die Modellwahl ändert keine Hardwarebelegung automatisch. Vor lokaler Ausführung das passende lokale Modell laden.
- Die Vorführrechnung ist ein textbasiertes PDF. Beliebige gescannte Rechnungen, andere Layouts und produktive Buchhaltungsdaten sind nicht durch diesen Test abgedeckt.
- Detailvorschauen zeigen die gespeicherten Laufdaten; nicht für jeden beliebigen Knotentyp steht die vollständige Eingabe zur Verfügung. Eine Animation ist kein zusätzlicher Ausführungsnachweis.
- Der Start benötigt weiterhin die vorhandene ausdrückliche Lauf-Freigabe. Notaus bleibt wirksam.
- Die Änderungen müssen nach dem Neustart im Benutzerprojekt sichtbar sein; eine bereits geöffnete alte Revision oder ein alter Entwurf ist kein Nachweis für den neuen Stand.
