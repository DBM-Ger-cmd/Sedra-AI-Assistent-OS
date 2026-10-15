"""Diagnosis for the GUPPI chat window (Captain 2026-10-12: "ein richtiges Chat-Fenster, das Interface ist zu klobig fuer Fehlerbehebung"; wanted: error details visible,
a diagnosis side bar, commands in the chat). GUPPI builds the pure parts; Claude wires them into uix_server.py and the chat window afterwards.
Stage 1: `diag_core.py` (python, judged in the microVM): explain_error, parse_command, status_rows. Stage 2: `diag_panel.js` (a classic browser script, judged on the host with node):
slashCommand, rowsText, worstState. Claude wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/chat_diag)."""

NOTES = '''# Notes for the chat diagnosis
Python part: standard library only, plain functions, no classes needed. JavaScript part: a CLASSIC script (no modules, no import/export, no DOM access, no `document`/`window`);
functions and `var` names become globals of the page. No comments and no docstrings, small helpers instead of copied code. All user-facing texts are German exactly as
written in the task (the hidden tests compare them).
'''

PY = r'''
from diag_core import explain_error, parse_command, status_rows

e = explain_error("hardware_pressure:hardware_profile_changed")
assert e["code"] == "hardware_profile_changed" and e["action"] == "rebind" and "/rebind" in e["hint"], e
assert e["title"] == "Hardware-Profil passt nicht mehr zu diesem PC"
e = explain_error("recipe_not_usable:hardware_pressure")
assert (e["code"], e["action"], e["title"]) == ("hardware_pressure", "free_vram", "Nicht genug freier Grafikspeicher"), e
e = explain_error("gpu_lease_busy:claude_quant_2026-10-12:S0 connection check")
assert e["code"] == "gpu_lease_busy" and e["action"] == "wait" and e["title"] == "GPU belegt von claude_quant_2026-10-12", e
assert "S0 connection check" in e["hint"], e
e = explain_error("gpu_lease_busy")
assert e["title"] == "GPU belegt von jemand anderem" and e["code"] == "gpu_lease_busy", e
assert explain_error("gpu_canary_failed")["action"] == "canary"
assert explain_error("x valid_gguf_model_required y")["action"] == "check_files"
assert explain_error("port_in_use")["action"] == "stop_server"
assert explain_error("model_loader_unavailable")["action"] == "enable_loader"
both = explain_error("hardware_pressure hardware_profile_changed")
assert both["code"] == "hardware_profile_changed", both
for odd in ["boom", "", None, 7, ["x"]]:
    u = explain_error(odd)
    assert u["code"] == "unknown" and u["action"] is None and u["title"] == "Unbekannter Fehler", u
assert explain_error("x" * 500)["hint"] == "x" * 200

assert parse_command("hallo") is None and parse_command("") is None and parse_command(None) is None and parse_command("  hallo /status") is None
assert parse_command("/plan bau mir was") is None
assert parse_command("/status") == {"cmd": "status", "args": [], "confirm": False}
assert parse_command("  /STATUS  ") == {"cmd": "status", "args": [], "confirm": False}
assert parse_command("/log 20 fehler") == {"cmd": "log", "args": ["20", "fehler"], "confirm": False}
assert parse_command("/rebind") == {"cmd": "rebind", "args": [], "confirm": False}
assert parse_command("/rebind ja") == {"cmd": "rebind", "args": ["ja"], "confirm": True}
assert parse_command("/Rebind JA") == {"cmd": "rebind", "args": ["JA"], "confirm": True}
assert parse_command("/rebind yes")["confirm"] is True
assert parse_command("/rebind nein")["confirm"] is False
assert parse_command("/status ja")["confirm"] is False
assert parse_command("/hilfe") == {"cmd": "hilfe", "args": [], "confirm": False}
assert parse_command("/fehler") == {"cmd": "fehler", "args": [], "confirm": False}
assert parse_command("/modelle") == {"cmd": "modelle", "args": [], "confirm": False}
assert parse_command("/Foo bar") == {"cmd": "unknown", "name": "foo", "args": [], "confirm": False}
assert parse_command("/") == {"cmd": "unknown", "name": "", "args": [], "confirm": False}

good = {"gpu": {"used_gb": 1.3, "total_gb": 12.0}, "lease": None, "model": {"running": True, "model": "qwen3.6-35b-a3b"},
        "canary": {"ok": True, "at": "2026-10-12 18:36"}, "hardware_profile": {"ok": True, "error": None, "rebind_needed": False}}
rows = status_rows(good)
assert [r["id"] for r in rows] == ["gpu", "lease", "model", "canary", "profile"], rows
assert [r["label"] for r in rows] == ["Grafikkarte", "GPU-Lease", "Modell", "GPU-Selbsttest", "Hardware-Profil"]
assert [r["state"] for r in rows] == ["ok", "ok", "ok", "ok", "ok"], rows
assert rows[0]["detail"] == "10.7 GB frei von 12.0 GB" and rows[1]["detail"] == "frei" and rows[2]["detail"] == "qwen3.6-35b-a3b"
assert rows[3]["detail"] == "bestanden 2026-10-12 18:36" and rows[4]["detail"] == "passt zu diesem PC"
assert all(set(r) == {"id", "label", "state", "detail"} for r in rows)

bad = {"gpu": {"used_gb": 10.5, "total_gb": 12.0}, "lease": {"owner": "claude_quant", "purpose": "S0 check", "stale": False, "mine": False},
       "model": {"running": False, "model": None}, "canary": {"ok": False, "at": None},
       "hardware_profile": {"ok": False, "error": "active_profile_hardware_changed", "rebind_needed": True}}
r = status_rows(bad)
assert [x["state"] for x in r] == ["bad", "warn", "warn", "bad", "bad"], r
assert r[0]["detail"] == "1.5 GB frei von 12.0 GB" and r[1]["detail"] == "belegt von claude_quant: S0 check" and r[2]["detail"] == "kein Modell geladen"
assert r[3]["detail"] == "fehlgeschlagen" and r[4]["detail"] == "passt nicht mehr zu diesem PC: /rebind"
assert status_rows({"gpu": {"used_gb": 8.5, "total_gb": 12.0}})[0]["state"] == "warn"
assert status_rows({"gpu": {"used_gb": 8.0, "total_gb": 12.0}})[0]["state"] == "ok"
assert status_rows({"gpu": {"used_gb": 10.0, "total_gb": 12.0}})[0]["state"] == "warn"
assert status_rows({"gpu": {"used_gb": 10.1, "total_gb": 12.0}})[0]["state"] == "bad"
assert status_rows({"lease": {"owner": "x", "purpose": "y", "stale": True, "mine": False}})[1] == {"id": "lease", "label": "GPU-Lease", "state": "warn", "detail": "verwaist (x)"}
assert status_rows({"lease": {"owner": "guppi-uix", "purpose": "Modell", "stale": False, "mine": True}})[1]["detail"] == "von GUPPI (diese Oberfläche)"
assert status_rows({"lease": {"owner": "guppi-uix", "purpose": "Modell", "stale": True, "mine": True}})[1]["state"] == "ok"
empty = status_rows({})
assert [x["state"] for x in empty] == ["warn", "ok", "warn", "warn", "bad"], empty
assert empty[0]["detail"] == "keine Messung" and empty[3]["detail"] == "noch nicht gelaufen" and empty[4]["detail"] == "Fehler"
assert status_rows(None) == empty
assert status_rows({"canary": {"ok": None, "at": None}})[3]["detail"] == "noch nicht gelaufen"
assert status_rows({"hardware_profile": {"ok": False, "error": "kaputt", "rebind_needed": False}})[4]["detail"] == "kaputt"
snap = {"gpu": {"used_gb": 1, "total_gb": 12}, "model": {"running": True, "model": "m"}}
copy = {k: dict(v) for k, v in snap.items()}; status_rows(snap); assert snap == copy
print("ok")
'''

