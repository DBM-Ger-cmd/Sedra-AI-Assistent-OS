"""Herkunft einer Antwort auf eine Freigabe (SPEC_HARNESS_SHELL_v1 HS-28/HS-29; G2 Stufe 3 §5.4 S7, K14; G3 Stufe 3 N5).

Die HTTP-Wege, mit denen man eine Karte beantwortet, eine Aufgabe anlegt oder zurücknimmt, einen Vorarbeiter ernennt oder im Posteingang antwortet, sind
durch Token und Origin gesichert – das Token kennt nur der Browser des Captains. Ein Agent mit `befehl` oder einem Lauf könnte es aber aus der Prozessliste lesen
(die Adresse mit `#token` steht in der Befehlszeile des Browsers) und seine eigene Karte bestätigen. Darum prüft der Server zusätzlich, **wer** anfragt:
Er löst die Gegenstelle der TCP-Verbindung zur PID auf (Windows: `GetExtendedTcpTable`, ohne neue Abhängigkeit) und lehnt ab, wenn diese Prozess ein Nachkomme eines
Harness-Prozesses ist (`befehl`, Läufe – sie tragen sich in `REGISTER` ein und bleiben danach noch eine Stunde dort, damit auch abgelöste Kindprozesse erkannt werden).

Grenzen (ehrlich): Das schützt nicht gegen Prozesse außerhalb der Harness (das Terminal des Captains) und nicht, wenn die Auflösung scheitert – dann gilt nur die
Prüfung von Token und Origin, und der Server schreibt eine Warnung ins Audit (Entscheidung D-G5). Harness-Code (Vorbehalt): SEDRA ändert diese Datei nicht an sich selbst."""
from __future__ import annotations

import os
import socket
import subprocess
import threading
import time

NACHLAUF_S = 3600


