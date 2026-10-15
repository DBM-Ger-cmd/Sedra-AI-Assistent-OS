# GUPPI v1.20 – Handoff

## Ziel

GUPPI erhält eine starke, kontrollierte Self-Development-DNA statt einer immer größeren Tool-Sammlung.

## Leitregel

> Capability before Tool.

## Stabilitätsgrenzen

- Stable wird nicht direkt als Entwicklungsworkspace verwendet.
- Guard / Captain Gates werden nicht umgangen.
- Neue Rechte werden nicht durch Self-Development erzeugt.
- Externe Modelle werden nicht still als Fallback benutzt.
- E3 Core kann niemals automatisch aktiviert werden.
- GUPPI-generierte Capabilities werden nicht automatisch `KNOWN_GOOD`.

## Local-First Modellstrategie

- Qwen3.5 = primäre Arbeitsmodellfamilie
- Kev = lokale Verification-/Decision-Schicht
- Kev Provider ist standardmäßig deaktiviert, bis lokaler Server qualifiziert ist

## Nächster realer PC-Schritt

1. v1.20 auf Ziel-PC starten.
2. Hardware Snapshot + Hardware-Model-Pass prüfen.
3. passendes Qwen3.5-Profil auswählen/anpassen und als Custom Profile speichern.
4. Kev lokal bereitstellen und Provider explizit aktivieren.
5. kontrollierten E1-Testfall in der GUPPI Entwicklungsumgebung durchführen.
6. Baseline -> Candidate -> Tests -> Kev -> Independent Review -> Captain Decision nachvollziehen.
7. erst danach E1-Automation weiter öffnen.
