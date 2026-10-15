"""Tests never start this PC's programs: nvidia-smi, LM Studio's lms, powercfg, PowerShell.

Every test module does `from host_isolation import setUpModule, tearDownModule`. While a module runs, the GUPPI modules that would
start such a program see a missing program instead (as on a PC without it), and hardware detection reports one fixed GPU. Only the
names inside those GUPPI modules are replaced, never the global subprocess/shutil: a test that patches for example
`guppi_runtime.hardware_manager.collector.subprocess.run` itself still works.

Why (2026-10-03): with the real programs, results and run time depended on the PC (LM Studio's CLI may wait up to 30 s, a busy GPU
or another chat's model changes what nvidia-smi says), and 19 tests started the real lms.exe 38 times per suite run.
"""
import shutil
from types import SimpleNamespace
from unittest import mock

# Matches the GUPPI PC (one 12 GB NVIDIA card), so hardware classes and model profiles stay as they were measured there.
TEST_GPU = {'vendor': 'NVIDIA', 'name': 'Test GPU (host_isolation)', 'vram_gb': 12.0}


def _no_program(*args, **kwargs):
    raise FileNotFoundError('host program disabled in tests (host_isolation)')


def _patches():
    return [
        mock.patch('guppi_runtime.hardware._nvidia', side_effect=lambda: dict(TEST_GPU)),
        mock.patch('guppi_runtime.hardware_manager.collector.shutil', SimpleNamespace(which=lambda *a, **k: None, disk_usage=shutil.disk_usage)),
        mock.patch('guppi_runtime.hardware_manager.collector.subprocess', SimpleNamespace(run=_no_program)),
        mock.patch('guppi_runtime.hardware_manager.power.subprocess', SimpleNamespace(run=_no_program)),
        mock.patch('guppi_runtime.models.runtime_control.shutil', SimpleNamespace(which=lambda *a, **k: None)),
    ]


_active = []


def setUpModule():
    for p in _patches():
        p.start(); _active.append(p)


def tearDownModule():
    while _active:
        _active.pop().stop()