JS_HEAD = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const box = { Array: Array, console: console };
vm.createContext(box); vm.runInContext(fs.readFileSync("diag_panel.js", "utf8"), box);
const plain = v => JSON.parse(JSON.stringify(v));
'''

JS = r'''
const sc = box.slashCommand;
assert.strictEqual(sc("hallo"), null); assert.strictEqual(sc(""), null); assert.strictEqual(sc(null), null); assert.strictEqual(sc(5), null);
assert.strictEqual(sc("  hallo /status"), null); assert.strictEqual(sc("/plan baue etwas"), null); assert.strictEqual(sc("  /Plan x"), null);
assert.deepStrictEqual(plain(sc("/status")), { cmd: "status", args: [], confirm: false });
assert.deepStrictEqual(plain(sc("  /STATUS  ")), { cmd: "status", args: [], confirm: false });
assert.deepStrictEqual(plain(sc("/log 20 fehler")), { cmd: "log", args: ["20", "fehler"], confirm: false });
assert.deepStrictEqual(plain(sc("/rebind")), { cmd: "rebind", args: [], confirm: false });
assert.deepStrictEqual(plain(sc("/rebind ja")), { cmd: "rebind", args: ["ja"], confirm: true });
assert.deepStrictEqual(plain(sc("/Rebind JA")), { cmd: "rebind", args: ["JA"], confirm: true });
assert.strictEqual(sc("/rebind yes").confirm, true); assert.strictEqual(sc("/rebind nein").confirm, false); assert.strictEqual(sc("/status ja").confirm, false);
["fehler", "modelle", "hilfe"].forEach(n => assert.deepStrictEqual(plain(sc("/" + n)), { cmd: n, args: [], confirm: false }));
assert.deepStrictEqual(plain(sc("/Foo bar")), { cmd: "unknown", name: "foo", args: [], confirm: false });
assert.deepStrictEqual(plain(sc("/")), { cmd: "unknown", name: "", args: [], confirm: false });

