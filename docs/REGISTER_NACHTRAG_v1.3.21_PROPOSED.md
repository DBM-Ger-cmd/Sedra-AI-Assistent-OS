# Registernachtrag zu v1.3.20 (15.10.2026, 14:35, PROPOSED) – Ticket B6-G-03 geplant, Zwischenstand

| ID | Änderung | Status / Vermerk |
|---|---|---|
| REGELWERK-v0.1 | neu: `REGELWERK_DATENKATEGORIEN_CLOUDSPERRE_v0.1_2026-10-15_PROPOSED.md`, 16 Regeln R-01…R-16; verbindlich für den Prototyp laut Klaus (14:08, Q2); neue Regeln als neue Zeilen mit neuer Version | DECIDED (Grundsatz) / PROPOSED (Inhalt, Rechtsbezüge sind Annahmen, Datenschutzreview offen) |
| B6-G-03 | neu: „SEDRA als Assistent in der KI-GateWay-Shell“ – Regelwerk im Modul, Wissensbasis, Leitfaden, Chat-Anbindung, Shell | PROPOSED mit Zwischenstand: `klassen.py` (Regelwerk, A01, R-01 nur lokal), KI-Kennzeichnung R-14, `wissen.py` (SQLite, Leitfaden, Antworten) **implementiert**; `klassen` getestet (38 Tests `test_gateway` grün), `wissen` nur von Hand geprüft; Chat/Shell nicht gebaut. Commit `9915aa2`/`12b8a53` Arbeitskopie; ZIP `GUPPI_Runtime_v1.20_Build_020_B6-G-03-Zwischenstand_2026-10-15.zip` SHA-256 `ecf9dd8c…a3b33`, Patch `1f5aed55…4959`. Plan und Prompt: `PLAN_UND_PROMPT_SEDRA_ALS_GATEWAY_ASSISTENT_2026-10-15_PROPOSED.md`. Gate Klaus (E1–E4) |
| P4 | beantwortet durch das Regelwerk: AUTO_APPROVED nur bei R-15 (keine Kategorie) oder lokal ohne Prüfpflicht (R-06, R-11, R-12) | DECIDED (Klaus 14:08) |
| KD-GUPPI-06 | SEDRA sieht die Studio-Shell als Arbeitsumgebung; Leitfaden (Anlegen → Eingeben → Warten → Prüfen → Ablegen) ist Teil des Moduls | DECIDED (Klaus 14:14/14:19, Q2) |
| E1–E4 | Freigabe Plan/Prompt; Wissensbasis vor dem Modell; eigene Einträge ohne Gate; P5-Zahl 24 h im selben Ticket | OPEN, Klaus |

**Abgabeplan 20.10.:** unverändert. Nichts davon berührt den Hauptbuild v0.7.7.
