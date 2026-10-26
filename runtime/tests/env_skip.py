"""Tests that need this particular PC (Windows, the engines and model files, dulwich, enough RAM) skip themselves elsewhere, with the reason.

Why (2026-10-14): the full suite on a Linux container showed 34 red tests, all of them environment, none of them a defect. Red must mean broken.
A module that cannot run at all calls `need_dulwich()` (and so on) at import time: unittest reports the whole module as skipped.
A single test uses the decorators."""
import importlib.util
import os
import sys
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]


def has_dulwich():
    return importlib.util.find_spec("dulwich") is not None


def has_numpy():
    return importlib.util.find_spec("numpy") is not None


def host_ram_gb():
    try:
        if sys.platform == "win32":
            import ctypes
            class Status(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            s = Status(); s.dwLength = ctypes.sizeof(Status); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
            return s.ullTotalPhys / 2 ** 30
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2 ** 30
    except Exception:
        return None


def pc_files_present():
    return (RUNTIME.parent / "engines").is_dir() and (RUNTIME.parent / "workspace").is_dir()


# ---- module level: the whole file cannot run here
def need_dulwich():
    if not has_dulwich(): raise unittest.SkipTest("dulwich fehlt (requirements.txt; auf dem GUPPI-PC im .venv) – DevVM-Tests übersprungen")


def need_numpy():
    if not has_numpy(): raise unittest.SkipTest("numpy fehlt (nur der Test baut damit Audiodaten; die .venv der Runtime hat es nicht) – Sprache-Kern-Test übersprungen")


def need_windows():
    if sys.platform != "win32": raise unittest.SkipTest("nur unter Windows (PowerShell, Laufwerkspfade, GetTickCount64)")


# ---- single tests
needs_dulwich = unittest.skipUnless(has_dulwich(), "dulwich fehlt (requirements.txt; auf dem GUPPI-PC im .venv)")
needs_windows = unittest.skipUnless(sys.platform == "win32", "nur unter Windows (PowerShell, Laufwerkspfade, GetTickCount64)")
needs_pc_files = unittest.skipUnless(pc_files_present(), "braucht engines/ und workspace/ des GUPPI-PCs (Modelle, llama.cpp)")


def needs_ram(gb):
    ram = host_ram_gb()
    return unittest.skipUnless(ram is None or ram >= gb, f"braucht mindestens {gb} GB RAM (hier {ram:.0f} GB)" if ram else "")
