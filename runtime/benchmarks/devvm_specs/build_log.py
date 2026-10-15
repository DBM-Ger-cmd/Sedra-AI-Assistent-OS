"""G3 build_log (docs/ABLAUF_GESPRAECH_2026-10-13.md, docs/BUILDFLOW_2026-10-13.md; the build runner has to know what a running build does: the output of devvm_build.py is text). `build_log.py` reads that text:
`parse_log` makes a data structure of it (spec, model, stages with their agent runs and reworks, the attempt, the way to resume), `summary` writes the German status block for the chat, and `events` turns the lines that
came in since the last look into short German progress events (a live log is read again and again; a half-written last line is never read). Pure functions on text, no files, no clock. The test data are two REAL logs
(benchmarks/fixtures/build_log_failed.txt, build_log_passed.txt). GUPPI builds it, Claude wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/build_log)."""
from pathlib import Path

NOTES = '''# Notes for build_log
Pure Python 3 standard library (`re` is allowed), no file, process or network access, never modify the arguments, no comments and no docstrings, small private helpers instead of copied code, `import` lines at the top. Texts contain the characters ä ü (UTF-8 source).
The log lines look like this (spaces are as shown; a number of spaces between the columns is NOT fixed):
S0 connection check: coder.local_primary ok
# run devvm_build_skill_unify started 2026-10-13T14:23:06 config {"spec": "skill_unify", "attempts": 1}
   load qwen3.6-35b-a3b with a window of 32768 tokens in each of 1 slot(s)
   agent solo developer         qwen3.6-35b-a3b        hand_in      5 calls   30.1 s 553 tokens, 11255 prompt, peak 2491
   agent solo developer (rework 1) qwen3.6-35b-a3b        answer_cut   8 calls  702.9 s 25409 tokens, 139247 prompt, peak 15151
   stage names: hidden PASSED (own check accepted=UNJUDGED, own tests none, 40.9 s)
   stage rest: hidden FAILED (own check accepted=UNJUDGED, own tests none, 974.7 s)
   stopped after the failed stage rest; skipped: all (--keep-going builds them anyway)
   resume: benchmarks/devvm_build.py <project> --spec assert_catalog --from-stage rest --seed "..." (plus the options of this run)
attempt 1: hidden test FAILED | own check accepted=UNJUDGED | 5845.0 s, 9 agent runs, 145 calls -> ..\\workspace\\GUPPI_OS\\runtime_data\\devvm_candidates\\assert_catalog\\attempt_01_20261013_193955
# run ended: done
DONE -> devvm_build_assert_catalog_2026-10-13_180229.json
Every other line (for example "   lesson for stage ...") is ignored. The agent lines of a stage come BEFORE its stage line.
'''

FIX = Path(__file__).resolve().parents[1] / "fixtures"
HEAD = "LOG_F = " + repr((FIX / "build_log_failed.txt").read_text(encoding="utf-8")) + "\nLOG_P = " + repr((FIX / "build_log_passed.txt").read_text(encoding="utf-8")) + "\n"

S1 = HEAD + r'''
from build_log import parse_log
head = chr(10).join(LOG_P.splitlines()[:4])
p = parse_log(head)
assert p["s0"] == {"recipe": "coder.local_primary", "state": "ok"} and p["spec"] == "skill_unify" and p["started"] == "2026-10-13T14:23:06"
assert p["loads"] == [{"model": "qwen3.6-35b-a3b", "window": 32768, "slots": 1}]
assert p["open_agents"] == [{"label": "solo developer", "model": "qwen3.6-35b-a3b", "stopped_by": "hand_in", "calls": 5, "seconds": 30.1, "tokens": 553, "prompt": 11255, "peak": 2491}]
for empty in ("", None, "nonsense" + chr(10) + "more nonsense"):
    q = parse_log(empty)
    assert (q["s0"], q["spec"], q["started"], q["loads"], q["open_agents"]) == (None, None, None, [], [])
only_header = parse_log("# run devvm_build_x started 2026-01-01T00:00:00")
assert only_header["started"] == "2026-01-01T00:00:00" and only_header["spec"] is None
rework = parse_log("   agent solo developer (rework 1) qwen3.6-35b-a3b        answer_cut   8 calls  702.9 s 25409 tokens, 139247 prompt, peak 15151")
assert rework["open_agents"] == [{"label": "solo developer (rework 1)", "model": "qwen3.6-35b-a3b", "stopped_by": "answer_cut", "calls": 8, "seconds": 702.9, "tokens": 25409, "prompt": 139247, "peak": 15151}]
crlf = parse_log((chr(13) + chr(10)).join(LOG_P.splitlines()[:4]))
assert crlf["spec"] == "skill_unify" and crlf["open_agents"] == p["open_agents"] and crlf["s0"] == p["s0"]
two = parse_log(chr(10).join(LOG_P.splitlines()[:3] + [LOG_P.splitlines()[3]] * 2))
assert len(two["open_agents"]) == 2 and two["loads"] == p["loads"]
text = "S0 connection check: x" + chr(10)
snapshot = text
parse_log(text)
assert text == snapshot
'''

