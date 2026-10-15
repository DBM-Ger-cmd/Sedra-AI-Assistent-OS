# Handoff-Testfälle: korrigierte Erwartungen

Diese Matrix beschreibt Zieltests; sie behauptet nicht, dass die noch fehlenden Funktionen bereits bestehen.

| Handoff | Stand / korrigierte Erwartung | Nächster Nachweis |
| --- | --- | --- |
| 01 Lokale Analyse | v1.12/v1.13 prüft begrenztes Dateiinventar. COMPLETE belegt diesen vereinbarten Umfang, keine semantische Repoanalyse | Ergebnisart und Akzeptanzkriterien müssen den ausgeführten Umfang nennen |
| 02 GPU belegt | Job-/RAM-/Thermal-Admission vorhanden; strukturierter Wartepfad fehlt | NOT_NOW mit Reason-Code; Resume prüft neu; kein FAILED allein wegen belegter Ressource |
| 03 Cloud verboten | Lokale Modelladapter vorhanden; kein Cloud-Adapter | Lokale URL-Grenzen weiter testen; zukünftiger Cloud-Stub darf bei Verbot nicht aufgerufen werden; unsichere Fallbacks blockieren |
| 04 Codeänderung | Kandidat getrennt, verifiziert, PREPARED_NOT_TESTED; Testplan allein führt keine Tests aus | Inhaltsfreigabe-Tampertest; später reale Guest-Tests mit Code-Digest; kein Accept ohne geforderte Nachweise |
| 05 Externe Aktion | Kein integrierter Versandpfad | Später Gate an Payload und Empfänger binden; Änderung nach Freigabe ablehnen; heute UNSUPPORTED |
| 06 Unbekanntes Thema | Persistenter Draft ohne Rechte schon vorhanden | Unterscheide Draft und aktives Thema; eine Mission mehrfach routen darf keine Mehrfachevidenz erzeugen |
| 07 Hardware | Telemetrie/Admission/Profile vorhanden; Lüfter-/Firmware-Schreiben nicht qualifiziert | Simulierte Sensorzustände; fehlende Werte offen kennzeichnen; tatsächliche Geräteprüfung am PC |
| 08 Performancebehauptung | Benchmark-/Qualifikationsbausteine vorhanden; kein allgemeiner Claims-Vertrag | Reproduzierbare Messung und Vergleichsbasis; LLM-Behauptung allein bleibt unqualifiziert |
| 09 Externer Timeout | Externe Ausführung nicht implementiert | Später UNKNOWN_REMOTE_OUTCOME, Statusabfrage/Idempotenz; kein automatisches Doppelsenden |
| 10 Self-Development | Ersatztext geliefert; kein autonomer CODE→TEST→ACCEPT-Zyklus | Erst Testbinder, Guest und Ergebnisprüfung; Review kann Vorbereitung bestätigen, keine ungetestete Produktübernahme |

Zusätzliche Regressionen für die vorgeschlagene Integration:

- Plan mit mehreren Schritten: jeden genau einmal fortsetzen, vorhandene Ergebnisse nach Neustart nutzen.
- Gate-Inhalt, Quellstand, Ziel oder Empfänger nach Freigabe ändern: erneute Freigabe notwendig.
- Ressourcen nach positiver Vorprüfung belegt: Ausführung wartet kontrolliert.
- Alternative unterschreitet harte Kontext-/Datengrenze: nicht auswählen.
- Wiederholtes VERIFY FAIL ohne neuen Input: begrenzt stoppen; Ziel bleibt unverändert.
- Candidate-Staging unterbrochen: Restbestand erkennen; keine falsche Vorbereitung/PASS melden.
- Cloud untersagt und lokaler Provider fehlt: offen blockieren; kein versteckter Cloud-Fallback.
- Zentrale Policyänderung: eigenes Captain-Gate, auch bei bestandenem Test.
- Sensorwert unbekannt oder veraltet: expliziter Befund statt angenommener Verfügbarkeit.

PC-Ready: Offline-/USB-Start, eingebettetes Python, konkrete Windows-Version, Guest-Image, MicroVM-Isolation und Lifecycle sowie reale Sensor-/Adapterqualität bleiben gesonderte Abnahmepunkte.
