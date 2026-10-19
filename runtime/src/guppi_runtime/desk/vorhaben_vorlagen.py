"""Vorlagen für Vorhaben mit Stufen (19.10.2026, Wunsch Klaus: die Paperclip-Shell für mehrstufige Arbeit nutzbar machen).

Eine Vorlage ist nur Text: ein Titel, ein Satz, und die Stufen, die ein solches Vorhaben üblicherweise geht. Sie legt nichts an
und führt nichts aus – `POST /api/intent/create {vorlage: id}` macht daraus ein Vorhaben mit genau diesen Stufen, und erst
„Aufgabe daraus machen“ an einer Stufe beginnt den gewohnten Weg (Plan, Gates, Ausführung). Die Texte je Stufe sind das, was
SEDRA als Auftrag bekommt, wenn die Stufe zur Aufgabe wird – sie sagen, was herauskommen soll, nicht wie.

Keine Aussage zu Rechten, Steuern oder Plattformregeln: wo eine Stufe so etwas berührt, steht „prüfen“, nicht „erledigt“."""
from __future__ import annotations

VORLAGEN = [
    {
        'id': 'leer',
        'titel': 'Ohne Vorlage',
        'satz': 'Ein Vorhaben ohne vorgegebene Stufen – die Stufen kommen aus dem Gespräch oder von Hand.',
        'stufen': [],
    },
    {
        'id': '3d-assets-shop',
        'titel': '3D-Assets über einen Etsy-Shop vertreiben',
        'satz': 'Ein Werkflow von der Idee bis zum laufenden Verkauf digitaler 3D-Assets (STL/OBJ/Blend) über einen Etsy-Shop.',
        'stufen': [
            {'name': 'Nische und Angebot festlegen',
             'text': 'Zielgruppe, Asset-Art (z. B. druckbare Figuren, Spiel-Props, Architektur) und drei erste Produkte bestimmen. '
                     'Ergebnis: eine Liste der drei Produkte mit je einem Satz, warum jemand sie kauft, und eine Preisspanne je Produkt.'},
            {'name': 'Assets modellieren',
             'text': 'Für jedes der drei Produkte ein Modell in der vereinbarten Software erstellen, mit sauberer Topologie und Maßen. '
                     'Ergebnis: je Produkt die Quelldatei und eine Exportliste (Formate, Einheiten, Polygonzahl).'},
            {'name': 'Prüfen und exportieren',
             'text': 'Jedes Modell prüfen (geschlossen, Normalen, Maßstab, Druckbarkeit, wo zutreffend) und in die Verkaufsformate exportieren. '
                     'Ergebnis: je Produkt eine Prüfliste mit Ja/Nein und die Exportdateien in einem Ordner je Produkt.'},
            {'name': 'Vorschaubilder rendern',
             'text': 'Je Produkt drei bis fünf Vorschaubilder (Hauptansicht, Details, Maßstab) in einheitlichem Stil rendern. '
                     'Ergebnis: Bilder in 2000 px Breite je Produkt, benannt nach Produkt und Ansicht.'},
            {'name': 'Listing-Texte schreiben',
             'text': 'Je Produkt Titel, Beschreibung, 13 Schlagwörter und die Lizenzangabe (private Nutzung, gewerblich?) formulieren. '
                     'Ergebnis: eine Tabelle Produkt × Titel × Beschreibung × Schlagwörter × Lizenz, zur Prüfung durch den Captain.'},
            {'name': 'Shop einrichten und Preise setzen',
             'text': 'Shop-Grundlagen zusammenstellen: Name, Banner-Vorgabe, Richtlinien, Versand (digital), Preise je Produkt aus der Spanne. '
                     'Ergebnis: eine Prüfliste für das Anlegen im Shop; Steuer- und Rechtsfragen als offene Punkte zum Prüfen markieren.'},
            {'name': 'Veröffentlichen und prüfen',
             'text': 'Die drei Listings mit Bildern, Texten und Dateien veröffentlichen und einmal als Käufer durchgehen (Kauf, Download). '
                     'Ergebnis: eine Prüfliste je Listing mit Ja/Nein und die Liste der Fehler, die dabei auffielen.'},
            {'name': 'Verkauf betreuen und auswerten',
             'text': 'Nach zwei Wochen: Aufrufe, Favoriten, Verkäufe und Fragen je Produkt zusammenstellen und zwei Verbesserungen vorschlagen. '
                     'Ergebnis: eine kurze Auswertung mit Zahlen je Produkt und zwei begründeten nächsten Schritten.'},
        ],
    },
    {
        'id': 'kundenanfrage',
        'titel': 'Kundenanfrage beantworten',
        'satz': 'Der Weg des KI Gateway für eine schriftliche Kundenanfrage: prüfen, entwerfen, freigeben, versenden.',
        'stufen': [
            {'name': 'Anfrage erfassen und prüfen', 'text': 'Die Anfrage ablegen und mit dem Schutz prüfen: welche Merkmale, welcher Weg. Ergebnis: die Prüfung mit Weg und Merkmalen.'},
            {'name': 'Entwurf erzeugen', 'text': 'Aus Anfrage und freigegebenen Unternehmensfakten einen Antwortentwurf erzeugen. Ergebnis: der Entwurf mit Kennzeichnung „KI-Entwurf“.'},
            {'name': 'Fachlich prüfen und freigeben', 'text': 'Den Entwurf fachlich prüfen, korrigieren und freigeben. Ergebnis: die geprüfte Fassung mit Vermerk, wer geprüft hat.'},
            {'name': 'Versenden und ablegen', 'text': 'Die Antwort versenden und mit Anfrage und Prüfung ablegen. Ergebnis: der abgelegte Vorgang.'},
        ],
    },
]


def liste():
    """Die Vorlagen für die Oberfläche: Kennung, Titel, Satz und die Zahl der Stufen, dazu die Stufen selbst (nur Text)."""
    return [{'id': v['id'], 'titel': v['titel'], 'satz': v['satz'], 'stufen': [dict(s) for s in v['stufen']]} for v in VORLAGEN]


def finde(vorlage_id):
    return next((v for v in VORLAGEN if v['id'] == str(vorlage_id or '')), None)
