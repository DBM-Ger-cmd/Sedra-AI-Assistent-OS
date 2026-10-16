# Offene Punkte: Prototyp GUPPI/SEDRA Build 20 und KI GateWay Studio (PROPOSED, 15.10.2026, nach Ticket B6-G-01)

Status Q3. Stand nach Umsetzung von B6-G-01 (G-01, G-04, G-05, G-06). „Erledigt“ heißt implementiert und auf Linux getestet, nicht abgenommen.

## A. Technisch, im Prototyp

| Nr | Punkt | Stand | Nächster Schritt | Gate |
|---|---|---|---|---|
| G-01 | IBAN-Vorgang nicht bearbeitbar | **erledigt** (B6-G-01) | Abnahme; Lauf mit echtem Modell in Station 04 | Klaus |
| G-04 | Inhaltsschutz Standard „beobachten“ | **erledigt** (B6-G-01): Standard scharf | Abnahme; Wirkung auf SEDRA-Gespräche und Agentenläufe beobachten (mehr Entscheidungen im Desk) | Klaus |
| G-05 | Bindung ohne Zweck und Person | **erledigt** (B6-G-01) | Abnahme; Person ist nicht authentifiziert – bleibt Pilotannahme | Klaus |
| G-06 | Korpus-Messung gegen GUPPI-Matrix | **Adapter erledigt**, Lauf offen | Korpusdatei (93 Fälle) bereitstellen, Lauf, Bericht ins Projekt | David (Korpus), Klaus |
| G-07 | `gateway`/`content_guard` nicht als Kern E3 in der Selbstentwicklung | offen (bewusst nicht im Ticket) | Entscheidung, ob der Prototyp eigenständig weiterläuft; dann `evolution_targets.CORE_TARGETS` ergänzen | Klaus |
| G-08 | Entwürfe liegen bis zum Löschdatum im Klartext unter `local_config/gateway/entwuerfe/` | offen | Verschlüsselung oder kürzere Frist; hängt an P5 | Klaus + David |
| G-09 | `sk-ant-…`-Schlüssel ohne Stichwort nicht erkannt | offen (im Prototyp dokumentiert) | Regel in `b6core/privacy.py`, Herkunft neu prüfen; betrifft beide Linien | David |
| G-10 | Windows-Lauf des geänderten Stands | offen | `run_tests.bat` auf dem Entwicklungs-PC | Klaus |

## B. Beide Linien (B6-Code nötig)

| Nr | Punkt | Stand | Nächster Schritt | Gate |
|---|---|---|---|---|
| G-02 | P02/V01 nicht erkannt („krankgeschrieben“, „Depression“, „15-jährig“) | offen; im Prototyp belegt, im B6-Build zu bestätigen | Ticket B6-P1-02: Schlüsselwörter und Altersmuster erweitern, Tests zuerst rot; dann als Herkunftsupdate in `b6core` des Prototyps | David, fachlich Klaus |
| Q-01 | `b6core/HERKUNFT.sha256` gegen B6 v0.7.8-Originale | offen | B6-Kandidaten-ZIP vorlegen, Prüfsummen vergleichen | David |
| Q-02 | Zwei Policies (`b6-policy-0.4.0-DRAFT` und `sedra-gateway-1.0`) | offen | MVP-Option A/B/C (P2) entscheidet, ob `klassen.py` entfällt | Klaus |

## C. Fachliche Entscheidungen

| Nr | Frage | Stand | Wirkung |
|---|---|---|---|
| P1 | Rolle des Prototyps: getrenntes Projekt (Stufe 3) oder Teil des B6-MVP? | offen | bestimmt G-07, Q-02 |
| P2 | MVP-Option A (B6 eigenständig, Muster übernehmen), B (SEDRA als Plattform), C (B6-Kern als Paket, SEDRA ruft auf) | offen, Empfehlung A jetzt, C als Zielbild | Architektur Stufe 2/3 |
| P3 | Injection in der Anfrage | **entschieden 15.10. (Klaus, Q2): Review** – Originaltext nach Prüfung nur ans lokale Modell | im Code vermerkt; weicht von B6 P0-10a §7 ab → Registereintrag, B6-Policy ggf. nachziehen |
| P4 | `AUTO_APPROVED` ohne bestätigte Quellenklasse und bekannten Zweck zulässig? | offen; Zweck ist seit G-05 Pflichtfeld, Quellenklasse fehlt weiter | Quellenregister im Vorgang oder Review für SK0/SK1 |
| P5 | Frist rehydrierter Entwürfe (Testwert 23.10. Tagesende) | offen | `vorgaben.yaml`; hängt mit G-08 zusammen |
| P6 | Unterlagen „V4-Akte“, „Studio Flow v1.1“, „0.3.0-Lieferung“ ins Quellenmanifest | offen | Herkunft der GUPPI-Spec belegen |

## D. Kein Einfluss auf die Abgabe 20.10.
Alle Punkte liegen außerhalb des Hauptbuilds v0.7.7. Stoppregel aus `PLAN_ABGABE_BAUSTEINPRUEFUNG_2026-10-14_PROPOSED.md` bleibt.
