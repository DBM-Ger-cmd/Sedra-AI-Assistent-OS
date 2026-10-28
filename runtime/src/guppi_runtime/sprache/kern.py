"""Aufnahme im Kern (19.10.2026): der Rechner nimmt auf – nicht die Seite. Ein Shell-Wechsel lädt nur die Oberfläche neu; die Aufnahme
läuft im Kern weiter und die Leiste holt den Stand wieder ab. Mikrofon über sounddevice (PortAudio), 16 kHz, mono, 16 Bit.
Rohes PCM geht laufend in `<id>.pcm` der Ablage; beim Stopp wird daraus ein WAV-Record (aufnahmen.Store), die Rohdatei fällt weg.
Verwerfen löscht Rohdatei und Record. Ohne Mikrofon sagt der Kern das – er erfindet keine Aufnahme."""
from __future__ import annotations

import math
import threading
import time
import wave
from pathlib import Path

from . import aufnahmen as au

RATE = 16000
KANAELE = 1
BREITE = 2  # Bytes je Probe (int16)


def pegel_von(werte):
    """Anzeige 0..1 in dB nach dem Spitzenwert des Blocks: -60 dB (Stille) bis 0 dB (Vollaussteuerung). Spitzen zeigen sich so
    sofort – Sprache ist kurz laut und zwischen den Worten leise, der Mittelwert hätte sie verschluckt."""
    if not len(werte): return 0.0
    spitze = max(abs(x) for x in werte) / 32768.0
    if spitze <= 0: return 0.0
    return max(0.0, min(1.0, (20 * math.log10(spitze) + 60) / 60))


def _sd_oeffnen(callback, rate):
    """Der echte Eingang: sounddevice, roh (RawInputStream) – ohne numpy, das die portable Umgebung nicht mitbringt.
    Der Callback bekommt einen Puffer aus int16-Proben. Im Test wird diese Stelle ersetzt."""
    import sounddevice as sd
    return sd.RawInputStream(samplerate=rate, channels=KANAELE, dtype='int16', callback=callback)


QUELLEN = ('mikrofon', 'pc_ton')   # pc_ton: was der Rechner über den Standard-Ausgang abspielt (WASAPI-Loopback)


