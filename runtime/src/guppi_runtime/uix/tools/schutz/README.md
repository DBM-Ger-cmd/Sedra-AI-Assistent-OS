# KI GateWay · Schutz (Nachweis)

Aus der ersten externen Lieferung (KI GateWay 0.3.0, 15.10.2026) übernommen und seit Build 19 CORE. Liest `GET /api/guard/status`
(der Inhaltsschutz von Build 16 – für ganz SEDRA, nicht nur für das GateWay) und `POST /api/guard/probe` („Selbst ausprobieren“:
prüft einen Text, ruft kein Modell, speichert nichts). Entscheidungen beantwortet es über `ctx.shell.decide`.

Geändert gegenüber der Lieferung (Build 19, Code nachgezogen 19.10.2026): das Umschalten einzelner Regeln ist weg – die Schärfe
kommt aus dem Modus des Projekts (Sandbox scharf, sonst beobachten; was den Rechner verlässt und der Grundschutz immer scharf), es
gibt keinen zweiten Schalter. Der Reiter „Regeln“ zeigt die Schärfe nur noch an und verweist auf „Modus und Grenzen“. Die
Vorführung der Lieferung (Attrappen-KI, simulierte Cloud) ist nicht Teil von SEDRA; ihr Reiter und ihr Code sind entfernt.
Die Routen `/api/guard/group` und `/api/guard/demo` gibt es im Server bewusst nicht, und das Werkzeug ruft sie nicht mehr auf
(Vertragstest: jede `/api/`-Route eines Werkzeugs muss im Server registriert sein).