S2 = S1 + r'''
f = parse_log(LOG_F)
assert [(s["name"], s["passed"], s["seconds"], s["reworks"], s["halt"], len(s["agents"])) for s in f["stages"]] == [("core", True, 712.9, 2, "hand_in", 3), ("more", True, 367.0, 1, "hand_in", 2), ("rest", False, 974.7, 3, "hand_in", 4)]
assert f["stages"][0]["agents"][1]["stopped_by"] == "answer_cut" and f["stages"][0]["agents"][1]["label"] == "solo developer (rework 1)" and f["open_agents"] == []
assert f["stages"][2]["agents"][3] == {"label": "solo developer (rework 3)", "model": "qwen3.6-35b-a3b", "stopped_by": "hand_in", "calls": 6, "seconds": 111.3, "tokens": 2894, "prompt": 99071, "peak": 17729}
q = parse_log(LOG_P)
assert [(s["name"], s["passed"], s["reworks"], len(s["agents"])) for s in q["stages"]] == [("names", True, 0, 1), ("groups", True, 0, 1), ("primary", True, 0, 1), ("all", True, 1, 2)]
assert q["stages"][0]["halt"] == "hand_in" and q["stages"][3]["halt"] == "hand_in"
lines = LOG_P.splitlines()
cut = parse_log(chr(10).join(lines[:6]))
assert [s["name"] for s in cut["stages"]] == ["names"] and len(cut["open_agents"]) == 1 and cut["open_agents"][0]["seconds"] == 36.5
cutter = parse_log(chr(10).join(lines[:9]))
assert [s["name"] for s in cutter["stages"]] == ["names", "groups", "primary"] and cutter["open_agents"] == []
bare = parse_log("   stage lone: hidden FAILED (own check accepted=UNJUDGED, own tests none, 2.5 s)")
assert bare["stages"] == [{"name": "lone", "passed": False, "seconds": 2.5, "agents": [], "reworks": 0, "halt": None}]
assert parse_log("")["stages"] == [] and parse_log(None)["stages"] == []
'''

