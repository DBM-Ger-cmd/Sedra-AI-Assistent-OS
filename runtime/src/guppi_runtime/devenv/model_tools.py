"""Tools a local model may call through llama-server's OpenAI `tools` interface, and the loop that runs them.

Some small models (Jan-code, SWE-Review: Qwen3 chat template with <tool_call>) are built for tool use and ramble or run into the token
limit when asked for plain text. The tools here are bound to one scratch folder and never execute model code on this host: reading,
writing a .py file, syntax check (ast.parse) and the two ending calls `submit_fix` / `submit_review`.

    box = ToolBox(folder, terminal="submit_fix")
    result = run_tool_loop(post, model_alias, messages, box, sampling)   # post(body) -> parsed /v1/chat/completions answer
"""
from __future__ import annotations

import ast
import json
import re
import time
from pathlib import Path

from ..tools.base import ToolError, ToolPermissionError, ToolValidationError

MAX_FILE_BYTES = 40_000
MAX_WRITE_BYTES = 20_000


def _fn(name, description, properties, required):
    return {"type": "function", "function": {"name": name, "description": description,
                                             "parameters": {"type": "object", "properties": properties, "required": required}}}


SCHEMAS = {
    "read_file": _fn("read_file", "Read a text file from the task folder.", {"path": {"type": "string"}}, ["path"]),
    "write_file": _fn("write_file", "Write a Python file into the task folder (to try a version; it is not run).",
                      {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    "check_syntax": _fn("check_syntax", "Check that a file in the task folder parses as Python. Nothing is executed.", {"path": {"type": "string"}}, ["path"]),
    "submit_fix": _fn("submit_fix", "Hand in the final fixed module. Ends the task.", {"code": {"type": "string", "description": "the complete module"}}, ["code"]),
    "submit_review": _fn("submit_review", "Hand in the review verdict. Ends the task.",
                         {"verdict": {"type": "string", "enum": ["PASS", "FAIL"]}, "cause": {"type": "string", "description": "for FAIL: the defect in one sentence"}},
                         ["verdict"]),
}


class ToolBox:
    def __init__(self, root, tools=("read_file", "check_syntax"), terminal="submit_fix"):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.names = tuple(tools) + (terminal,)
        self.terminal = terminal
        self.final = None           # the arguments of the terminal call
        self.calls = []

    def schemas(self):
        return [SCHEMAS[n] for n in self.names]

    def _path(self, value):
        if not isinstance(value, str) or not value or len(value) > 120: raise ToolValidationError("path_required")
        p = (self.root / value).resolve()
        try: p.relative_to(self.root)
        except ValueError: raise ToolPermissionError("path_outside_tool_root")
        return p

    def call(self, name, args):
        """Result text for the model. Errors are returned as text, not raised: the model may correct itself."""
        self.calls.append(name)
        if name not in self.names: return f"error: unknown tool {name}"
        if not isinstance(args, dict): return "error: arguments must be an object"
        try:
            if name == "read_file":
                p = self._path(args.get("path"))
                if not p.is_file(): raise ToolValidationError("file_not_found")
                return p.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_BYTES]
            if name == "write_file":
                p = self._path(args.get("path"))
                content = args.get("content")
                if p.suffix != ".py" or not isinstance(content, str) or len(content.encode("utf-8")) > MAX_WRITE_BYTES: raise ToolValidationError("only_py_files_up_to_20kb")
                p.write_text(content, encoding="utf-8")
                return "written"
            if name == "check_syntax":
                p = self._path(args.get("path"))
                if not p.is_file(): raise ToolValidationError("file_not_found")
                try: ast.parse(p.read_text(encoding="utf-8"))
                except SyntaxError as exc: return f"SyntaxError line {exc.lineno}: {exc.msg}"
                return "ok: the file parses"
            if name == "submit_fix":
                if not isinstance(args.get("code"), str) or not args["code"].strip(): raise ToolValidationError("code_required")
                self.final = args
                return "received"
            if name == "submit_review":
                if args.get("verdict") not in ("PASS", "FAIL"): raise ToolValidationError("verdict_must_be_PASS_or_FAIL")
                self.final = {"verdict": args["verdict"], "cause": str(args.get("cause") or "")[:500]}
                return "received"
        except ToolError as exc:
            return f"error: {exc}"
        return "error: not handled"


_TAG = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)


