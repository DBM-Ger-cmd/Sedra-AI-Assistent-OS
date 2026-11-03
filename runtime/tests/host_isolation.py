"""Tests never start this PC's programs: nvidia-smi, LM Studio's lms, powercfg, PowerShell.

Every test module does `from host_isolation import setUpModule, tearDownModule`. While a module runs, the GUPPI modules that would
start such a program see a missing program instead (as on a PC without it), and hardware detection reports one fixed GPU. Only the
names inside those GUPPI modules are replaced, never the global subprocess/shutil: a test that patches for example
`guppi_runtime.hardware_manager.collector.subprocess.run` itself still works.

`models/gpu_preflight` binds the real `subprocess.run` as default argument, so its probes are wrapped instead (2026-11-03): called with that
default they answer like a PC without PowerShell and with an empty card and never stop a process; a `run` passed in by a test is used as
before. Before, `test_tuning` reached `clear_leftovers` through `benchmark._take_gpu` and on Windows listed the real llama-servers, read the
real card and could stop every running GUPPI llama-server with taskkill /F (off Windows it failed on the missing nvidia-smi).

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


def _host_only(fn, harmless):
    """`fn` with its own default `run` (the real subprocess.run) answers `harmless(arguments)`; with any other `run` it runs as written."""
    import functools
    import inspect
    sig = inspect.signature(fn)
    real = sig.parameters['run'].default

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        if bound.arguments['run'] is real:
            return harmless(bound.arguments)
        return fn(*bound.args, **bound.kwargs)
    return wrapper


def _gpu_preflight_patches():
    from guppi_runtime.models import gpu_preflight as gp
    harmless = {
        '_powershell': lambda a: '',                 # no PowerShell: no listener, no processes, no llama-servers
        'vram_used_gb': lambda a: 0.0,               # an empty card
        'gpu_users': lambda a: [],
        '_stop': lambda a: _no_program(),            # never stop a process of this PC
    }
    return [mock.patch.object(gp, name, _host_only(getattr(gp, name), answer)) for name, answer in harmless.items()]


def _patches():
    return _gpu_preflight_patches() + [
        mock.patch('guppi_runtime.hardware._nvidia', side_effect=lambda: dict(TEST_GPU)),
        mock.patch('guppi_runtime.hardware_manager.collector.shutil', SimpleNamespace(which=lambda *a, **k: None, disk_usage=shutil.disk_usage)),
        mock.patch('guppi_runtime.hardware_manager.collector.subprocess', SimpleNamespace(run=_no_program)),
        mock.patch('guppi_runtime.hardware_manager.power.subprocess', SimpleNamespace(run=_no_program)),
        mock.patch('guppi_runtime.models.runtime_control.shutil', SimpleNamespace(which=lambda *a, **k: None)),
    ]


_active = []


def setUpModule():
    import os
    os.environ['SEDRA_PRUEFZUGANG'] = '1'        # Härtung E4: Browser-Prüfungen brauchen den Prüfzugang der Seite (window.sedraBoot.ctx)
    for p in _patches():
        p.start(); _active.append(p)


def tearDownModule():
    while _active:
        _active.pop().stop()