S3 = S2 + r'''
assert (f["stopped_after"], f["skipped"], f["ended"], f["end_state"], f["report"]) == ("rest", ["all"], True, "done", "devvm_build_assert_catalog_2026-10-13_180229.json")
assert f["attempt"] == {"number": 1, "passed": False, "seconds": 5845.0, "agent_runs": 9, "calls": 145, "exported_to": chr(46) * 2 + chr(92) + "workspace" + chr(92) + "GUPPI_OS" + chr(92) + "runtime_data" + chr(92) + "devvm_candidates" + chr(92) + "assert_catalog" + chr(92) + "attempt_01_20261013_193955"}
assert f["resume"].startswith("benchmarks/devvm_build.py <project> --spec assert_catalog --from-stage rest --seed ") and f["resume"].endswith("(plus the options of this run)")
assert (q["stopped_after"], q["skipped"], q["resume"], q["ended"], q["end_state"]) == (None, [], None, True, "done")
assert q["attempt"]["passed"] is True and q["attempt"]["seconds"] == 420.5 and q["attempt"]["agent_runs"] == 5 and q["attempt"]["calls"] == 41
running = parse_log(chr(10).join(lines[:8]))
assert (running["ended"], running["end_state"], running["report"], running["attempt"]) == (False, None, None, None)
multi = parse_log("   stopped after the failed stage b; skipped: c, d, e")
assert multi["stopped_after"] == "b" and multi["skipped"] == ["c", "d", "e"]
from build_log import summary, events
assert summary(f) == chr(10).join(["Bau assert_catalog: 2 von 4 Stufen bestanden, gescheitert: rest, nicht gebaut: all", "Zeit 5845 s, 145 Aufrufe, 9 Läufe", "  core: bestanden, 2 Nacharbeiten, 713 s",
    "  more: bestanden, 1 Nacharbeit, 367 s", "  rest: GESCHEITERT, 3 Nacharbeiten, letzter Halt hand_in, 975 s", "Fortsetzbar ab Stufe rest"]) + chr(10)
assert summary(q) == chr(10).join(["Bau skill_unify: 4 von 4 Stufen bestanden", "Zeit 420 s, 41 Aufrufe, 5 Läufe", "  names: bestanden, keine Nacharbeit, 41 s", "  groups: bestanden, keine Nacharbeit, 36 s",
    "  primary: bestanden, keine Nacharbeit, 32 s", "  all: bestanden, 1 Nacharbeit, 94 s"]) + chr(10)
assert summary(parse_log(chr(10).join(lines[:6]))) == chr(10).join(["Bau skill_unify: 1 von 1 Stufen bestanden", "  names: bestanden, keine Nacharbeit, 41 s", "Bau läuft noch"]) + chr(10)
assert summary(parse_log("")) == "Bau ?: 0 von 0 Stufen bestanden" + chr(10) + "Bau läuft noch" + chr(10)
ev, nxt = events(LOG_P)
assert nxt == 15 and [e["kind"] for e in ev] == ["load", "agent", "stage", "agent", "stage", "agent", "stage", "agent", "agent", "stage", "attempt", "end"]
assert ev[0]["text"] == "Modell geladen: qwen3.6-35b-a3b (Fenster 32768)" and ev[1]["text"] == "Lauf solo developer: hand_in, 5 Aufrufe, 30 s" and ev[2]["text"] == "Stufe names bestanden (41 s)"
assert ev[8]["text"] == "Lauf solo developer (rework 1): hand_in, 11 Aufrufe, 208 s" and ev[10]["text"] == "Versuch 1: bestanden, 420 s, 41 Aufrufe" and ev[11]["text"] == "Bau beendet: done"
fail_events, _ = events(LOG_F)
assert [e["text"] for e in fail_events if e["kind"] == "stage"] == ["Stufe core bestanden (713 s)", "Stufe more bestanden (367 s)", "Stufe rest gescheitert (975 s)"]
assert [e["text"] for e in fail_events if e["kind"] == "attempt"] == ["Versuch 1: gescheitert, 5845 s, 145 Aufrufe"]
partial = LOG_P[:LOG_P.index("stage groups") + 10]
first, mid = events(partial)
assert mid == 6 and [e["kind"] for e in first] == ["load", "agent", "stage", "agent"]
rest, end = events(LOG_P, since=mid)
assert end == 15 and [e["kind"] for e in rest] == ["stage", "agent", "stage", "agent", "agent", "stage", "attempt", "end"]
assert events(LOG_P, since=15) == ([], 15) and events("", 0) == ([], 0) and events(None) == ([], 0)
assert events("   stage x: hidden PASSED (a, 1.0 s)") == ([], 0)
assert events("   stage x: hidden PASSED (a, 1.0 s)" + chr(10)) == ([{"kind": "stage", "text": "Stufe x bestanden (1 s)"}], 1)
assert events(LOG_P, since=100) == ([], 100)
'''

S4 = S3 + r'''
expected = {"s0": {"recipe": "coder.local_primary", "state": "ok"}, "spec": "assert_catalog", "started": "2026-10-13T18:02:29", "loads": [{"model": "qwen3.6-35b-a3b", "window": 32768, "slots": 1}],
            "open_agents": [], "stopped_after": "rest", "skipped": ["all"], "ended": True, "end_state": "done", "report": "devvm_build_assert_catalog_2026-10-13_180229.json"}
assert {k: v for k, v in f.items() if k in expected} == expected and set(f) == set(expected) | {"stages", "attempt", "resume"}
assert parse_log(LOG_F) == parse_log(LOG_F) and parse_log(LOG_F + chr(10)) == f
twice = parse_log(LOG_F + LOG_P)
assert twice["spec"] == "skill_unify" and len(twice["stages"]) == 7 and twice["attempt"]["passed"] is True
'''