def parse_calls(message):
    """[(id, name, args)] from the server's parsed tool_calls, else from <tool_call> text (a model whose template the server did not parse)."""
    out = []
    for i, tc in enumerate(message.get("tool_calls") or []):
        fn = tc.get("function") or {}
        raw = fn.get("arguments")
        try: args = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except ValueError: args = None
        out.append((tc.get("id") or f"call_{i}", fn.get("name"), args))
    if not out:
        for i, m in enumerate(_TAG.finditer(message.get("content") or "")):
            try: obj = json.loads(m.group(1))
            except ValueError: continue
            out.append((f"text_{i}", obj.get("name"), obj.get("arguments") if isinstance(obj.get("arguments"), dict) else None))
    return out


EXTRA_SAMPLING = ("top_p", "top_k", "min_p", "presence_penalty", "frequency_penalty", "repeat_penalty")      # forwarded to the server next to the temperature (Qwen3.x: greedy-like decoding at 0.1 can repeat itself endlessly)


CUT_NOTE = ("Your last answer was cut off because it was too long, and nothing of it was kept. Do the same work in SMALLER steps: at most 100 lines per write_file call, then add the rest with append_file; "
            "for tests write only the few most important ones (at most 15 short tests), not every imaginable variant.")


def cut_arguments(arguments, cut):
    """The arguments of a tool call stay VALID JSON (a cut JSON text makes the chat template of the server fail with HTTP 500, run-4be80c2f9c83): only the long string values are cut."""
    try: data = json.loads(arguments) if isinstance(arguments, str) else arguments
    except ValueError: return arguments
    if not isinstance(data, dict): return arguments
    short = {k: cut(v) if isinstance(v, str) else v for k, v in data.items()}
    return json.dumps(short, ensure_ascii=False) if isinstance(arguments, str) else short


WRITE_TOOLS = ("write_file", "append_file", "edit_file")


def stub_writes(messages, keep_last=6, min_chars=200):
    """The code a model wrote stays in the conversation as the arguments of its write calls and is sent again with EVERY request, although the file is on disk. Older write calls (not the last `keep_last` messages)
    keep their path but their long texts (content, old, new) become a one-line note; read_file brings the text back when needed. Unchanged messages are the same objects, so the start of the conversation stays identical for the prompt cache."""
    out = []
    for i, m in enumerate(messages):
        calls = m.get("tool_calls") if i < len(messages) - keep_last else None
        if not calls or not any(c["function"].get("name") in WRITE_TOOLS for c in calls): out.append(m); continue
        new = []
        for c in calls:
            fn = c["function"]
            if fn.get("name") in WRITE_TOOLS:
                try: args = json.loads(fn["arguments"]) if isinstance(fn.get("arguments"), str) else None
                except ValueError: args = None
                long = [k for k in ("content", "old", "new") if isinstance(args, dict) and isinstance(args.get(k), str) and len(args[k]) > min_chars]
                if long:      # 2026-10-12: the long text is REMOVED, not replaced by a note in its place - a model that repeated a shortened call wrote the note into the file
                    kept = {k: v for k, v in args.items() if k not in long}
                    kept["omitted"] = "; ".join(f"{k}: {len(args[k])} characters" for k in long) + f" (already applied to {args.get('path')}; read_file shows the file)"
                    c = {**c, "function": {**fn, "arguments": json.dumps(kept, ensure_ascii=False)}}
            new.append(c)
        out.append({**m, "tool_calls": new})
    return out


