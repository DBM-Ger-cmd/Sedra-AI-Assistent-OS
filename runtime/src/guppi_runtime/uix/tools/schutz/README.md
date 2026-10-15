# KI GateWay · Schutz (Nachweis)

Aus der ersten externen Lieferung (KI GateWay 0.3.0, 15.10.2026) übernommen und seit Build 19 CORE. Liest `GET /api/guard/status`
(der Inhaltsschutz von Build 16 – für ganz SEDRA, nicht nur für das GateWay) und `POST /api/guard/probe` („Selbst ausprobieren“:
prüft einen Text, ruft kein Modell, speichert nichts).

Geändert gegenüber der Lieferung (zwei Stellen, Build 19): das Umschalten einzelner Regeln ist weg – die Schärfe kommt aus dem
Modus des Projekts (Sandbox scharf, sonst beobachten), es gibt keinen zweiten Schalter. Die Vorführung der Lieferung
(Attrappen-KI) ist nicht Teil von SEDRA; ihr Reiter erscheint nur, wenn der Status `demo` sagt – tut er hier nie.