STAGES = [
    {"name": "head", "no_own_check": True,
     "task": '''Create `build_log.py` (the log format is in NOTES.md). `parse_log(text) -> dict` reads the text of a devvm build log line by line (`str(text or "")`, `splitlines()`; a "\\r" at the end of a line is no problem) and returns a dict with these keys (in this step the others may be missing or hold their defaults): "s0" (None, or {"recipe": ..., "state": ...} from the line "S0 connection check: <recipe> <state>"), "spec" (None, or the value of "spec" in the config JSON of the "# run <name> started <time> config {...}" line, found with a regex `"spec": "<name>"`), "started" (None, or the time text of that line; a header line without config still gives "started"), "loads" (a list with one dict {"model", "window" (int), "slots" (int)} per line "   load <model> with a window of <n> tokens in each of <m> slot(s)") and "open_agents" (a list of the agent dicts of the agent lines that no stage line has closed yet).
An agent line "   agent <label> <model> <stopped_by> <n> calls <seconds> s <tokens> tokens, <prompt> prompt, peak <peak>" gives {"label" (text, white space cut; it may hold spaces and a part such as "(rework 1)"), "model", "stopped_by", "calls" (int), "seconds" (float), "tokens" (int), "prompt" (int), "peak" (int)}; the number of spaces between the columns is not fixed, the model is the last word before the stop word. Other lines are ignored. Nothing is modified. No comments and no docstrings.''',
     "hidden": {"hidden_log_1.py": S1}},
    {"name": "stages", "no_own_check": True,
     "task": '''In `build_log.py` (keep everything) add the key "stages" to the result of `parse_log`: a list with one dict per line "   stage <name> hidden: PASSED/FAILED" — exactly "   stage <name>: hidden PASSED (<text>, <seconds> s)" or "... hidden FAILED (...)" — with the keys "name", "passed" (True for PASSED), "seconds" (float: the last number before " s)"), "agents" (the agent dicts of the agent lines since the previous stage line, in order), "reworks" (how many of those agents have "(rework" in their label) and "halt" (the "stopped_by" of the last of those agents, None when there are none). The agents of a stage move from "open_agents" into that stage; "open_agents" holds only the agents after the last stage line. No stage lines: "stages" is []. No comments and no docstrings.''',
     "hidden": {"hidden_log_2.py": S2}},
    {"name": "end", "no_own_check": True,
     "task": '''In `build_log.py` add the rest of `parse_log` and the two functions `summary` and `events`.
More keys: "stopped_after" (None, or the stage name of the line "   stopped after the failed stage <name>; skipped: <a, b>" possibly followed by " (<text>)"), "skipped" (the names of that line as a list, split at ",", white space cut; [] otherwise), "attempt" (None, or {"number" (int), "passed" (True for PASSED), "seconds" (float), "agent_runs" (int), "calls" (int), "exported_to" (the text after "-> ")} from the line "attempt <n>: hidden test PASSED|FAILED | <text> | <seconds> s, <k> agent runs, <c> calls -> <path>"), "resume" (None, or the text after "   resume: "), "ended" (True when a line "# run ended: <state>" exists, else False), "end_state" (that <state>, else None) and "report" (the file name of the line "DONE -> <file>", else None). The key set of the result is then: s0, spec, started, loads, stages, open_agents, stopped_after, skipped, attempt, resume, ended, end_state, report.
`summary(parsed) -> str` is the status block for the chat, German, lines joined with a newline and ONE newline at the end: (1) "Bau <spec or ?>: <number of passed stages> von <number of stages + number of skipped stages> Stufen bestanden" + (", gescheitert: <names of the failed stages, joined with ', '>" when there are some) + (", nicht gebaut: <skipped joined with ', '>" when there are some); (2) when there is an attempt: "Zeit <seconds, format .0f> s, <calls> Aufrufe, <agent_runs> Lauf" (one) or "Läufe" (otherwise); (3) one line per stage: "  <name>: bestanden, <rework text>, <seconds .0f> s" or "  <name>: GESCHEITERT, <rework text>, letzter Halt <halt>, <seconds .0f> s" with the rework text "keine Nacharbeit", "1 Nacharbeit" or "<n> Nacharbeiten"; (4) when `stopped_after` is set: "Fortsetzbar ab Stufe <name>"; (5) when the log has not ended: "Bau läuft noch".
`events(text, since=0) -> (list, next_index)`: the progress events of a live log. Only COMPLETE lines count (a line is complete when a "\\n" follows it; a half-written last line is not read yet). `next_index` is the number of complete lines (at least `since`); the events come from the complete lines with an index of `since` or more, in order, as dicts {"kind", "text"}: a load line gives kind "load", "Modell geladen: <model> (Fenster <window>)"; an agent line kind "agent", "Lauf <label>: <stopped_by>, <calls> Aufrufe, <seconds .0f> s"; a stage line kind "stage", "Stufe <name> bestanden (<seconds .0f> s)" or "Stufe <name> gescheitert (<seconds .0f> s)"; an attempt line kind "attempt", "Versuch <n>: bestanden, <seconds .0f> s, <calls> Aufrufe" (or "gescheitert"); the "# run ended" line kind "end", "Bau beendet: <state>". Other lines give no event. No comments and no docstrings.''',
     "hidden": {"hidden_log_3.py": S3}},
    {"name": "all", "no_own_check": True,
     "task": '''Read `build_log.py` once more: no rule may be copied into several places (the patterns of the lines exist once and are used by `parse_log` AND `events`), no comments, no docstrings, all `import` lines at the top, no leftover debug files. Fix only real defects, keep the behaviour.''',
     "hidden": {"hidden_log_full.py": S4}},
]