const rows = [{ id: "gpu", label: "Grafikkarte", state: "ok", detail: "10.7 GB frei von 12.0 GB" }, { id: "lease", label: "GPU-Lease", state: "warn", detail: "belegt von x: y" },
              { id: "profile", label: "Hardware-Profil", state: "bad", detail: "passt nicht mehr zu diesem PC: /rebind" }];
assert.deepStrictEqual(plain(box.rowsText(rows)), ["✔ Grafikkarte: 10.7 GB frei von 12.0 GB", "⚠ GPU-Lease: belegt von x: y", "✖ Hardware-Profil: passt nicht mehr zu diesem PC: /rebind"]);
assert.deepStrictEqual(plain(box.rowsText([{ label: "A", state: "weird", detail: "d" }])), ["? A: d"]);
assert.deepStrictEqual(plain(box.rowsText([])), []); assert.deepStrictEqual(plain(box.rowsText(null)), []); assert.deepStrictEqual(plain(box.rowsText("x")), []);
assert.strictEqual(box.worstState(rows), "bad"); assert.strictEqual(box.worstState(rows.slice(0, 2)), "warn"); assert.strictEqual(box.worstState(rows.slice(0, 1)), "ok");
assert.strictEqual(box.worstState([]), "ok"); assert.strictEqual(box.worstState(null), "ok");
assert.strictEqual(box.worstState([{ state: "warn" }, { state: "ok" }, { state: "warn" }]), "warn");
const before = JSON.stringify(rows); box.rowsText(rows); box.worstState(rows); assert.strictEqual(JSON.stringify(rows), before);
console.log("ok");
'''

STAGES = [
    {"name": "core",
     "task": """Create `diag_core.py` (Python 3 standard library only) with three functions. All texts are German exactly as written here.
1. `explain_error(raw) -> {"code", "title", "hint", "action"}`; raw is the error text of the chat window (any value; a non-string counts as ""). The FIRST rule that applies wins:
 - raw starts with "gpu_lease_busy": split it at ":"; owner = the 2nd part or "jemand anderem" when missing or empty, purpose = the 3rd part or "". code "gpu_lease_busy", title "GPU belegt von " + owner, hint "Warten, bis der Lauf fertig ist" + (" (" + purpose + ")" if purpose else "") + ".", action "wait".
 - raw CONTAINS (checked in this order) one of: "hardware_profile_changed" -> title "Hardware-Profil passt nicht mehr zu diesem PC", hint "Meist nach einem Treiber-Update. Mit /rebind neu binden.", action "rebind";
   "hardware_pressure" -> "Nicht genug freier Grafikspeicher", "Andere Programme beenden, die die Grafikkarte nutzen, oder ein kleineres Modell wählen.", "free_vram";
   "gpu_canary_failed" -> "GPU-Selbsttest fehlgeschlagen", "NVIDIA-Debug-Modus prüfen, dann den Selbsttest wiederholen.", "canary";
   "valid_gguf_model_required" -> "Modelldatei nicht gefunden", "Pfad der Modelldatei im Rezept prüfen.", "check_files";
   "port_in_use" -> "Port belegt", "Den laufenden Server im Fenster Modelle beenden.", "stop_server";
   "model_loader_unavailable" -> "Automatisches Laden ist aus", "Den Schalter im Fenster Modelle einschalten.", "enable_loader". The code is the matched word itself.
 - otherwise code "unknown", title "Unbekannter Fehler", hint = the first 200 characters of raw, action None.
2. `parse_command(text) -> dict or None`: None unless text is a string whose stripped form starts with "/". Words = the stripped text without the "/" split at whitespace; name = first word lower-cased (or "" when there is none), args = the other words (case kept).
 name "plan" -> None (the chat handles it). A name outside status, fehler, rebind, modelle, log, hilfe -> {"cmd": "unknown", "name": name, "args": [], "confirm": False}.
 Otherwise {"cmd": name, "args": args, "confirm": c}; c is True only for name "rebind" when the first arg lower-cased is "ja" or "yes".
3. `status_rows(snap) -> list` of five dicts {"id", "label", "state", "detail"} in this order (snap may be None or miss keys; never modify it): state is "ok", "warn" or "bad".
 - "gpu" / "Grafikkarte", from snap["gpu"] = {"used_gb", "total_gb"}: missing -> warn, "keine Messung". Else free = total - used; state bad if free < 2, warn if free < 4, else ok; detail "%.1f GB frei von %.1f GB" % (free, total).
 - "lease" / "GPU-Lease", from snap["lease"] = {"owner", "purpose", "stale", "mine"}: missing -> ok, "frei". mine -> ok, "von GUPPI (diese Oberfläche)" (checked first). stale -> warn, "verwaist (OWNER)". Else warn, "belegt von OWNER: PURPOSE".
 - "model" / "Modell", from snap["model"] = {"running", "model"}: running -> ok, the model name; else warn, "kein Modell geladen".
 - "canary" / "GPU-Selbsttest", from snap["canary"] = {"ok", "at"}: missing or ok None -> warn, "noch nicht gelaufen"; ok True -> ok, "bestanden " + at (at None counts as ""; strip the result); ok False -> bad, "fehlgeschlagen".
 - "profile" / "Hardware-Profil", from snap["hardware_profile"] = {"ok", "error", "rebind_needed"}: missing counts as {}. ok true -> ok, "passt zu diesem PC". Else bad: rebind_needed -> "passt nicht mehr zu diesem PC: /rebind", else the error text or "Fehler" when it is empty or None.""",
     "hidden": {"hidden_diag_1.py": PY}},
    {"name": "panel",
     "task": """Create `diag_panel.js` (a classic browser script, see NOTES.md) with:
- `var DIAG_COMMANDS = ["status", "fehler", "rebind", "modelle", "log", "hilfe"]`.
- `slashCommand(text)`: the same rules as `parse_command` of diag_core.py: null unless text is a string whose trimmed form starts with "/"; words = the trimmed text without the "/" split at whitespace (no empty words); name = first word lower-cased or ""; args = the other words (case kept); name "plan" -> null; a name outside DIAG_COMMANDS -> {cmd: "unknown", name, args: [], confirm: false}; otherwise {cmd: name, args, confirm} with confirm true only for "rebind" whose first arg lower-cased is "ja" or "yes".
- `rowsText(rows)`: for an array of {id, label, state, detail} the array of strings symbol + " " + label + ": " + detail with the symbol "\\u2714" for ok, "\\u26A0" for warn, "\\u2716" for bad and "?" for any other state; [] for anything that is not an array.
- `worstState(rows)`: "bad" if any row is bad, else "warn" if any is warn, else "ok" (also for an empty list or a non-array). Never change the arguments.""",
     "host_hidden": {"hidden_diag_2.cjs": JS_HEAD + JS}},
]
