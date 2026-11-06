# SEDRA Prozess-Apps - Update-Kandidat 1.22.2, Apps 0.2.0

Stand 05.11.2026. Nicht veröffentlicht, nicht in die laufende Installation übernommen.
Basis: d51083aa16d573c59be276dc407cbd59468a9fa4 (SEDRA 1.22.0).
Zusätzlich akzeptiert das Paket den exakt geprüften vorherigen Update-Kandidaten
1.22.1. Andere Programmstände werden nicht automatisch überschrieben.

## Enthalten

Zwei eigenständige Apps im Startmenü von One Sedra, Gruppe Arbeit:

- **n8n Workflows:** rechteckige Knoten, Knotenkatalog, technische Parameter,
  n8n-JSON-Import/Export und JSON-Ausgabe der Läufe.
- **Szenario Studio:** runde Module, eigener Modulkatalog, Feldzuordnung über
  Formular, Router mit zwei gefilterten Wegen, Routen und Bündelübersicht aus der
  tatsächlich empfangenen Engine-Antwort. Keine simulierten Ergebnisse.

Die Apps unterscheiden sich in Inhalt und Bedienung, teilen aber eine Basis:
Prozessdaten, Ein-/Ausgabeverträge, Schema, Revisionen, Missionsausführung, Guard,
Audit und gemeinsame UI-Bausteine. Kein Querimport zwischen Apps. Jede geöffnete
Editorinstanz hat ihren eigenen Entwurf; veraltete Stände können neue Versionen
nicht überschreiben. Wechsel über den Knopf der jeweils anderen App nach Speichern.

Szenario Studio ist eine eigene, von Make inspirierte Oberfläche, kein eingebettetes
Make und kein Make-Client. Keine Make-Blueprints, Cloud-Verbindung, Kontosynchronisation
oder vollständige Nachbildung seiner Module. Beide Apps verwenden den bestehenden
n8n-Austauschadapter; die eigene Oberfläche erteilt keinerlei Ausführungsrechte.

Gemeinsam: importierte unbekannte Felder/Knoten erhalten, Zeichnen/Verbinden,
Undo/Redo, Original-/bereinigter Export, SIPOC, vollständiger Prozessgraph,
verdichtete Kernübersicht und Detailtabelle. Zoom, Verschieben des Canvas und
Fokus auf Auswahl. Prozessangaben je Schritt: Rolle und Rollenstatus, Lieferant,
Input, Output, Empfänger, Nachweis, Abschlusskriterium, Ausnahme, Hypothese und
Automatisierungsbegründung; Board-Angaben und Vorschläge bleiben unterscheidbar.

Ein Prozessmodell ist ausdrücklich nicht ausführbar. Beschriebene menschliche
Schritte oder Freigaben werden niemals als technische noOp-Freigaben interpretiert.
Die Kernübersicht fasst Zwischenwege zusammen und verändert den Originalgraph nicht.
Die Modellvorlagen des Kursprojekts liegen separat und sind kein Update-Bestandteil.

## Prozessversionen

Jedes Speichern erzeugt eine unveränderliche Revision mit UTC-Zeit und Änderungsgrund.
Bei Änderungen eines Prozessmodells ist ein Grund Pflicht. Die Historie zeigt
Änderungsumfang und einen Vorher/Nachher-Vergleich, auch für Rollen und Verbindungen.
Alte Version als Entwurf laden und neu speichern; kein stilles Zurücksetzen.
Mit **Als neue Version importieren** wird eine überarbeitete externe Datei in den
aktuellen Prozess übernommen, ohne dessen Versionsfolge zu verlieren.

Neue Revisionen besitzen einen eigenen Hash und die Hashbindung zum Vorgänger;
Änderungsereignisse werden im vorhandenen Audit protokolliert. Altbestände ohne
Versionsnotiz können unverändert weitergelesen und erweitert werden. Hashketten
erkennen Beschädigungen; sie ersetzen keine Zugriffskontrolle oder Signatur.
Es wird keine personengeprüfte Autorenschaft oder Mehrbenutzerverwaltung behauptet.

