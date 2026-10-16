# GUPPI Core Contract v1

Der Core Contract definiert die stabile Grenze zwischen GUPPI Core und Erweiterungen.

## Stable Core
Der feste Stamm umfasst nur:

1. Brain / Mission Loop + Capability Router
2. Mission State
3. Message Bus
4. Guard / Human Gates
5. Registries
6. Lifecycle / Update / Rollback

Planning, Control Master, Verification, Knowledge und Communications sind **Module**.

## Öffentliche Schnittstellen

### Routing API
Captain/User-Intent in benötigte Capabilities, Module, Skills, Tools, Modellpolitik und Risiko auflösen. Der Router führt selbst keine Tools aus.

### Mission API
Missionen lesen, Status anfragen, zulässige Statusänderungen beantragen.

### State API
Strukturierten Mission State lesen und nur freigegebene Bereiche schreiben.

### Message API
Kontrollierte Modul-zu-Modul-Kommunikation über Mission-ID, Sender, Empfänger und Nachrichtentyp.

### Module API
Module registrieren, Fähigkeiten veröffentlichen, Health-Status melden.

### Skill API
Skills registrieren, laden, versionieren und einem Modul zuordnen.

### Tool API
Tools registrieren und kontrolliert über Control Master aufrufen.

### Guard API
Aktionen vor Ausführung auf ALLOW, BLOCK oder CAPTAIN_REQUIRED prüfen.

## Regeln
- Keine direkten Importe in private Core-Funktionen.
- Module verändern niemals Captain-Intent oder Core-Invarianten.
- Horizontale Modulkommunikation ist erlaubt, aber protokolliert.
- Ergebnisse mit Missionsrelevanz werden in den Mission State zurückgeführt.
- Kritische Aktionen laufen immer durch Guard/Human Gate.