def compact_history(messages, keep_last=8, max_chars=500):
    """A shorter copy of a conversation for a long run (Cline does the same with a summary, 2026-10-09): the system message, the first user message (the task) and the last `keep_last`
    messages stay as they are; everything in between keeps its role and its tool-call structure but its long texts (tool results, written files in tool-call arguments) are cut to `max_chars`."""
    if len(messages) <= keep_last + 2: return list(messages)
    def cut(text):
        return text if not isinstance(text, str) or len(text) <= max_chars else text[:max_chars // 2] + " [...cut...] " + text[-max_chars // 4:]
    out = []
    for i, m in enumerate(messages):
        if i < 2 or i >= len(messages) - keep_last: out.append(m); continue
        copy = dict(m); copy["content"] = cut(m.get("content"))
        if m.get("tool_calls"):
            copy["tool_calls"] = [{**c, "function": {**c["function"], "arguments": cut_arguments(c["function"].get("arguments"), cut)}} for c in m["tool_calls"]]
        out.append(copy)
    return out


LIMIT_KEYS = ("minLength", "maxLength", "minItems", "maxItems")
GRAMMAR_LIMIT = 1999        # Qwen Code measured 1999 as the lowest limit that older llama.cpp grammars reject (docs/design/openai-tool-schema-grammar-compatibility.md)


def relax_schema(node):
    """The copy of a tool schema that goes over the wire: llama.cpp compiles every function schema of a request into ONE grammar, and one schema it cannot compile ends the whole request (HTTP 500 "Unexpected empty grammar stack" was seen with b11530,
    2026-10-09). Empty `properties` maps and `additionalProperties: false` of an object without properties are left out, length and item limits of 1999 and more too. The original schema stays with the tool; the arguments are checked by the toolbox."""
    if isinstance(node, list): return [relax_schema(x) for x in node]
    if not isinstance(node, dict): return node
    out = {}
    for key, value in node.items():
        if key in LIMIT_KEYS and isinstance(value, int) and value >= GRAMMAR_LIMIT: continue
        out[key] = relax_schema(value)
    if out.get("type") == "object" and isinstance(out.get("properties"), dict) and not out["properties"]:
        out.pop("properties"); out.pop("required", None)
        if out.get("additionalProperties") is False: out.pop("additionalProperties")
    return out


FINAL_ANSWER_NOTE = "Du hast jetzt genug Informationen. Antworte dem Captain jetzt in Text, ohne weitere Werkzeuge."

def run_tool_loop(post, alias, messages, box, sampling, *, max_turns=8, max_tokens=4000, cut_retries=2, compact_at=0, stub_at=0, ext=None):
    """Runs the conversation until the terminal tool was called, the model answers without a tool call, or `max_turns` is used up.
    Returns {final, content, turns, tool_calls, finish, seconds, error?}. `post(body)` returns the parsed completion JSON.
    `ext` (coder_ext.CoderExtensions, E-21): thinking patch in every request (E-02), old results pruned (E-05), an answer without a tool call is judged instead of ending the run (E-03)."""
    messages = list(messages)
    t0, content, finish, cuts, corrections, prunes = time.monotonic(), "", None, 0, 0, 0
    for turn in range(1, max_turns + 1):
        body = {"model": alias, "messages": messages, "tools": relax_schema(box.schemas()), "tool_choice": "auto", "max_tokens": max_tokens, "cache_prompt": True,      # the server keeps the evaluated start of the conversation: only the new part is computed again
                "temperature": sampling.get("temperature", 0.1)}
        body.update({key: sampling[key] for key in EXTRA_SAMPLING if isinstance(sampling.get(key), (int, float)) and not isinstance(sampling.get(key), bool)})
        if ext is not None: body.update(ext.request_patch())
        try: data = post(body)
        except Exception as exc:
            return {"final": box.final, "content": content, "turns": turn, "tool_calls": box.calls, "finish": "error",
                    "error": f"{type(exc).__name__}: {str(exc)[:200]}", "seconds": round(time.monotonic() - t0, 1)}
        choice = data["choices"][0]
        message, finish = choice.get("message") or {}, choice.get("finish_reason")
        content = message.get("content") or content
        calls = parse_calls(message)
        used = (data.get("usage") or {}).get("prompt_tokens") or 0
        if stub_at and used > stub_at: messages = stub_writes(messages)       # written code is in the files: do not carry it in every request
        if compact_at and used > compact_at:      # the window fills up (HTTP 400 in the 5th stage of am007, 2026-10-10: ~32k tokens after 23 calls): shorten the old tool results BEFORE the next request
            messages = compact_history(messages)
            reset = getattr(getattr(box, "guard", None), "reset", None)      # the model no longer SEES the old results: reading the same file again is legitimate now, the loop guard starts counting from zero
            if reset: reset()
        if ext is not None:      # E-05: the same list unless the window is fuller than prune_at; a changed message counts as one prune (2026-10-12: E-05 had no counter)
            pruned = ext.prune(messages, used)
            prunes += sum(1 for old, new in zip(messages, pruned) if old is not new)
            messages = pruned
        if finish == "length" and cut_retries > 0:      # an answer that hit the limit is lost (a half tool call cannot be run): say so once or twice instead of ending the run (2026-10-09: 13 % of the Qwen3-Coder runs)
            cut_retries -= 1; cuts += 1
            messages.append({"role": "user", "content": CUT_NOTE})
            continue
        notes = []
        if ext is not None and finish != "length":
            judged = ext.after_answer(data, bool(calls))
            notes = judged["notes"]
            if not calls and judged["action"] == "run": calls = [(f"text_{i}", name, args) for i, (name, args) in enumerate(judged["calls"])]      # a call written as JSON text
            elif not calls and judged["action"] == "correct":
                corrections += 1
                messages.append({"role": "assistant", "content": message.get("content") or ""})
                messages.extend({"role": "user", "content": note} for note in notes)
                continue
        if not calls or finish == "length": break
        messages.append({"role": "assistant", "content": message.get("content") or "",
                         "tool_calls": [{"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args if args is not None else {})}}
                                        for cid, name, args in calls]})
        for cid, name, args in calls:
            messages.append({"role": "tool", "tool_call_id": cid, "content": box.call(name, args) if args is not None else "error: arguments are not valid JSON"})
        messages.extend({"role": "user", "content": note} for note in notes)      # E-02: a note about too much thinking comes after the results
        if box.final is not None: break
        if turn == max_turns - 2:      # a small model keeps reading files: say once that it is time to answer
            messages.append({"role": "user", "content": f"You have enough information. Call {box.terminal} now with your best answer."})
    # Am Limit ohne Text (das Modell rief immer wieder dasselbe Werkzeug): eine letzte Antwort ohne Werkzeuge, sonst bleibt der Captain
    # ohne Text. 28.10.2026: der Chat zeigte dabei „model_answer_empty“.
    if not str(content).strip() and box.final is None and finish != "error":
        messages.append({"role": "user", "content": FINAL_ANSWER_NOTE})
        try:
            data = post({"model": alias, "messages": messages, "tools": [], "tool_choice": "none", "max_tokens": max_tokens, "temperature": sampling.get("temperature", 0.1)})
            choice = data["choices"][0]
            content = (choice.get("message") or {}).get("content") or content
            finish = choice.get("finish_reason") or finish
        except Exception:
            pass                                    # die Antwort bleibt leer; der Aufrufer meldet das
    return {"final": box.final, "content": content, "turns": turn, "tool_calls": box.calls, "finish": finish, "cuts": cuts, "seconds": round(time.monotonic() - t0, 1), "messages": messages, "ext_corrections": corrections, "ext_prunes": prunes}
