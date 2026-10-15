from __future__ import annotations
from dataclasses import asdict, dataclass
import ctypes
import os
import platform
import shutil
import subprocess
import hashlib
import json


@dataclass
class HardwareSnapshot:
    os: str
    architecture: str
    cpu: str
    cpu_threads: int
    ram_gb: float | None
    gpu_vendor: str | None = None
    gpu_name: str | None = None
    vram_gb: float | None = None
    apple_unified_memory: bool = False
    hardware_class: str = "unknown"

    def to_dict(self):
        return asdict(self)

    def fingerprint(self):
        payload = {
            "os": self.os, "architecture": self.architecture, "cpu": self.cpu,
            "cpu_threads": self.cpu_threads, "ram_gb": self.ram_gb,
            "gpu_vendor": self.gpu_vendor, "gpu_name": self.gpu_name,
            "vram_gb": self.vram_gb, "apple_unified_memory": self.apple_unified_memory,
            "hardware_class": self.hardware_class,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:24]


def _ram_gb():
    try:
        if os.name == "nt":
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            stat = MEMORYSTATUSEX(); stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return round(stat.ullTotalPhys / (1024**3), 1)
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return round((pages * page_size) / (1024**3), 1)
    except Exception:
        return None


def _nvidia():
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        proc = subprocess.run(
            [exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, shell=False
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        first = proc.stdout.strip().splitlines()[0]
        name, mem = [x.strip() for x in first.rsplit(",", 1)]
        return {"vendor":"NVIDIA", "name":name, "vram_gb":round(float(mem)/1024, 1)}
    except Exception:
        return None


def classify(snapshot: HardwareSnapshot) -> str:
    if snapshot.apple_unified_memory:
        ram = snapshot.ram_gb or 0
        if ram >= 64: return "apple_unified_64plus"
        if ram >= 32: return "apple_unified_32plus"
        if ram >= 16: return "apple_unified_16plus"
        return "apple_unified_small"
    if snapshot.gpu_vendor == "NVIDIA" and snapshot.vram_gb:
        v = snapshot.vram_gb
        if v >= 24: return "nvidia_24plus"
        if v >= 16: return "nvidia_16plus"
        if v >= 10: return "nvidia_10_12"
        if v >= 6: return "nvidia_6_8"
        return "nvidia_small"
    ram = snapshot.ram_gb or 0
    if ram >= 64: return "cpu_64plus"
    if ram >= 32: return "cpu_32plus"
    if ram >= 16: return "cpu_16plus"
    return "cpu_small"


def detect_hardware() -> HardwareSnapshot:
    sysname = platform.system()
    machine = platform.machine()
    snap = HardwareSnapshot(
        os=sysname,
        architecture=machine,
        cpu=platform.processor() or machine or "unknown",
        cpu_threads=os.cpu_count() or 1,
        ram_gb=_ram_gb(),
        apple_unified_memory=(sysname == "Darwin" and machine.lower() in {"arm64", "aarch64"}),
    )
    nvidia = _nvidia()
    if nvidia:
        snap.gpu_vendor=nvidia["vendor"]; snap.gpu_name=nvidia["name"]; snap.vram_gb=nvidia["vram_gb"]
    elif snap.apple_unified_memory:
        snap.gpu_vendor="Apple"; snap.gpu_name="Apple Silicon"; snap.vram_gb=snap.ram_gb
    snap.hardware_class = classify(snap)
    return snap
