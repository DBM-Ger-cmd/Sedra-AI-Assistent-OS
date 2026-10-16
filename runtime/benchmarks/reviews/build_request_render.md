Review of `build_request.py`. The step "validate" is fine (validate_request and cases_from_examples); change ONLY `render_spec` and `stage_tests` as listed.

1. `render_spec` never calls `validate_request`. The task says: when `validate_request(request)` finds a problem, `render_spec` raises `ValueError("invalid request: " + first problem)`. Make this the FIRST statement of `render_spec`:

    problems = validate_request(request)
    if problems:
        raise ValueError("invalid request: " + problems[0])

   Example that must raise: the request with the name "bad name" (a space) must give ValueError("invalid request: bad name"); a request with `stages` = [] must give ValueError("invalid request: no stages"). Without this the code takes request["name"] and builds a spec file for an invalid request.

2. `stage_tests(request)` must also refuse a check with a kind that does not exist (`assert_catalog.build_test` already raises KeyError or ValueError for it: do not catch that error).

3. Keep the other rules of `render_spec`: TITLE is the cleaned title (`" ".join(title.split())`), the name when there is no title or the cleaned title is empty; NOTES is the notes text or ""; STAGES is the list of dicts with the keys in the order name, no_own_check, task, hidden; every text is written with `repr`; the text ends with ONE newline.
