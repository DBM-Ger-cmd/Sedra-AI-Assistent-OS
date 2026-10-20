"""Does a model still CODE correctly when the window is full? 32k vs 64k on THIS PC (a measurement, not a test).

    .venv\\Scripts\\python.exe benchmarks/context_coding.py <project_dir> <recipe_id> [--windows 8192,32768,65536] [--seeds 2]
        [--set kv_cache_type=f16 ...] [--tag f16]

Captain's goal (2026-10-03): GUPPI builds its own user interface and codes with a 64k window; 32k is accepted if the code is better there.
A needle search (context_ladder.py) only shows that a model can FIND a line. This shows whether it can USE what it found:

  - the window is filled to ~85 % with real GUPPI source files (src/guppi_runtime, fixed order per seed),
  - somewhere in it (10 / 50 / 90 %) sits `uix_kit.py`, a small UI helper library whose names are random per seed (so they cannot be
    guessed) and which contains a deprecated look-alike helper,
  - the model writes `build_dashboard(status)` with that library.

Grading is deterministic and static (the code is parsed, never executed on this host): 11 checks such as "calls the header helper with
level=2", "escapes the name", "uses the alarm tone for failed jobs", "never calls the deprecated helper", "invents no uix_kit name".
Result: runtime_data/measurements/context_coding_<recipe>[_tag]_<date>.json. Holds the GPU lease; nothing in any recipe is changed.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import random
import re
import sys
import tempfile
import time
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from context_ladder import RESERVE_GIB, gpu_mib                                                  # noqa: E402
from guppi_runtime.models.gpu_preflight import clear_leftovers                              # noqa: E402
from guppi_runtime.models.llama_server_runtime import LlamaServerConfig, LlamaServerRuntime  # noqa: E402
from guppi_runtime.jobs.testlab import TestLab, default_path                             # noqa: E402

FILL = 0.85
MAX_TOKENS = 8000
TEMPERATURE = 0.1      # what code_generation.py sends in real runs (2026-10-03: at 0, gpt-oss looped in its thinking 3 of 9 times)
SYLLABLES = ("tor", "vel", "mak", "rin", "sol", "dar", "pex", "lun", "qua", "bri", "fen", "gor", "hal", "jun", "kis", "mor", "nax", "ple")


def word(rng, n=2):
    return "".join(rng.choice(SYLLABLES) for _ in range(n))


def make_kit(rng):
    """Random names for the hidden UI library and its source text."""
    n = {"header": f"{word(rng)}_heading", "row": f"{word(rng)}_line", "join": f"{word(rng)}_stack", "escape": f"{word(rng)}_safe",
         "old": None, "alarm": f"TONE_{word(rng).upper()}", "calm": f"TONE_{word(rng).upper()}", "gap": f"GAP_{word(rng).upper()}",
         "gap_other": f"GAP_{word(rng).upper()}"}
    n["old"] = n["header"].replace("_heading", "_heading_v1")
    src = f'''# file: uix_kit.py  (GUPPI's small UI helper library; every UI module must render through it)
"""Building blocks for GUPPI's status pages. All helpers return HTML strings."""

{n["alarm"]} = "alarm"   # tone for anything that failed or needs the Captain's attention
{n["calm"]} = "calm"     # tone for anything that is fine
{n["gap"]} = 12          # standard vertical gap between blocks (use this one for dashboards)
{n["gap_other"]} = 4     # tight gap, only for tables inside one block


def {n["escape"]}(text):
    """Escape user or model supplied text before it goes into any other helper. Always call this on names."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def {n["old"]}(title):
    """DEPRECATED since v1.18, renders without a level and breaks the page outline. Do not use; use {n["header"]}."""
    return f"<h1>{{title}}</h1>"


def {n["header"]}(title, *, level):
    """Page or block heading. `level` is keyword-only: 1 for the page title, 2 for a dashboard, 3 for a block."""
    return f"<h{{level}}>{{title}}</h{{level}}>"


def {n["row"]}(label, value, *, tone):
    """One label/value line. `tone` is keyword-only and must be one of the TONE_* constants of this module."""
    return f'<div class="{{tone}}"><b>{{label}}</b> {{value}}</div>'


def {n["join"]}(parts, *, gap):
    """Stack blocks vertically. `parts` is a list of HTML strings; `gap` is keyword-only, one of the GAP_* constants."""
    return f'<div style="gap:{{gap}}px">' + "".join(parts) + "</div>"
'''
    return n, src


TASK = """

