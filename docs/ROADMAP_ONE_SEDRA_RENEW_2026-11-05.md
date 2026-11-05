# Roadmap One Sedra – Renew und Unterchat-Plan (Stand 05.11.2026)

Ersetzt `UIX_ROADMAP.md` (04.10.2026, Retro-Desktop, überholt). Die Bausteine AM0–AM9 (`KONZEPT_APPS_UND_ERWEITERUNGEN_v1.md` §11) gelten weiter; hier steht nur, **in welcher Reihenfolge und in welchen Chats** sie jetzt gebaut werden.

## 1. Leitlinien (Beschluss des Captains)

1. **One Sedra (Kennung `harness`) ist die Zentrale.** Sedra XP und Retro-Desktop werden nicht weiterentwickelt (eingefroren, nur Fehler, die Sicherheit betreffen).
2. Funktionen der anderen Shells (Cockpit, Translator, Gateway, Paperclip, Wissensbasis, Minimal) wandern als **Apps/Werkzeuge** in One Sedra; Zuschnitt für Auftraggeber über **Profile**, nicht über neue Shells.
3. Ein Weg für Freigaben, ein Weg für Berechtigungen (Grundfunktionen nie ausblendbar).
4. Erst messen und im echten Sedra ausprobieren, dann ausbauen. Logs zuerst selbst lesen (`events.jsonl`).
5. Keine Läufe auf der GPU, keine Downloads, kein Push ohne ausdrückliches Ja.

## 2. Wo wir stehen

Fertig auf `main` (bis `2d0c62d`): Modell-Laden gehärtet (Auto-Fenster, Ladeprobe, Vertragstest), Info-Hub, Betriebslog, Freigaben S1–S3, Desktop Builder (Module, Start-Menü, Taskleiste, Layout, Profile mit Marke/Logo/Schrift/Startseite), Rechtsklick „Im Chat anpassen“, Lernsystem L1–L4 mit Vorhersagen beim Tippen, Cache-Messung, Taskleiste mit Temp/VRAM/RAM.

Nicht im echten Sedra geprüft: Cache-Zahlen gegen den echten llama-server, Lernsystem mit echten Lob-/Korrekturdaten, Betriebslog- und Belohnungs-Anträge (Posteingang), Playwright-Test `test_uix_harness_browser.py`.

## 3. Neue Phasen

| Phase | Ziel | Inhalt | Bausteine |
|---|---|---|---|
| **R0 Festigen** | Das Gebaute ist im Alltag bewiesen | Neustart + Strg+F5, Anträge freigeben, Cache-Zahl und Lernsystem beobachten, Playwright-Test laufen lassen, wackelige Tests beruhigen | – |
| **R1 Zentrale** | Eine Oberfläche statt sechs | Inventur Shell-Funktionen gegen One Sedra; dann je Shell eine App: Translator, Wissensbasis, Cockpit, Paperclip, Gateway; Minimal wird Profil | AM1, AM2 |
| **R2 Profile für Auftraggeber** | Zuschnitt ohne neue Shell | Profile exportieren/importieren, Prüfung beim Laden, Profilvorlagen (KMU, Privat, Stick), Logo/Schrift/Startseite fertig durchgetestet | Entwurf Auftraggeber-Profile |
| **R3 Freigaben und Rechte** | Ein Modell „Erlaubnis mit Dauer“ | Freigaben S4 (Schutzcode erst nach Beschluss), Berechtigungsseite, Update mit Diff | AM3, AM8 |
| **R4 Unternehmen** | Rollen und Betreiber-Richtlinie | Konten-Modell, Rollen, Richtlinie, Profile je Rolle in One Sedra | AM7 (Stufe 4) |
| **R5 Lernen und Hilfswerkzeuge** | Aus Lob und Korrektur wird Verhalten | Rückblick im Alltag, Vorschläge verbessern, CPU-Hilfswerkzeuge E1–E5 | `PLAN_CPU_HILFSWERKZEUGE` |
| **R6 Betrieb und Stick** | Auslieferung | Minimal-Stick aus Profil „Stick“, Werkstatt/Betrieb trennen, Updater | AM9, `PLAN_USB_STICK_MINIMAL` |
| **R7 Dienste und Cloud** | Außenanbindung | Dienste außerhalb des Prozesses, Langdock als Modellquelle und Agenten (ausgehend) | AM4, AM5, AM6 |

