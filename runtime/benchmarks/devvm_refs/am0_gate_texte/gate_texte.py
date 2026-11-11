RAHMEN = 'läuft abgeschottet in einem eigenen Rahmen: ohne Token, ohne Netz, ohne Zugriff auf die Seite'
GRENZE = 'nicht begrenzt: Rechenzeit und Speicher im Browser'
SHELL_CODE = 'ohne eigenen Code und ohne eigenes CSS – die Oberfläche baut der Rahmen des Vertrags (ui/frame.js)'
SHELL_ROUTEN = 'Routen: nur die festen Routen des Rahmens'


def leserouten_text(routen):
    gesehen = []
    if isinstance(routen, list):
        for r in routen:
            if isinstance(r, str) and r.startswith('GET ') and len(r) > 4:
                pfad = r[4:]
                if pfad not in gesehen:
                    gesehen.append(pfad)
    if not gesehen:
        return 'Leserouten: keine'
    return 'Leserouten: ' + ', '.join(gesehen)


def _funde(funde):
    if not isinstance(funde, list):
        return []
    return [f for f in funde if isinstance(f, str) and f]


def risiken_werkzeug(routen, funde=None):
    return [RAHMEN, GRENZE, leserouten_text(routen)] + _funde(funde)


def risiken_shell(funde=None):
    return [SHELL_CODE, SHELL_ROUTEN] + _funde(funde)


def risiken(art, routen=None, funde=None):
    if art == 'tool':
        return risiken_werkzeug(routen, funde)
    if art == 'shell':
        return risiken_shell(funde)
    raise ValueError('art')