class _PcTonStrom:
    """Der Ton des Rechners (Windows, WASAPI-Loopback über PyAudioWPatch) als 16 kHz mono int16. Der Ausgang liefert nur Blöcke, wenn etwas
    abgespielt wird; Mischen auf mono und Umrechnen der Rate geschehen hier, ohne numpy. Die Stücke gehen an denselben Callback wie das Mikrofon."""

    def __init__(self, callback, rate):
        import pyaudiowpatch as pa
        self.pa = pa.PyAudio()
        try:
            geraet = self.pa.get_default_wasapi_loopback()
        except Exception:
            self.pa.terminate()
            raise
        self.kanaele = max(1, int(geraet['maxInputChannels']))
        self.quelle_rate = int(geraet['defaultSampleRate'])
        self.rate, self.callback, self.pos, self._weiter = rate, callback, 0.0, pa.paContinue
        self.strom = self.pa.open(format=pa.paInt16, channels=self.kanaele, rate=self.quelle_rate, input=True,
                                  input_device_index=geraet['index'], frames_per_buffer=1024, stream_callback=self._block)
        self.name = geraet['name']

    def _block(self, daten, frames, _zeit, _status):
        import array
        a = array.array('h'); a.frombytes(daten)
        k = self.kanaele
        mono = a if k == 1 else [sum(a[i:i + k]) // k for i in range(0, len(a) - k + 1, k)]
        schritt = self.quelle_rate / self.rate
        aus = array.array('h')
        pos = self.pos
        while pos < len(mono):
            aus.append(mono[int(pos)])
            pos += schritt
        self.pos = pos - len(mono)
        if len(aus):
            self.callback(aus.tobytes(), len(aus), None, None)
        return (None, self._weiter)

    def start(self):
        self.strom.start_stream()

    def stop(self):
        try: self.strom.stop_stream()
        except Exception: pass

    def close(self):
        try: self.strom.close()
        finally: self.pa.terminate()


def _pc_oeffnen(callback, rate):
    return _PcTonStrom(callback, rate)


class Kern:
    def __init__(self, store, oeffnen=None, oeffnen_pc=None):
        self.store = store
        self.oeffnen = oeffnen or _sd_oeffnen
        self.oeffnen_pc = oeffnen_pc or _pc_oeffnen
        self.lock = threading.RLock()   # stand() wird aus start/pause/... heraus gerufen
        self.lauf = None  # dict: id, titel, sprache, strom, datei, frames, stuecke, pause, pegel, start, pausiert, pause_seit

    # ---------------------------------------------------------------- Stand
    def stand(self):
        with self.lock:
            l = self.lauf
            if not l: return {'status': 'aus'}
            return {'status': 'pause' if l['pause'] else 'laeuft', 'voll': l['voll'], 'id': l['id'], 'titel': l['titel'], 'sprache': l['sprache'], 'quelle': l['quelle'],
                    'sekunden': round(self._sekunden(l), 1), 'pegel': round(l['pegel'], 3), 'stuecke': l['stuecke'], 'groesse': l['frames'] * BREITE * KANAELE}

    def _sekunden(self, l):
        jetzt = l['pause_seit'] if l['pause'] else time.monotonic()
        return max(0.0, jetzt - l['start'] - l['pausiert'])

    # ---------------------------------------------------------------- Aufnehmen
    def start(self, titel, sprache, now, quelle='mikrofon'):
        with self.lock:
            if self.lauf: raise ValueError('laeuft_schon')
            if quelle not in QUELLEN: raise ValueError('quelle_unbekannt')
            a = self.store.beginnen(titel, 'audio/wav', sprache, now)
            datei = Path(self.store.dir) / (a['id'] + '.pcm')
            l = {'id': a['id'], 'titel': a['titel'], 'sprache': sprache, 'datei': datei, 'frames': 0, 'stuecke': 0, 'pause': False,
                 'pegel': 0.0, 'start': time.monotonic(), 'pausiert': 0.0, 'pause_seit': None, 'strom': None, 'f': datei.open('wb'), 'voll': False, 'quelle': quelle}

            def aufnehmen(indata, frames, _zeit, _status):
                if l['pause'] or l['f'] is None: return
                if (l['frames'] + frames) * BREITE * KANAELE > au.MAX_GROESSE: l['voll'] = True; return   # Grenze je Aufnahme: nichts wächst über das Limit
                roh = bytes(indata)
                l['f'].write(roh)
                l['frames'] += frames
                l['stuecke'] += 1
                werte = memoryview(roh).cast('h')
                l['pegel'] = pegel_von(werte)

            try:
                strom = (self.oeffnen_pc if quelle == 'pc_ton' else self.oeffnen)(aufnehmen, RATE)
                strom.start()
            except ImportError:
                l['f'].close(); datei.unlink(missing_ok=True); self.store.loeschen(a['id'])
                raise ValueError('kein_mikrofon: Das Paket PyAudioWPatch fehlt auf diesem Rechner (pip install PyAudioWPatch), danach die Runtime neu starten.' if quelle == 'pc_ton'
                                 else 'kein_mikrofon: Das Paket sounddevice fehlt auf diesem Rechner (pip install sounddevice), danach die Runtime neu starten.')
            except Exception as exc:
                l['f'].close(); datei.unlink(missing_ok=True); self.store.loeschen(a['id'])
                raise ValueError(('kein_mikrofon: Kein Ausgabegerät zum Mitschneiden bereit (' if quelle == 'pc_ton' else 'kein_mikrofon: Kein Eingabegerät bereit (') + str(exc)[:160] + ').')
            l['strom'] = strom
            self.lauf = l
            return self.stand()

    def pause(self):
        with self.lock:
            l = self._lauf()
            if not l['pause']: l['pause'] = True; l['pause_seit'] = time.monotonic()
            return self.stand()

    def weiter(self):
        with self.lock:
            l = self._lauf()
            if l['pause']:
                l['pausiert'] += time.monotonic() - l['pause_seit']; l['pause'] = False; l['pause_seit'] = None
            return self.stand()

    def stopp(self, now):
        with self.lock:
            l = self._lauf()
            sek = self._sekunden(l)
            self._schliessen(l)
            if l['frames'] == 0:                       # nichts gehört: kein leerer Record bleibt zurück
                l['datei'].unlink(missing_ok=True); self.store.loeschen(l['id']); self.lauf = None
                raise ValueError('aufnahme_leer')
            wav = Path(self.store.dir) / (l['id'] + '.wav')
            with wave.open(str(wav), 'wb') as w:
                w.setnchannels(KANAELE); w.setsampwidth(BREITE); w.setframerate(RATE)
                with l['datei'].open('rb') as roh:
                    while True:
                        chunk = roh.read(1 << 20)
                        if not chunk: break
                        w.writeframes(chunk)
            l['datei'].unlink(missing_ok=True)
            a = self.store.get(l['id'])
            a['groesse'] = wav.stat().st_size; a['stuecke'] = l['stuecke']
            self.store.schreiben(a)
            self.lauf = None
            return self.store.beenden(l['id'], round(sek, 2), now)

    def verwerfen(self):
        with self.lock:
            l = self._lauf()
            self._schliessen(l)
            l['datei'].unlink(missing_ok=True)
            self.store.loeschen(l['id'])
            self.lauf = None
            return {'status': 'aus'}

    # ---------------------------------------------------------------- Intern
    def _lauf(self):
        if not self.lauf: raise ValueError('keine_aufnahme')
        return self.lauf

    def _schliessen(self, l):
        try:
            if l['strom'] is not None:
                l['strom'].stop(); l['strom'].close()
        finally:
            if l['f'] is not None:
                l['f'].close(); l['f'] = None
