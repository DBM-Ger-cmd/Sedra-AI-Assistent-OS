r"""Captain 2026-10-12: switch the recipe coder.llama_qwen35 (Qwen3.5-9B Q6 with MTP head, 131k) ON.

    .venv\Scripts\python.exe benchmarks/mtp_enable_2026-10-12.py <project_dir>

Switched on in place. The script checks that no main role (coder, planner, reviewer, tester, documentation, researcher, verifier) resolves to another recipe
afterwards (the active profile prefers coder.local_primary), and restores the backup if one does. The model runs when asked for by id
(--coder coder.llama_qwen35, a routing profile) or as the fallback when the big models do not fit.
Recipes are never changed while a run uses the GPU: this waits for the lease, holds it only for the edit and backs the file up first.
The file is written as bytes, so its line endings stay as they are.
"""
import shutil
import sys
from pathlib import Path

import yaml

RUNTIME = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RUNTIME / "src"))

from guppi_runtime.role_routing import RoleRouter, RoutingConfig   # noqa: E402
from guppi_runtime.testlab import TestLab, default_path            # noqa: E402
from guppi_runtime.util import atomic_write_bytes                  # noqa: E402

NL = "\n"
OLD_FLAG = "      enabled: false   # guppi-model-remove RM-20261003T185920" + NL
NEW_FLAG = "      enabled: true    # 2026-10-12 Captain: on (Q6 + MTP, 131k); off before since RM-20261003T185920" + NL
ROLES = ("coder", "planner", "reviewer", "tester", "documentation", "researcher", "verifier")


def edit(text):
    start = text.index("    - id: coder.llama_qwen35" + NL)
    end = text.index(NL + "    - id: ", start + 1)
    block = text[start:end]
    if block.count(OLD_FLAG) != 1:
        raise SystemExit("recipe block not as expected - nothing changed")
    return text[:start] + block.replace(OLD_FLAG, NEW_FLAG) + text[end:]


def picks(path):
    """Which recipe each main role resolves to (no hardware snapshot): switching the small model on must not move any role."""
    router = RoleRouter(RoutingConfig.load(RUNTIME / "config" / "role_routing.yaml", path), snapshot=None)
    return {role: router.resolve_role(role, {})["capability_id"] for role in ROLES}


def main():
    project = Path(sys.argv[1])
    path = project / "local_config" / "role_routing.yaml"
    with TestLab(default_path(project)).lease("claude_mtp_enable", "recipe edit: coder.llama_qwen35 on", ttl_s=600, wait_s=8 * 3600):
        raw = path.read_bytes().decode("utf-8")
        if "2026-10-12 Captain: on (Q6 + MTP, 131k)" in raw:
            print("already on"); return
        crlf = "\r\n" in raw
        updated = edit(raw.replace("\r\n", NL))
        if crlf:
            updated = updated.replace(NL, "\r\n")
        recipe = {r["id"]: r for r in yaml.safe_load(updated)["role_routing"]["capabilities"]}["coder.llama_qwen35"]
        assert recipe["enabled"] is True and recipe["profile"]["context"]["maximum"] == 131072 and recipe["profile"]["server"]["mtp"] is True
        before = picks(path)
        backup = path.with_name(path.name + ".bak-2026-10-12-before-mtp-on")
        shutil.copy2(path, backup)
        try:
            atomic_write_bytes(path, updated.encode("utf-8"))
        except PermissionError:               # a reader without FILE_SHARE_DELETE refused the rename (seen 2026-10-12 10:07)
            with path.open("r+b") as stream:
                stream.write(updated.encode("utf-8")); stream.truncate()
        after = picks(path)
        if after != before:
            shutil.copy2(backup, path)
            raise SystemExit(f"roles moved {before} -> {after}: restored from {backup.name}")
        print(f"on; roles unchanged {after} (backup {backup.name})")


if __name__ == "__main__":
    main()