Ausführung nur über bestehende Mission, Brain, ControlMaster, Guard und Audit.
Der Lauf wartet auf die bestehende Captain-Freigabe im Posteingang. Anschließend
in der App ausdrücklich fortsetzen. Die App erteilt keine Freigaben.

## Später als Update installieren

Das ZIP ist ein vollständiger Stand der beiden Prüfbereiche des bestehenden
Updaters, mit release/MANIFEST.sha256 und Quellbasis in release/CANDIDATE.json.
Kein Installer startet sich selbst; keine Modelle, Engine oder Zugangsdaten sind
enthalten. Kein GNPKG-Bestand ist enthalten. Prüfsummen sind keine Signatur.

1. ZIP in einen neuen, getrennten Ordner entpacken. SEDRA vor Übernahme beenden.
2. Mit dem Python der vorhandenen SEDRA-Umgebung INSTALL_UPDATE.py aufrufen:

   `python INSTALL_UPDATE.py --root "<sedra>"`

   Das ist nur eine Vorschau. Sie nennt geänderte Dateien, Modulrechte und einen
   Bestätigungsschlüssel. Ohne --apply wird nichts in der Installation geändert.
3. Nur nach Durchsicht denselben Aufruf um `--apply --confirm <Schlüssel>` ergänzen.
   Der Schlüssel gilt genau für Quelle, Zielpfad und aktuellen Zielstand.
4. SEDRA neu starten. Beide Prozess-Apps finden sich unter Arbeit. n8n bleibt ausgeschaltet.
5. Rückweg: bestehende System-App, Updates, letzte Sicherung wiederherstellen.
   Dabei bleiben Workflow-Laufdaten und lokale Einstellungen erhalten.

Der Offline-Weg verwendet die geprüfte Updater-Fassung des Pakets. Das ist wichtig:
der alte Updater behandelt runtime/config/local_paths.yaml und lokale .bak-Dateien
noch als entfallene Programmdateien. Der Kandidat schützt diese Dateien explizit.
Das Paket darf deshalb nicht blind mit dem alten Updater eingespielt werden.

Bei abweichendem Programmstand oder zusätzlichen Programmdateien wird die
Offline-Installation gesperrt. Nicht erzwingen: auf den neuen Stand aufsetzen,
prüfen und neu paketieren. Ein bloß gleicher Versionsname ist kein Kompatibilitätsbeleg.
Programmänderungen an den anderen runtime/config-Dateien lösen ebenfalls einen
Konflikt aus; nichts wird dabei automatisch überschrieben.

## Optional: lokale n8n-Testinstanz

Die App installiert oder startet n8n nicht. Für echte Engine-Läufe benötigt sie
eine eigene lokale Instanz mit öffentlicher REST-API und einen API-Schlüssel mit
den benötigten Workflow-Rechten. Endpunkte: POST/GET/DELETE /api/v1/workflows,
POST .../{id}/activate und .../{id}/deactivate. Manuell vorab mit der konkreten
n8n-Version abnehmen; deren vollständige Version beim Test protokollieren.

runtime/config/n8n.example.json nach <Projekt>/local_config/n8n.json kopieren,
enabled ausdrücklich auf true setzen. base_url darf nur http://127.0.0.1:<Port>
sein. SEDRA_N8N_API_KEY in der Umgebung des SEDRA-Prozesses setzen. Kein Schlüssel
in der JSON, im Workflow oder im Repository. Neustart übernimmt die Umgebung.

