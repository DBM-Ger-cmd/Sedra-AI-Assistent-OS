# 01 – Überblick und Herkunft

## Was SEDRA ist

SEDRA (*Self-Evolving Development & Research Assistant*) ist ein **lokaler Agenten-Betriebsrahmen für den eigenen PC**. Er plant Aufgaben, führt sie mit lokalen Sprachmodellen aus und kann unter strenger Kontrolle eigene Teile des Codes erweitern.

Der technische Name im Code ist **GUPPI** (Paket `guppi_runtime`, Archiv, Logbuch). **GUPPI** ist zugleich das Maskottchen und die Stimme im Chat. Diese Trennung gilt seit dem 14.10.2026 und ist im README festgehalten.

## Grundsätze

Aus dem README und der Entwicklungsdoku:

- **Captain First:** Jede Wirkung nach außen und jede Übernahme in den eigenen Code braucht die Freigabe eines Menschen, des *Captain*.
- **Local First:** Läuft vollständig lokal. Es gibt keinen stillen Wechsel auf ein Cloud-Modell.
- **Capability Before Tool, Evidence Before Evolution, Plan Before Code, Candidate Before Stable, Verify Before Accept, Least Privilege, Reversible Change, Learn From Results.**

Daraus folgen harte Regeln, die auch die Selbstentwicklung nicht umgehen kann:

- Der Guard und die Captain-Freigaben werden nie umgangen.
- Selbstentwicklung erzeugt keine neuen Rechte.
- Der Kern (Stufe E3) wird nie automatisch geändert.
- Übernommener Code lässt sich zurückrollen.

## Was heute läuft (Stand Oktober 2026)

- **Lokale Modelle:** eigener llama.cpp-Server; Hauptmodell Qwen3.6-35B-A3B auf einer RTX 4070 Ti (12 GB). Gebaut und gemessen auf einem einzigen PC.
- **Missionen mit Kontrolle:** Jede Aufgabe läuft durch *verstehen → planen → ausführen → prüfen*. Ein Guard entscheidet jede Aktion (erlauben, sperren, den Captain fragen). Alles landet in einer hash-verketteten Audit-Kette.
- **Selbstentwicklung:** In einer abgeschotteten Entwicklungsumgebung (DevVM, mit microVM für Tests) schreiben Coder-Agenten neue Module. Versteckte Abnahmetests, die das Modell nie sieht, entscheiden über die Annahme.
- **Inhaltsschutz vor jedem Modellaufruf** (seit Build 16).
- **Strukturierte Antworten vom Modell** mit erzwungenem JSON-Schema (seit Build 17).
- **Oberflächen (Shells)** aus Code oder aus einer Vorgabe-Datei (seit Build 14 und 17), mit eigenem Einstieg (seit Build 18).
- **Das KI GateWay** als erster Anwendungsfall, der auf dem Kern aufsetzt (seit Build 19).

## Herkunft: Von GUPPI zu SEDRA – die Stationen

Die Entwicklung lief über mehrere Versionen (v1.2 bis v1.20). Ältere Notizen liegen im Quellcode unter `docs/historie/`. Die Stationen, die für dieses Archiv zählen:

| Zeitpunkt | Station | Bedeutung |
|---|---|---|
| bis 13.10. | GUPPI-Paket v1.2 bis v1.20 | Missionen, Agent Manager, DevVM, Retro-Oberfläche „GUPPI XP“ |
| 14.10. | Namensgebung und Oberflächen | SEDRA als Systemname, GUPPI als technischer Name und Maskottchen; Desk, Werkbank und Grenzen (Build 7 bis 9); Werkzeug- und Shell-Vertrag (`SHELL_WERKZEUG_VERTRAG_v1`) |
| 14.10. | Start-Shell | Einstieg „Start“ mit Karten je Oberfläche (Build 14) |
| 15.10. | Erste Lieferung von außen | Zwei Werkzeuge eines anderen Chats durch das Gate; Vertragsbefunde V1 und V2 geschlossen (Build 15) |
| 15.10. | Inhaltsschutz im Kern | Kein Modellaufruf ohne Prüfung (Build 16) |
| 15.10. | Shell-Creator | Schema-Zwang beim Modell, Rahmen aus Vorgabe, Satz an GUPPI (Build 17) |
| 15.10. | START_SEDRA | Sauberer Einstieg; GUPPI XP als wählbare Shell (Build 18) |
| 15.10. | KI GateWay in SEDRA | Vorgang nach dem Studio Flow, Schutzklassen, Studio-Shell (Build 19) |

Eine ausführliche Chronik mit den Abnahmezahlen steht in `07_BUILD_CHRONIK_14_BIS_19.md`.

## Was SEDRA bewusst nicht ist

- Kein Cloud-Dienst. Cloud-Modelle sind bis auf Weiteres nur **simuliert**.
- Kein Mehrbenutzersystem. Es gibt **keine Rollen und Berechtigungen**; der Captain ist die einzige Freigabestelle.
- Kein Ersatz für eine Produkt-Aufbewahrungspolicy. Die Löschfristen im KI GateWay sind Testwerte, keine Policy.