Task: write a Python module `dashboard.py` for GUPPI's user interface. Use ONLY the helper library `uix_kit` shown in the context above
(import it with `import uix_kit`; do not write HTML yourself). Define

    def build_dashboard(status: dict) -> str

`status` looks like {"name": "GUPPI", "jobs": [{"name": "build", "state": "failed"}, {"name": "test", "state": "done"}]}.
It must return: the dashboard heading (the right heading level for a dashboard) with the escaped status name, then one label/value line
per job (label = escaped job name, value = the state) whose tone is the failure tone for state "failed" and the fine tone otherwise, all
stacked with the standard dashboard gap. Follow the library's docstrings exactly (keyword-only arguments, deprecated helpers).
Answer with the complete module in one ```python block."""


def corpus(rng):
    files = sorted((RUNTIME / "src" / "guppi_runtime").rglob("*.py"))
    rng.shuffle(files)
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        yield f"# file: {f.relative_to(RUNTIME / 'src').as_posix()}\n{text}\n"


def build_context(n_chars, kit_src, where, seed):
    parts, size = [], 0
    for chunk in corpus(random.Random(seed)):
        if size >= n_chars:
            break
        chunk = chunk[: n_chars - size + 1]
        parts.append(chunk); size += len(chunk)
    text = "".join(parts)
    # Placed by size, at the line boundary nearest to `where` (files are 1-60k characters, so file boundaries would be too coarse).
    at = text.rfind("\n", 0, max(1, int(len(text) * where))) + 1
    return "Context: source files of the GUPPI project.\n\n" + text[:at] + "\n" + kit_src + "\n" + text[at:]


def extract_code(text):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, flags=re.S)
    for b in reversed(blocks):
        if "build_dashboard" in b:
            return b
    return blocks[-1] if blocks else text


def grade(code, n):
    checks = {}
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return {"parses": False, "error": str(exc)[:120]}, 0, 11
    checks["parses"] = True
    # Both import styles count for the API checks: `import uix_kit [as k]` and `from uix_kit import x [as y]` (2026-10-03: gpt-oss wrote
    # correct code with the from-form and scored 4/11). The task asks for `import uix_kit`, so only that earns "imports_uix_kit".
    modules, local = set(), {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {a.asname or a.name for a in node.names if a.name == "uix_kit"}
        if isinstance(node, ast.ImportFrom) and node.module == "uix_kit":
            local.update({a.asname or a.name: a.name for a in node.names})
    checks["imports_uix_kit"] = bool(modules)
    fn = [d for d in ast.walk(tree) if isinstance(d, ast.FunctionDef) and d.name == "build_dashboard"]
    checks["defines_build_dashboard"] = bool(fn) and len(fn[0].args.args) == 1

    def kit(expr):
        """The uix_kit name an expression refers to, or None."""
        if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name) and expr.value.id in modules:
            return expr.attr
        if isinstance(expr, ast.Name) and expr.id in local:
            return local[expr.id]
        return None

    attrs = set(local.values())
    calls = []                  # (call node, uix_kit name)
    for node in ast.walk(tree):
        name = kit(node)
        if name:
            attrs.add(name)
        if isinstance(node, ast.Call) and kit(node.func):
            calls.append((node, kit(node.func)))

    def kw(call, name):
        return next((k.value for k in call.keywords if k.arg == name), None)

    headers = [c for c, k in calls if k == n["header"]]
    checks["header_level_2"] = any(isinstance(kw(c, "level"), ast.Constant) and kw(c, "level").value == 2 for c in headers)
    # Escaped before use: as a direct argument OR first stored in a variable. Two calls = the status name and the job names.
    checks["escapes_names"] = sum(k == n["escape"] for _, k in calls) >= 2
    rows = [c for c, k in calls if k == n["row"]]
    checks["row_with_tone_keyword"] = any(kw(c, "tone") is not None for c in rows)
    checks["alarm_tone_used"] = n["alarm"] in attrs
    checks["calm_tone_used"] = n["calm"] in attrs
    joins = [c for c, k in calls if k == n["join"]]
    checks["stack_with_dashboard_gap"] = any(kit(kw(c, "gap")) == n["gap"] for c in joins if kw(c, "gap") is not None)
    checks["no_deprecated_helper"] = n["old"] not in attrs
    real = {n[k] for k in ("header", "row", "join", "escape", "old", "alarm", "calm", "gap", "gap_other")}
    invented = sorted(attrs - real)
    checks["no_invented_names"] = not invented
    score = sum(1 for v in checks.values() if v is True)
    if invented:
        checks["invented"] = invented
    return checks, score, 11


def ask(endpoint, alias, prompt, effort):
    import urllib.error
    import urllib.request
    from guppi_runtime.models.openai_local import split_harmony
    body = json.dumps({"model": alias, "messages": [{"role": "user", "content": prompt}], "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE,
                       **({"reasoning_effort": effort} if effort != "default" else {})}).encode()
    req = urllib.request.Request(endpoint + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=1500) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code}: {exc.read()[:300].decode('utf-8', 'replace')}", "seconds": round(time.monotonic() - started, 1)}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}", "seconds": round(time.monotonic() - started, 1)}
    content = data["choices"][0]["message"].get("content") or ""
    harmony = split_harmony(content)
    if harmony is not None:
        content = harmony[0]
    return {"content": content, "finish": data["choices"][0].get("finish_reason"), "usage": data.get("usage") or {},
            "seconds": round(time.monotonic() - started, 1)}


class OllamaRuntime:
    """The same small surface as LlamaServerRuntime for this test, but through Ollama's own API (cross-check, Captain 2026-10-03).
    Ollama truncates an over-long prompt silently instead of refusing it, so every answer records the prompt tokens it counted."""

    def __init__(self, model, url="http://127.0.0.1:11434"):
        self.model, self.endpoint, self.ctx = model, url, None

    def load_model(self, alias, *, context_length, **_):
        self.ctx = context_length

    def unload_model(self, **_):
        self._post("/api/generate", {"model": self.model, "keep_alive": 0}, 120)

    def _post(self, path, body, timeout):
        import urllib.request
        req = urllib.request.Request(self.endpoint + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())

    def ask(self, prompt, effort):
        started = time.monotonic()
        try:
            data = self._post("/api/chat", {"model": self.model, "stream": False, "keep_alive": "10m", "messages": [{"role": "user", "content": prompt}],
                                            "options": {"num_ctx": self.ctx, "num_predict": MAX_TOKENS, "temperature": TEMPERATURE}}, 1800)
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {str(exc)[:200]}", "seconds": round(time.monotonic() - started, 1)}
        return {"content": (data.get("message") or {}).get("content") or "", "finish": data.get("done_reason"),
                "usage": {"prompt_tokens": data.get("prompt_eval_count")}, "seconds": round(time.monotonic() - started, 1)}


def run_window(runtime, alias, server, window, seeds, effort, cpt, say):
    row = {"window": window, "tasks": []}
    runtime.load_model(alias, context_length=window, gpu="max", identifier=alias, parallel=1, server=server)
    try:
        used, total = gpu_mib()
        row["vram_free_gib"] = round((total - used) / 1024, 2)
        if row["vram_free_gib"] < RESERVE_GIB:     # same 1 GiB reserve as the scheduler: never run below it
            row["error"] = "over_reserve"
            return row, cpt
        budget_tokens = int(window * FILL) - MAX_TOKENS if window > 16384 else window - MAX_TOKENS - 600
        for seed in range(seeds):
            for where in (0.1, 0.5, 0.9):
                rng = random.Random(f"{seed}-{where}")
                n, kit_src = make_kit(rng)
                for _ in range(3):
                    n_chars = max(0, int(budget_tokens * cpt) - len(kit_src) - len(TASK) - 200)
                    prompt = build_context(n_chars, kit_src, where, seed) + TASK
                    out = runtime.ask(prompt, effort) if isinstance(runtime, OllamaRuntime) else ask(runtime.endpoint, alias, prompt, effort)
                    counted = re.search(r'"n_prompt_tokens":(\d+)', out.get("error") or "")
                    if not counted:
                        break
                    cpt = max(1.0, len(prompt) / int(counted.group(1)) * 0.97)
                ptoks = (out.get("usage") or {}).get("prompt_tokens")
                if ptoks:
                    cpt = max(1.5, min(6.0, len(prompt) / ptoks))
                task = {"seed": seed, "where": where, "prompt_tokens": ptoks, "seconds": out.get("seconds"), "finish": out.get("finish")}
                if "error" in out:
                    task.update(score=0, error=out["error"])
                else:
                    checks, score, of = grade(extract_code(out["content"]), n)
                    task.update(score=score, of=of, checks=checks)
                    if out.get("finish") == "length" and not out["content"].strip():
                        task["runaway"] = True          # all output tokens went into thinking, no answer at all
                    task["answer"] = out["content"]          # kept in full so the answers can be graded again later
                row["tasks"].append(task)
                say(f"    seed {seed} @{int(where * 100)}%: {task['score']}/11  {ptoks} tokens  {out.get('seconds')} s  {out.get('finish')}")
                # The reserve is checked again after every answer: llama-server allocates its compute buffers on the first big
                # prompt, so a window can pass at load time and still fall below the reserve while working (gpt-oss 64k q8: 0.84 GiB).
                used, total = gpu_mib()
                row["vram_free_min_gib"] = min(row.get("vram_free_min_gib", 99.0), round((total - used) / 1024, 2))
                if row["vram_free_min_gib"] < RESERVE_GIB:
                    row["error"] = "over_reserve_while_working"
                    say(f"    stopped: only {row['vram_free_min_gib']} GiB free (< {RESERVE_GIB} GiB reserve)")
                    break
            if row.get("error"):
                break
        scores = [t["score"] for t in row["tasks"]]
        row["mean_score"] = round(sum(scores) / (11 * len(scores)), 3)
        row["perfect"] = sum(s == 11 for s in scores)
        row["runaway"] = sum(bool(t.get("runaway")) for t in row["tasks"])
        return row, cpt
    finally:
        try:
            runtime.unload_model(all_models=True)
        except Exception:
            pass
        time.sleep(2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project"); ap.add_argument("recipe")
    ap.add_argument("--windows", default="8192,32768,65536"); ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--effort", default="default", choices=("default", "low", "medium", "high"))
    ap.add_argument("--set", dest="overrides", action="append", default=[], metavar="KEY=VALUE"); ap.add_argument("--tag", default="")
    ap.add_argument("--ollama", metavar="MODEL", help="run the same tasks through Ollama's API with this model instead of GUPPI's llama-server")
    ap.add_argument("--cpt", type=float, default=3.0, help="starting characters per token (Ollama cannot tell when a prompt is too long)")
    args = ap.parse_args()
    project = Path(args.project)
    recipes = {r["id"]: r for r in (yaml.safe_load((project / "local_config" / "role_routing.yaml").read_text(encoding="utf-8"))
                                    or {})["role_routing"]["capabilities"]}
    recipe = recipes[args.recipe]
    overrides = {}
    for item in args.overrides:
        key, _, value = item.partition("=")
        overrides[key.strip()] = value if value.strip().lower() in ("on", "off", "auto") else (yaml.safe_load(value) if value else None)   # YAML reads off as False
    server = {**recipe["profile"]["server"], **overrides}
    alias = str(recipe.get("model") or recipe["id"])
    config = LlamaServerConfig.load(RUNTIME / "config" / "llama_server.yaml"); config.enabled, config.mtp = True, True
    runtime = OllamaRuntime(args.ollama) if args.ollama else LlamaServerRuntime(config, Path(tempfile.mkdtemp(prefix="guppi_ctxcode_")))
    out_dir = project / "runtime_data" / "measurements"; out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"_{args.tag}" if args.tag else ""
    target = out_dir / f"context_coding_{args.recipe}{tag}_{date.today().isoformat()}.json"
    result = {"recipe": args.recipe, "model": alias, "server": {k: v for k, v in server.items() if k != "gguf"}, "overrides": overrides, "backend": ("ollama:" + args.ollama) if args.ollama else "guppi-llama-server",
              "effort": args.effort, "temperature": TEMPERATURE, "fill": FILL, "max_tokens": MAX_TOKENS, "rows": []}
    lab = TestLab(default_path(project))
    with lab.lease(os.environ.get("TESTLAB_OWNER", "context_coding"), f"context coding {args.recipe}{tag}", ttl_s=1800, wait_s=3600,
                   preflight=None if args.ollama else clear_leftovers):
        print(f"== {args.recipe} ({alias}) {overrides or ''} {('via ollama ' + args.ollama) if args.ollama else ''}", flush=True)
        cpt = args.cpt
        for window in (int(w) for w in args.windows.split(",")):
            print(f"  window {window}:", flush=True)
            try:
                row, cpt = run_window(runtime, alias, server, window, args.seeds, args.effort, cpt, lambda s: print(s, flush=True))
            except Exception as exc:
                row = {"window": window, "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
            result["rows"].append(row)
            print(f"  -> window {window}: mean {row.get('mean_score')}  perfect {row.get('perfect')}/{len(row.get('tasks', []))}  runaway {row.get('runaway')}  "
                  f"free {row.get('vram_free_gib')} GiB {row.get('error', '')}", flush=True)
            result["measured_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"  DONE -> {target.name}", flush=True)


if __name__ == "__main__":
    main()
