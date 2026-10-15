Review of `build_log.py`. The steps "head" and "stages" are fine; change ONLY what is listed. All three points are about the lines of the attempt and the stage in `parse_log` and `events`.

1. `parse_log`, the attempt line (the `re.match(r"attempt\s+(\d+):...` and the dict below it): the pattern has SEVEN groups: 1 number, 2 PASSED/FAILED, 3 the middle text ("own check accepted=..."), 4 seconds, 5 agent runs, 6 calls, 7 path. The code reads seconds from group 3, agent_runs from group 4, calls from group 5 and exported_to from group 6, so `float()` gets "own check accepted=UNJUDGED" and `parse_log` raises ValueError. Read seconds from group 4, agent_runs from 5, calls from 6 and exported_to from 7. Use NAMED groups ((?P<seconds>...)) so that this cannot slip again.

2. `events`, the attempt line (the `re.match` below `elif line.startswith("attempt ")`): the same pattern, the same slip: `seconds = float(m.group(3))` must be group 4 (seconds) and `calls = m.group(4)` must be group 6 (calls).

3. Every line pattern must exist ONCE. The stage pattern, the attempt pattern and the agent pattern are written out in `parse_log` AND in `events`. Define module level compiled patterns (AGENT, STAGE, LOAD, ATTEMPT, and so on) with named groups at the top of the file and use the same objects in both functions.

Keep the behaviour of everything else. Test it yourself against the example in NOTES.md: the attempt line there must give number 1, passed False, seconds 5845.0, agent_runs 9, calls 145.
