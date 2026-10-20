"""Ein Mikrofon für die Tests: der Kern bekommt einen Strom, der ohne Gerät Stücke liefert (16 kHz, mono, int16)."""
import threading
import time

import numpy as np


class FakeStrom:
    def __init__(self, cb):
        self.cb = cb
        self.laeuft = False

    def start(self):
        self.laeuft = True

        def lauf():
            while self.laeuft:
                self.cb(np.full(800, 500, dtype=np.int16).tobytes(), 800, None, None)
                time.sleep(0.05)
        threading.Thread(target=lauf, daemon=True).start()

    def stop(self):
        self.laeuft = False

    def close(self):
        pass


def installieren(hub):
    """Den Kern des Hubs auf das Fake-Mikrofon setzen; das echte Gerät bleibt in diesen Tests aus."""
    hub.sprache.kern.oeffnen = lambda cb, rate: FakeStrom(cb)