class Register:
    """Die PIDs der Harness-Prozesse (befehl, Läufe): laufende und die der letzten Stunde, mit ihrer Startzeit gegen PID-Wiederverwendung."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._sperre = threading.Lock()
        self._eintraege = {}               # pid → {'start': Startzeit oder None, 'ende': None oder Zeit}

    def registrieren(self, pid, start=None):
        with self._sperre:
            self._eintraege[pid] = {'start': start if start is not None else startzeit(pid), 'ende': None}

    def austragen(self, pid):
        with self._sperre:
            if pid in self._eintraege:
                self._eintraege[pid]['ende'] = self._clock()

    def eintraege(self):
        """{pid: start} aller laufenden und der in den letzten NACHLAUF_S beendeten Harness-Prozesse; ältere werden vergessen."""
        jetzt = self._clock()
        with self._sperre:
            for pid in [p for p, e in self._eintraege.items() if e['ende'] is not None and jetzt - e['ende'] > NACHLAUF_S]:
                del self._eintraege[pid]
            return {pid: e['start'] for pid, e in self._eintraege.items()}


REGISTER = Register()


# ---------------------------------------------------------------- Betriebssystem (Windows mit ctypes, sonst best effort)
def prozess_tabelle():
    """{pid: ppid} aller Prozesse."""
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD),
                        ('th32DefaultHeapID', ctypes.c_size_t), ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                        ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', wintypes.LONG), ('dwFlags', wintypes.DWORD),
                        ('szExeFile', wintypes.WCHAR * 260)]

        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k32.Process32FirstW.argtypes = k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        snap = k32.CreateToolhelp32Snapshot(0x2, 0)
        if snap in (None, wintypes.HANDLE(-1).value):
            return {}
        tabelle = {}
        try:
            e = PROCESSENTRY32W()
            e.dwSize = ctypes.sizeof(e)
            ok = k32.Process32FirstW(snap, ctypes.byref(e))
            while ok:
                tabelle[int(e.th32ProcessID)] = int(e.th32ParentProcessID)
                ok = k32.Process32NextW(snap, ctypes.byref(e))
        finally:
            k32.CloseHandle(snap)
        return tabelle
    try:
        out = subprocess.run(['ps', '-A', '-o', 'pid=,ppid='], capture_output=True, text=True, timeout=10).stdout
        return {int(a): int(b) for a, b in (z.split() for z in out.splitlines() if z.strip())}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}


def startzeit(pid):
    """Die Startzeit eines Prozesses (Windows: GetProcessTimes) – oder None, wenn er nicht (mehr) lesbar ist."""
    if os.name != 'nt':
        return None
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        h = k32.OpenProcess(0x1000, False, int(pid))                    # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return None
        try:
            c, e, k, u = (wintypes.FILETIME() for _ in range(4))
            if not k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)):
                return None
            return (c.dwHighDateTime << 32) | c.dwLowDateTime
        finally:
            k32.CloseHandle(h)
    except Exception:
        return None


def tcp_besitzer(client_port, server_port):
    """Die PID des Prozesses, dem die Verbindung 127.0.0.1:client_port → :server_port gehört – oder None (nicht lesbar, kein Windows)."""
    if os.name != 'nt':
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class ROW(ctypes.Structure):
            _fields_ = [('state', wintypes.DWORD), ('lokal_adr', wintypes.DWORD), ('lokal_port', wintypes.DWORD), ('fern_adr', wintypes.DWORD),
                        ('fern_port', wintypes.DWORD), ('pid', wintypes.DWORD)]

        ip = ctypes.WinDLL('iphlpapi')
        ip.GetExtendedTcpTable.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL, wintypes.ULONG, ctypes.c_int, wintypes.ULONG]
        groesse = wintypes.DWORD(0)
        ip.GetExtendedTcpTable(None, ctypes.byref(groesse), False, socket.AF_INET, 5, 0)       # 5 = TCP_TABLE_OWNER_PID_ALL
        for _ in range(3):                                                                      # die Tabelle kann zwischen den Aufrufen wachsen
            puffer = ctypes.create_string_buffer(groesse.value + 4096)
            groesse = wintypes.DWORD(len(puffer))
            if ip.GetExtendedTcpTable(puffer, ctypes.byref(groesse), False, socket.AF_INET, 5, 0) == 0:
                break
        else:
            return None
        n = ctypes.c_ulong.from_buffer(puffer).value
        rows = (ROW * n).from_buffer(puffer, ctypes.sizeof(ctypes.c_ulong))
        for r in rows:
            if socket.ntohs(r.lokal_port & 0xFFFF) == client_port and socket.ntohs(r.fern_port & 0xFFFF) == server_port:
                return int(r.pid)
    except Exception:
        return None
    return None


# ---------------------------------------------------------------- die Prüfung
def stammt_von(pid, register_eintraege, tabelle, start_von=startzeit):
    """Ist `pid` ein registrierter Harness-Prozess oder ein Nachkomme eines solchen? Beim Hochklettern zählt ein noch lebender Vorfahre nur, wenn seine Startzeit
    zu der im Register passt (PID-Wiederverwendung); ein toter Vorfahre (nicht mehr in der Tabelle) zählt, wenn seine PID im Register steht."""
    gesehen = set()
    knoten = pid
    while knoten and knoten not in gesehen:
        gesehen.add(knoten)
        if knoten in register_eintraege:
            soll = register_eintraege[knoten]
            lebt = knoten in tabelle
            ist = start_von(knoten) if lebt else None
            if not lebt or soll is None or ist is None or soll == ist:
                return True
        if knoten not in tabelle:
            return False
        knoten = tabelle[knoten]
    return False


class Herkunft:
    """Die Prüfung, gerufen vom Server für die Antwort-Wege. Alles Betriebssystemnahe ist austauschbar (Tests)."""

    def __init__(self, register=REGISTER, tabelle=prozess_tabelle, besitzer=tcp_besitzer, start_von=startzeit, audit=None):
        self.register, self.tabelle, self.besitzer, self.start_von, self.audit = register, tabelle, besitzer, start_von, audit

    def pruefen(self, client_adresse, server_port):
        """{ok, grund?, warnung?, pid?}. `client_adresse` ist (host, port) der Verbindung."""
        try:
            pid = self.besitzer(int(client_adresse[1]), int(server_port))
        except Exception:
            pid = None
        if pid is None:
            out = {'ok': True, 'warnung': 'aufloesung_nicht_moeglich'}
            self._audit('HARNESS_HERKUNFT_UNGEPRUEFT', out)
            return out
        if stammt_von(pid, self.register.eintraege(), self.tabelle(), self.start_von):
            out = {'ok': False, 'grund': 'von_harness_prozess', 'pid': pid}
            self._audit('HARNESS_HERKUNFT_ABGELEHNT', out)
            return out
        return {'ok': True, 'pid': pid}

    def _audit(self, event, payload):
        if self.audit is not None:
            try: self.audit(event, payload)
            except Exception: pass
