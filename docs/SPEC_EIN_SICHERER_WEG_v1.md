# Spec: Ein sicherer Weg – das KI GateWay in SEDRA, und was SEDRA dabei sicherer wird (15.10.2026, S1–S5 GEBAUT in Build 16 · G1–G3, G5, G6 GEBAUT in Build 19 nach SPEC_GATEWAY_VORGANG_v1 (Studio Flow statt Bestandsablauf) · S6, S7, G4 PROPOSED)

**Captain, 02:15:** *„Können wir das Modul an SEDRA anpassen, damit es am Ende nur einen sicheren Weg gibt – auch wenn es heißt,
dass wir SEDRA sicherer machen müssen?“* Ja. Diese Spec sagt, wo SEDRA heute schwächer ist als die Lieferung, was deshalb
*in SEDRA* kommt, und wie das GateWay darauf sitzt. Geschrieben vor dem Bau, nach dem Lesen beider Seiten.

## 1. Die ehrliche Gegenüberstellung

| | SEDRA heute (`core/guard.py`, `models/router.py`) | KI GateWay (`sedra_gateway/guard.py`, `policy.py`, `scan.py`) |
|---|---|---|
| **Was es bewacht** | **Handlungen**: jede Aktion hat eine Regel (ALLOW / BLOCK / CAPTAIN_REQUIRED), ein Gate hat Einmal-Token, Inhaltsbindung, TTL; seit Build 9 die vier Grenzen | **Inhalte**: jeder Modellaufruf wird gescannt (Schlüssel, Karten, IBAN, Personen, Anweisungen an die KI, unsichtbare Zeichen), bewertet (ALLOW / REVIEW / PSEUDONYMIZE / BLOCK), fremde Teile als Daten markiert, pseudonymisiert, die **Antwort** geprüft |
| **Der Modellaufruf** | `ModelRouter.chat` ist die eine Stelle – **ohne jede Inhaltsprüfung**; Audit `TOOL_CALLED` mit Anbieter und Modell | `ModelGuard.call` ist die eine Stelle – `complete` wird von außen mitgegeben, kein eigener Netzzugriff |
| **Netz** | Adapter nur Loopback (`require_loopback_url`) – eine Cloud gibt es nicht, also auch keinen Weg dorthin | Station 5 schickt an eine Cloud; heute nur `simuliert`, letzte Sperre vor der Tür (kein Originalwert im Paket) |
| **Entscheidungen** | eine Quelle (`desk/decisions.py`), drei Wege, eine Antwortroute | eigener `ApprovalStore` mit TTL (nach SEDRAs H11 gebaut), eigene Antwort |
| **Logbuch** | Audit-Kette, Hashes verkettet | eigenes Logbuch: Hashes, Regel-IDs, Zählungen – **nie Text** |

**Der Befund in einem Satz:** SEDRA bewacht, *ob* etwas getan werden darf; das GateWay bewacht, *was* dabei hinausgeht. Beides
ist nötig, keins ersetzt das andere – und **SEDRA hat heute keinen Inhaltsschutz.** Jeder Agentenaufruf, jedes Gespräch, jeder
Kandidat geht ungeprüft ans Modell. Lokal ist das verschmerzbar; sobald irgendein Weg nach draußen existiert, nicht mehr.

## 2. Was deshalb in SEDRA kommt – nicht ins Modul

| Nr. | Was | Wo | Warum hier |
|---|---|---|---|
| **S1** | **Der Inhaltsschutz wird Teil des Kerns.** `ModelGuard` (Scan, Policy, Pseudonymisierung, Antwortprüfung) zieht nach `guppi_runtime/core/content_guard.py`; `b6core` kommt als geprüfter Fremdcode mit (`B6CORE_HERKUNFT.sha256`). | `core/` | Ein Schutz, der nur in einem Modul lebt, schützt nur dieses Modul. |
| **S2** | **`ModelRouter.chat` ruft ihn bei jedem Aufruf.** Vorher: Scan und Policy; nachher: Antwortprüfung. Es gibt keinen Aufruf am Guard vorbei – ein Test setzt einen Adapter ein und zählt. | `models/router.py` | Das ist *die eine Stelle*; alles andere wäre ein zweiter Weg. |
| **S3** | **Entscheidungen des Inhaltsschutzes sind SEDRA-Entscheidungen.** `REVIEW` wird ein Gate mit Inhaltsbindung (Hash des Aufrufs), beantwortet wie jede andere; der eigene `ApprovalStore` entfällt. | `desk/decisions.py` | Regel 2: ein Ort. |
| **S4** | **Sein Logbuch ist die Audit-Kette.** Die Ereignisse (`SG_*`) gehen in `audit.append`, mit denselben Feldern, ohne Text. | `core/audit.py` | Eine Kette, ein Nachweis. |
| **S5** | **Der Modus steuert die Schärfe.** Sandbox = alle Gruppen scharf; Beobachten = beobachten, nur `ALWAYS` scharf; Vertraut = beobachten. Was den Rechner verlässt, ist **immer** scharf – das ist keine Einstellung. | `desk/boundaries.py` | Der Captain stellt schon heute an genau einer Stelle ein, wie misstrauisch SEDRA ist. Ein zweiter Schalter wäre ein zweiter Ort. |
| **S6** | **Ein Cloud-Adapter ist ein Adapter, der die Netzgrenze kreuzt.** `require_loopback_url` bleibt für lokale; ein Cloud-Adapter darf nur registriert werden, wenn er die Grenze `netz` deklariert – jeder Aufruf kreuzt sie (Regel 7: einmal · ändern · ablehnen) **und** geht durch S2. Bis Anbieter, Vertrag und Schlüssel stehen, gibt es nur den simulierten. | `models/`, `desk/boundaries.py` | Damit kreuzt zum ersten Mal ein Verb der Oberfläche die Netzgrenze – und zwar das wichtigste. |
| **S7** | **Die Kostengrenze zählt die Hilfsaufrufe.** Bis 20.000 je Vorgang gehen über `ModelRouter.chat`; damit sieht sie das Guppy-Meter, und die Kostengrenze fragt, wenn ein Vorgang teurer wird als das Doppelte der bisher teuersten Aufgabe. | `desk/boundaries.py` | Nichts läuft an der Kostengrenze vorbei. |