Unterstützt: manualTrigger 1, set 3.4 (manuelle Zuweisung einfacher Felder),
if 2.2 (begrenzte Operatoren), noOp 1, stickyNote 1. Maximal 32 aktive Knoten,
ein Start, azyklisch, alle aktiven Knoten erreichbar. Einfache Ausdrücke wie
`={{ $json.text }}` sind erlaubt. Keine Methoden, $env, freien Code, Credentials,
HTTP-Aktionen, Subworkflows, Zeitpläne, Schleifen, Parallel-Worker oder KI-Knoten.
Unbekannte n8n-Versionen/Knoten bleiben im Austausch erhalten, Ausführung gesperrt.

Der Adapter erstellt nach Freigabe einen zufälligen temporären Webhook-Workflow,
bildet die Eingabe auf den ursprünglichen manuellen Start ab, aktiviert ihn,
prüft die Definition erneut, ruft ihn einmal auf und deaktiviert/löscht ihn.
Der API-Schlüssel wird NICHT an den Webhook geschickt. Keine Redirects/Proxys.
Workflow-Einstellungen aus dem Import (etwa errorWorkflow) werden nie übernommen.
Erfolgreiche und fehlerhafte Engine-Ausführungsdaten werden für diesen temporären
Workflow nicht dauerhaft in n8n gespeichert; SEDRA hält das Ergebnis als Artefakt.
Cleanup-Fehler zeigen Remote-ID und offenen Bereinigungsbedarf. Ein Timeout nach
Trigger hat unbekannten Ausgang und wird nie automatisch wiederholt.

Vertrauensbasis: lokale n8n-Engine, deren Administrator und dedizierte Testinstanz.
Loopback ist keine Betriebssystem-Isolation. Der MVP ist keine Sandbox für beliebige
Nodes. Die Ausgabe zeigt Endergebnis und Missionsschritt, kein komplettes n8n-Tracing.
COMPLETE bedeutet hier: Engine-Antwort als Artefakt vorhanden, keine fachliche
Freigabe. Die bestehende Ergebnisqualifikation ARTIFACT_ONLY bleibt bewusst erhalten.

## Daten, Grenzen und Weiterentwicklung

Revisionen: <Projekt>/runtime_data/workflows/<ID>/*.json. Läufe: vorhandene
Missionsdateien und runtime_data/workspace/<Mission>/n8n-result.json. Audit:
vorhandene Kette. Definitionen können geheime Werte enthalten; Originalexport
bewusst bestätigen. Bereinigter Export entfernt benannte Geheimnisfelder und
pinData/staticData, erkennt aber keine Geheimnisse in beliebigen freien Texten.

Rückkehr zu einer alten Revision verändert laufende Missionen nicht. Ein gestarteter
Lauf ist an seine Definition gebunden. Zeichnungen ändern sich währenddessen frei
als neuer Entwurf; Änderungen geben keinem laufenden Schritt neue Rechte.

Als nächstes: reale n8n-Versionsmatrix, stärkere Isolierung für weitere Nodes,
geprüfte externe Connectoren und erst danach lokale KI-/Captain-Brückenknoten.
Es wird keine vollständige n8n-Kompatibilität behauptet.

## Öffentliche Veröffentlichung

Nach Review/Übernahme und erneuten Tests auf der dann aktuellen Basis:
Version mit dem Release-Verantwortlichen abstimmen, Änderungen committen,
release_manifest.py aus dem Commit erzeugen, Manifest committen und genau diesen
Stand taggen. Erst ein bewusst veröffentlichter Tag macht das Update über die
bestehende GitHub-Update-Suche verfügbar. Hier wurde nichts gepusht oder getaggt.

Entwicklungszweig: codex/n8n-workflow-app. Paket neu erzeugen:
`python runtime/benchmarks/package_n8n_update.py --output <Ziel.zip> --previous-candidate <Gepruefter-1.22.1-Kandidat.zip>`.
Paketprüfung einschließlich Upgrade und Rücknahme des Vorgängers:
`python runtime/benchmarks/verify_n8n_update.py --zip <Ziel.zip> --previous-candidate <Gepruefter-1.22.1-Kandidat.zip> --report <Bericht.json>`.
Prüfbericht: docs/N8N_VALIDATION.md.
