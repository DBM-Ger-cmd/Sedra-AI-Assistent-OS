r"""Run the GPU canary again, on purpose (the normal canary only runs at the first model load after a Windows start or a crash).

    .venv\Scripts\python.exe benchmarks/canary_retry.py <project_dir>

Holds the TestLab GPU lease (waits for it), runs the canary exactly like the runtime does, prints the result and exits 0 (passed) or 1 (failed). It never changes clocks, drivers or
settings; if it fails, the NVIDIA debug mode has to be switched on by the Captain (it falls back at every Windows restart).
"""
import os
import sys
import tempfile
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))

from guppi_runtime.models import gpu_canary                                          # noqa: E402
from guppi_runtime.models.gpu_preflight import clear_leftovers                       # noqa: E402
from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime  # noqa: E402
from guppi_runtime.jobs.testlab import TestLab, default_path                         # noqa: E402


def main(project):
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml"); config.enabled = True
    runtime = LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_canary_retry_")))
    engine = runtime.executable_dir
    if config.canary.engine_build and config.engine_source == "guppi":
        from guppi_runtime.models.engine_provision import DEFAULT_ROOT, engine_dir, verify_engine
        root = Path(config.engine_root) if config.engine_root else DEFAULT_ROOT
        if not verify_engine(root, config.canary.engine_build)[0]:
            print("canary engine missing", flush=True)
            return 1
        engine = engine_dir(root, config.canary.engine_build)
    with TestLab(default_path(project)).lease(os.environ.get("TESTLAB_OWNER", "canary_retry"), "gpu canary retry", ttl_s=900, wait_s=3600, preflight=clear_leftovers):
        state = gpu_canary.run_canary(config.canary, engine)
    print(f"canary: passed={state.get('passed')} result={state.get('result')}", flush=True)
    return 0 if state.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
