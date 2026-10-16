# Regelwerk: Datenkategorien und Cloudsperre, v0.1 (PROPOSED, 15.10.2026)

**Anlass:** Entscheidung Klaus (Chat 15.10. 14:08, Q2): „Wir gehen praktisch aus Firmensicht daran: Wir haben Daten, die wir laut DSGVO und EU AI Act nicht in die Cloud geben dürfen. Mit diesen arbeiten wir erstmal als verbindliche Regeln, so ist es einheitlich.“ Gilt für den Prototyp GUPPI/SEDRA und – nach Ticket – für die B6-Linie (Option C: eine Policy). Ersetzt die Übergangsfrage P4 (Quellenklasse).
**Status:** Q3. Die Zuordnung zu Rechtsnormen ist eine **fachliche Annahme des Teams**, keine Rechtsprüfung. Keine Aussage „DSGVO-konform“ oder „AI-Act-konform“. Der Datenschutzreview (Vorgehen v2 §8, ULD) steht aus; bis dahin gilt die strengere Lesart.
**Grundsatz:** Was in einer gesperrten Kategorie liegt, verlässt den Rechner nicht – auch nicht pseudonymisiert, weil pseudonymisierte Daten personenbezogen bleiben (Erwägungsgrund 26 DSGVO; Vorgehen v2 §1 und §8). Cloud ist im Prototyp ohnehin nur simuliert; die Regel sagt, was auch bei einer echten Cloud nie dorthin dürfte.

## 1. Die Regeltabelle

| Regel | Kategorie | Merkmal (klassen.py) | Bezug (Annahme, zu prüfen) | Lokal | Cloud | Review |
|---|---|---|---|---|---|---|
| R-01 | Personenbezogene Daten (Name, E-Mail, Telefon, Kundennummer, Adresse) | P01 | Art. 4 Nr. 1, Art. 6 DSGVO; ohne Rechtsgrundlage, AVV und Drittlandprüfung kein Cloudweg | ja | **nein** (bis Rechtsgrundlage + AVV dokumentiert; dann nur pseudonymisiert) | nein |
| R-02 | Besondere Kategorien (Gesundheit, Religion, Gewerkschaft, Sexualität, Herkunft, Biometrie, Genetik) | P02 | Art. 9 DSGVO | ja, nur nach Review | **nie** | ja |
| R-03 | Strafrechtliche Daten | P03 | Art. 10 DSGVO | ja, nur nach Review | **nie** | ja |
| R-04 | Amtliche Kennungen (Steuer-ID, Ausweis, Sozialversicherung) | P04 | § 139b AO, DSGVO Art. 87; hohes Missbrauchsrisiko | ja, nur nach Review | **nie** | ja |
| R-05 | Minderjährige | V01 | Art. 8 DSGVO, Erwägungsgrund 38 | ja, nur nach Review | **nie** | ja |
| R-06 | Bankverbindung, Kartendaten | F01, F02 | Vertraulichkeit, PCI-DSS (nicht DSGVO) | ja | **nie** | nein |
| R-07 | Kartendaten mit Prüfwert, Zugangsdaten, Schlüssel | F03, S01 | Hard Block (B6 P0-10a §7) | **nein** | **nie** | – (nicht übersteuerbar) |
| R-08 | Anweisungen an die KI, versteckte Zeichen im Dokument/Anhang | S02 (Dokument) | Hard Block | **nein** | **nie** | – |
| R-09 | Anweisungen an die KI in der eigenen Anfrage | S02 (Anfrage) | Entscheidung P3 (15.10.) | ja, nur nach Review, ohne Platzhalter | **nie** | ja |
| R-10 | Geschäftsgeheimnis, Kalkulation | G01 | GeschGehG § 2 (nicht DSGVO) | ja, nur nach Review (TC-011) | **nie** | ja |
| R-11 | Vertraulichkeitsvereinbarung | G02 | Vertrag | ja | **nie** | nein |
| R-12 | Rechtsstreit, laufendes Verfahren | R01 (von Hand) | Verschwiegenheit | ja | **nie** | nein |
| R-13 | Hochrisiko-Anwendungskontext (Personal, Kredit, Bildung, Strafverfolgung) | **neu: A01**, von Hand | EU AI Act Anhang III (Annahme; Rolle Anbieter/Betreiber offen) | ja, nur nach Review | **nie** | ja |
| R-14 | KI-Kennzeichnung des Entwurfs | – | EU AI Act Art. 50 | Entwurf trägt Hinweis „KI-Entwurf, menschlich geprüft“ | – | – |
| R-15 | Keine Kategorie getroffen, Scan vollständig | – | – | ja | ja (simuliert) | nein |
| R-16 | Scan unvollständig, Datei unlesbar, Regelkonflikt | UNCLASSIFIED | fail-closed (Projektanweisung) | nein | nein | ja |

