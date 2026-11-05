# Abnahme Prozess-Apps / Update-Kandidat 1.22.2

05.11.2026, Basis d51083a, isolierte verknüpfte Arbeitskopie des Projekts auf E:.
Kein Einspielen in die laufende Installation, kein Push, kein Tag, keine GPU.

## Ausgeführt

- Gemeinsame gezielte Python-Abnahme: **236 Tests, OK, 1 übersprungen**.
  Neue Interchange-, Engine-, Missions-, Update- und Browser-Tests; vorhandene
  Workflow-Verträge, Freigabevollständigkeit, UI-Vertrag, Desk-Gateway/-Kinds/
  -Gated/-Modules/-Decisions, Kernabgrenzung, Update-Anwenden/-Holen/-Suche.
- JavaScript-Editorlogik: **8 Tests, 8 bestanden** (Node test runner).
- Headless Microsoft Edge, echte One-Sedra-Testinstanz im temporären Projekt:
  App laden, Knoten umbenennen, Undo, Knoten ergänzen, Undo, drei Revisionen,
  frühere Revision laden, unbekannten Knoten importieren, JSON exportieren und
  mit Original vergleichen, Kompatibilität prüfen; 1400 und 1024 Pixel Breite.
- Screenshot der echten Test-App erstellt. Kein Modell und keine Live-Daten.
- Zwei eigenständige Apps im echten Browser: gemeinsame Speicherung und
  Versionshistorie, unterschiedliche Kataloge und Konfigurationsformulare;
  Wiederöffnung und Rückkehr zur aktuellsten gespeicherten Revision.
- Prozessversionen: Änderungsgrund, Vorher/Nachher, Integritätskette,
  Abwärtskompatibilität vorhandener Revisionen und Ablehnung manipulierter Daten.
  Prozessmodelle bleiben auch nach Entfernen von disabled nicht ausführbar.
- Externe Kursvorlagen nur als Testeingabe: Ausgangsfassung importiert, Ergänzung
  als zweite Revision gespeichert, JSON-Rundlauf geprüft, beide Apps gerendert.
  Screenshots visuell kontrolliert. Keine Kursfälle im generischen Update-Paket.
- Git diff --check ohne Befund.

Der übersprungene Test ist test_binding_rejects_symlink: Windows verweigert das
Anlegen des Test-Symlinks mit WinError 1314. Er wurde nicht als bestanden gezählt.

Ein zunächst fehlgeschlagener CommonJS-Test entstand durch die übergeordnete
package.json im Benutzerverzeichnis. Die neue private package.json am Repository-
Root legt den bestehenden CommonJS-Modultests eine eindeutige Umgebung fest;
der gemeinsame Endlauf besteht. Kein fremdes Projekt wurde dafür verändert.
Beim Ausbau musste der Browsertest zusätzlich auf die abgeschlossene App-
Initialisierung warten; danach wurde der gemeinsame Endlauf erneut ausgeführt.

## Paketprüfung

package_n8n_update.py baut einen vollständigen, unveröffentlichten Kandidaten
einschließlich release/MANIFEST.sha256 und Basis-Prüfsummen. Anschließend prüft
verify_n8n_update.py das fertige ZIP mit dem eigenständigen Offline-Installer:
Vorschau unverändert, falsche Bestätigung abgewiesen, Installation in temporärer
Kopie, lokale Pfade/Sicherungen/Konfigurationen/Daten erhalten, Rücknahme stellt
den ursprünglichen Programmstand wieder her. Maschinenlesbarer Bericht liegt
neben dem ausgelieferten ZIP. Die neun Paketprüfungen sind mit **PASS** beendet:
Manifestintegrität, reine Vorschau, falsche Bestätigung abweisen, Offline-Übernahme,
lokale Daten erhalten, vollständige Rücknahme und Datenerhalt nach Rücknahme;
zusätzlich Übernahme vom geprüften 1.22.1-Kandidaten und Rücknahme auf diesen.

## Grenzen

Die n8n-Protokolltests verwenden kontrollierte Testdoppel. Es war keine echte
n8n-Engine installiert/angebunden; keine vollständige Live-Versionskompatibilität
bestätigt. Vor dem ersten realen Lauf ist eine dedizierte lokale n8n-Testinstanz
mit dokumentierter Version erforderlich. Bis dahin bleibt n8n standardmäßig aus.
Die gesamte historische SEDRA-Suite und reale GPU-/Modellläufe wurden nicht
ausgeführt. Das Paket ist ein Review-Kandidat, keine öffentliche Veröffentlichung.
Szenario Studio ist eine eigene Oberfläche, keine Live-Anbindung an Make.