**Was SEDRA damit gewinnt – auch ohne GateWay:** jeder Modellaufruf ist auf Geheimnisse, Anweisungen an die KI und Personenbezug
geprüft, im Modus Sandbox scharf, sonst beobachtet und sichtbar im Werkzeug `schutz`. Das ist die Antwort auf „SEDRA sicherer
machen“: nicht ein Modul mehr, sondern ein Schutz an der einen Stelle.

## 3. Wie das GateWay dann darauf sitzt

| Nr. | Was | Wo |
|---|---|---|
| G1 | `sedra_gateway` (Einlesen, Vorgang, Triage, Vorgaben) kommt als `guppi_runtime/gateway/`. `guard.py` entfällt zugunsten von S1; `desk.py` wird die Andockstelle `desk/gateway_vorgang.py`. | Paket |
| G2 | Routen `/api/gateway/*` und `/api/guard/*` im Vermittler; Vorgänge und Ergebnisse unter `local_config/gateway/`. Objekttyp `gateway` wird Vertragstyp (dann darf die Palette ihn kennen). | `uix_server.py`, `desk/` |
| G3 | Die Freigabe eines Vorgangs ist ein Gate `kind: gateway_release` mit Inhaltsbindung: Prüfsumme der Vorgaben, der Policy und **jeder Einheit** (ID, Stufe, Hash des Ausgehenden). Ändert sich eine Einheit, passt die Freigabe nicht mehr (ihr Test, übernommen). | `desk/decisions.py` |
| G4 | Der Versand (Station 5) ist ein Verb des Objekts `gateway` mit Deckungsprüfung vor dem Gate (`actions._boundary_first('netz', …)`) – wie *Kandidat übernehmen* für `projekt`. | `desk/actions.py` |
| G5 | Die Werkzeuge `gateway` und `schutz` werden **CORE** im Paket (nicht mehr fremd), behalten ihren Code; `schutz` liest `/api/guard/status` aus S1 und zeigt damit den Inhaltsschutz **für ganz SEDRA**, nicht nur fürs GateWay. | `uix/tools/` |
| G6 | Die 88 Tests ziehen mit; dazu neue: *jeder Modellaufruf geht durch den Inhaltsschutz*, *ein Cloud-Adapter ohne Netzgrenze lässt sich nicht registrieren*, *Versand ohne bestätigte Grenzen bleibt stehen*, *die Freigabe stirbt, wenn eine Einheit sich ändert*. | `tests/` |

## 4. Was bleibt, wie es ist – bewusst

- **Pseudonymisierung ist keine Anonymisierung** (B6 KNOWN_LIMITS). Welche Daten mit welcher Rechtsgrundlage an einen Anbieter
  dürfen, entscheidet die Firma mit ihrem Datenschutzbeauftragten. SEDRA macht die Entscheidung sichtbar und bindet sie; es
  trifft sie nicht. Das steht im Werkzeug, nicht nur hier.
- **Die Cloud bleibt simuliert**, bis Anbieter, Auftragsverarbeitungsvertrag und Schlüssel da sind. Der echte Adapter ist ein
  eigener, kleiner Build – mit derselben Signatur, hinter derselben Grenze.
- **Die KI-Attrappe** der Lieferung erkennt Namen aus einer Liste; ein echtes Modell findet mehr *und* erfindet mehr. Deshalb
  bleibt die Belegpflicht: ein KI-Fund zählt nur, wenn er wörtlich im Text steht.

## 5. Bauplan

| Build | Inhalt | Abnahme |
|---|---|---|
| **16** | S1–S5: Inhaltsschutz im Kern, am Router, als Entscheidung, in der Kette, über den Modus. **Kernänderung** – mit einem Test je Zusage und der vollen Suite. | jeder Modellaufruf geprüft; Suite grün; `schutz` zeigt den Zustand |
| **17** | G1–G5: das GateWay als Teil des Pakets, Routen, Vorgänge, Freigabe als Gate, Werkzeuge CORE. | Musterbestand der Lieferung läuft durch: 196 Einheiten, dieselben Zahlen wie in ihrem §5 |
| **18** | S6, S7, G4: der simulierte Cloud-Adapter hinter der Netzgrenze; Versand als Verb; Kostengrenze sieht die Hilfsaufrufe. | erster Versand kreuzt die Grenze „netz“ mit *einmal · ändern · ablehnen* |

Vor Build 16 lese ich `policy.py` und `scan.py` ganz, nicht nur die Schnittstelle – ein Inhaltsschutz, den man übernimmt, ohne
jede Regel zu kennen, ist keiner.
