r"""Captain 2026-10-12: raise the context limit of coder.llama_qwen35 (Qwen3.5-9B Q6 with MTP head) to 131k.

    .venv\Scripts\python.exe benchmarks/mtp_context_raise_2026-10-12.py <project_dir>

Basis: context ladder context_ladder_coder.llama_qwen35_mtp_q6_2026-10-12.json, every rung 16k..131k ok, 0 driver events, 10.48 GiB used / 1.47 GiB free
at 131072. Recipes are never changed while a run uses the GPU, so this waits for the GPU lease, holds it only for the edit, and backs the file up first.
"""
import os
import shutil
import sys
from pathlib import Path

import yaml

RUNTIME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RUNTIME / "src"))

from guppi_runtime.testlab import TestLab, default_path   # noqa: E402
from guppi_runtime.util import atomic_write_text          # noqa: E402

RECIPE = "coder.llama_qwen35"
CHANGES = [
    ("      measured_vram_gb: 6.2        # MTP on, ctx 8192: 5.92 measured + 0.3 margin\n      measured_context: 8192\n"
     "      kv_cache_gb_per_1k_tokens: 0.026   # measured 0.0249 (MTP on) between 8192 and 65536\n",
     "      measured_vram_gb: 8.3        # Q6 + MTP, FA on, KV q8_0, ctx 32768: 7.98 measured + 0.3 margin (ladder 2026-10-12)\n      measured_context: 32768\n"
     "      kv_cache_gb_per_1k_tokens: 0.026   # ladder 2026-10-12: 7.98 GiB at 32k -> 10.48 GiB at 131k = 0.0254 per 1k\n"),
    ("        # Capped at 16384: qwen3.5 (hybrid) crashed with CUDA illegal memory access at prompts of ~23k tokens and above (7k and 15k stable; all\n"
     "        # flags, KV types, MTP on/off and versions tried). The working set keeps prompts under this. See docs/PHASE9_STATUS.md.\n"
     "        context: {recommended: 8192, maximum: 16384, measured_maximum: 16384, tiers: [8192, 16384]}\n",
     "        # 2026-10-12 (Captain): raised from 16384 to 131072. The old cap came from CUDA crashes at ~23k on b11371 without FA (docs/PHASE9_STATUS.md);\n"
     "        # with b11160, FA on and KV q8_0 the ladder (tag mtp_q6) passed every rung 16k..131k, 0 driver events, 1.47 GiB free at 131k.\n"
     "        context: {recommended: 32768, maximum: 131072, measured_maximum: 131072, tiers: [8192, 16384, 32768, 65536, 131072]}\n"),
]


def main():
    project = Path(sys.argv[1])
    path = project / "local_config" / "role_routing.yaml"
    with TestLab(default_path(project)).lease("claude_mtp_context", "recipe edit coder.llama_qwen35 context 131k", ttl_s=600, wait_s=8 * 3600):
        text = path.read_text(encoding="utf-8")
        start = text.index(f"- id: {RECIPE}\n")
        end = text.index("\n    - id: ", start + 1)
        block = text[start:end]
        if "maximum: 131072, measured_maximum: 131072" in block:
            print("already raised"); return
        for old, new in CHANGES:
            if block.count(old) != 1:
                raise SystemExit("recipe block not as expected - nothing changed")
            block = block.replace(old, new)
        updated = text[:start] + block + text[end:]
        recipe = {r["id"]: r for r in yaml.safe_load(updated)["role_routing"]["capabilities"]}[RECIPE]
        assert recipe["profile"]["context"]["maximum"] == 131072 and recipe["profile"]["server"]["mtp"] is True
        backup = path.with_name(path.name + ".bak-2026-10-12-before-mtp-131k")
        shutil.copy2(path, backup)
        try:
            atomic_write_text(path, updated)
        except PermissionError:               # a reader without FILE_SHARE_DELETE refused the rename (seen 2026-10-12 10:07)
            with path.open("r+", encoding="utf-8", newline="") as stream:
                stream.write(updated); stream.truncate()
        if yaml.safe_load(path.read_text(encoding="utf-8")) != yaml.safe_load(updated):
            raise SystemExit("recipe file differs after writing - restore it from " + backup.name)
        print(f"raised to 131072 (backup {backup.name})")


if __name__ == "__main__":
    main()