**Folge für die Matrix:** `CLOUD_AFTER_PSEUDONYMIZATION` entfällt im Prototyp, bis R-01 eine dokumentierte Rechtsgrundlage und einen AVV hat. `CLOUD_ALLOWED` nur bei R-15. `AUTO_APPROVED` nur bei R-15, R-06, R-11, R-12 (lokal, eindeutig). Alles andere Review oder Block. Das ist die Antwort auf P4: „eindeutig“ = keine gesperrte Kategorie oder nur lokal ohne Review-Pflicht.

## 2. Was sich gegenüber `sedra-gateway-1.0` ändert

| Fall | heute | nach Regelwerk v0.1 |
|---|---|---|
| P01 (SK1) | lokal AUTO, Cloud nach Pseudonymisierung | **nur lokal**, AUTO; Cloudweg erst mit Rechtsgrundlage (Registerfeld) |
| SK0 | lokal oder Cloud, AUTO | unverändert |
| A01 Hochrisiko-Kontext | nicht vorhanden | neues manuelles Merkmal, Review |
| Entwurf | kein Hinweis | KI-Kennzeichnung im Entwurf und in der Anzeige |
| Policyversion | `sedra-gateway-1.0` | `b6-datenregeln-0.1` (gemeinsamer Name für beide Linien) |

Vorgehen v2 §5 nannte für „intern, normaler Personenbezug“ den Pfad „Cloud nach Pseudonymisierung – nur mit Rechtsgrundlage, AVV und Drittlandprüfung, sonst lokal“. Da keines davon vorliegt, ist „sonst lokal“ der Stand. Die Regel ist damit keine Verschärfung des Konzepts, sondern seine Anwendung.

## 3. Umsetzung (Vorschlag, Ticket B6-G-03 neu gefasst)
1. `gateway/klassen.py`: Tabelle `MERKMALE` um A01 (manuell) ergänzen; Matrix nach Abschnitt 1; `POLICY_VERSION = 'b6-datenregeln-0.1'`; Konstante `RECHTSGRUNDLAGE_CLOUD = False` (Schalter nur per Registereintrag, nicht per UI).
2. `gateway/vorgang.py`: Entwurf bekommt Kopfzeile „KI-Entwurf (lokales Modell), menschlich geprüft: nein/ja“; R-14.
3. Werkzeug `gateway`: Kästchen A01 neben R01; Regelnummer je Grund anzeigen („R-02: besondere Kategorie“), damit der Nutzer die Regel sieht (Vorgehen v2 §4, Mitteilung an den Nutzer).
4. Tests: ein Test je Regelzeile R-01…R-16; bestehende Matrixtests anpassen (P01 ohne Cloud); Korpus-Adapter liest die neue Policyversion.
5. Dokument: dieses Regelwerk als `docs/REGELWERK_…` in den Prototyp, als Quelle für die B6-Linie (Ticket B6-P1-03/04).

**Nicht enthalten:** Rechtsgrundlagen-Register, AVV, Drittlandprüfung, Rollen (Anbieter/Betreiber), DSFA – alles Datenschutzreview.

## 4. Entscheidung
- [ ] Regelwerk v0.1 als verbindlich für den Prototyp (Klaus) · [ ] Ticket B6-G-03 (Umsetzung 1–5) freigeben (Klaus) · [ ] Übernahme in die B6-Linie nach 20.10. (David)
- Offen für den Datenschutzreview: Normbezüge R-01…R-05, R-13; Rolle nach AI Act; Fristen.