Reihenfolge: R0 → R1 (und R2 parallel, andere Dateien) → R3 → R4; R5 läuft nebenher; R6 nach R1/R2; R7 nach R3.

## 4. Unterchat-Plan

Jeder Unterchat ist eine eigene Sitzung mit eigenem Worktree und Branch. Zwei Schreiber nie auf denselben Dateien.

| # | Name | Phase | Ziel / fertig, wenn … | Bereich (Dateien) | braucht vorher |
|---|---|---|---|---|---|
| U0 | **Alltagsprobe** | R0 | Cache-Zahl, Lob/Korrektur, Anträge im echten Sedra beobachtet; Befunde in `docs/`; Playwright-Test grün oder begründet | nur lesen, `docs/`, Tests | Captain startet Sedra neu |
| U1 | **Shell-Inventur** | R1 | Tabelle „Funktion der Shell → in One Sedra vorhanden / fehlt / Ziel-App“, Reihenfolge-Vorschlag | nur lesen, `docs/` | – |
| U2 | **App Translator** | R1 | Übersetzer als App in One Sedra, Test grün, Shell Translator unverändert | `uix/shells/harness/`, `shells/translator` (lesen) | U1 |
| U3 | **App Wissensbasis** | R1 | Wissensbasis-Funktionen in One Sedra (Suche, Quellen, Anträge) | `harness/`, `desk_wissen` | U1 |
| U4 | **Profile exportieren** | R2 | Profil als Datei aus-/einlesen, Prüfung, Vorlagen KMU/Privat/Stick | `harness/desktop.py`, `builder.js`, Tests | – |
| U5 | **Freigaben S4** | R3 | Gemeinsames Modell „Erlaubnis mit Dauer“; Schutzcode nur nach Beschluss | `desk/freigabe*.py`, `aufgabe.js`, `freigabeklasse.py` | Beschluss Captain |
| U6 | **Rechte und Rollen** | R3/R4 | Spec AM3 → AM7 in Code: Berechtigungsseite, Rollen, Richtlinie | `desk/`, `docs/SPEC_APPS_v1_AM3/AM7` | U5 |
| U7 | **Lernen ausbauen** | R5 | Rückblick im Alltag, bessere Vorschläge, E1–E5 der CPU-Hilfswerkzeuge | `harness/belohnung.py`, `vorschlaege.js`, `PLAN_CPU_HILFSWERKZEUGE` | U0 |
| U8 | **Stick aus Profil** | R6 | Minimal-Stick als Profil von One Sedra gebaut; Branch `claude/usb-stick-minimal-3c1b19` abgelöst oder eingearbeitet | Stick-Branch, `PLAN_USB_STICK_MINIMAL` | U1, U4 |
| U9 | **Testgesundheit** | R0 | Wackelige Tests (`test_harness_lauf`, `test_uix_harness_lauf`, `test_uix_stufe6.ImBrowser`) unter Last stabil | `tests/` | – |

Abhängig von nichts und gefahrlos parallel startbar: **U1, U4, U9** (U0 braucht den Neustart des Captains).

## 5. Altlasten und Aufräumen

- `UIX_ROADMAP.md`: Kopf „überholt durch ROADMAP_ONE_SEDRA_RENEW“ ergänzen.
- Sedra XP/Retro-Desktop: im Shell-Verzeichnis als „eingefroren“ kennzeichnen (Hinweis in `README`).
- MasterChat-Probelauf und Übersicht der Nebensitzungen (`UEBERSICHT_NEBENSITZUNGEN_2026-11-04.md`) nach jedem Unterchat nachziehen.

## 6. Offene Entscheidungen des Captains

1. Welche Shell zuerst (Vorschlag: Translator oder Wissensbasis, vorher U1)?
2. Schutzcode bei Freigaben (S4): ja/nein?
3. Soll die Stick-Version ein Profil von One Sedra werden (Vorschlag) oder eigener Zweig bleiben?
4. Sollen Unterchats nach Phase gestartet werden oder einzeln auf Zuruf?
