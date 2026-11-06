RULES = [
    ("edit_file", r"old was not found", "edit_not_found"),
    ("edit_file", r"occurs \d+ times", "edit_ambiguous"),
    ("edit_file", r"the changes overlap", "edit_overlap"),
    ("write_file", r"already exists", "write_exists"),
    ("read_file", r"the file has only \d+ lines", "read_range"),
    ("*", r"too long: \d+ characters", "too_long"),
    ("*", r"\b\w+ is required", "missing_arg"),
]

CARDS = {
    "edit_not_found": "How to use edit_file: `old` must be copied EXACTLY from the file as it is now (spaces, indentation, quotes). Read the part again with read_file (start/end), copy 2-4 whole lines around the place, change only `new`. Do not type `old` from memory.",
    "edit_ambiguous": "How to use edit_file: `old` occurs several times. Make it unique by adding the line above or below it (for example the `def` line of the function), or change each place in its own edit with more context.",
    "edit_overlap": "How to use edit_file with `edits`: every change must touch a different place. If two changes touch the same lines, put them into ONE change whose `old` covers all those lines.",
    "write_exists": "How to change an existing file: use edit_file for each place you change (several places at once with `edits`). Only to replace the WHOLE file: delete_file it first, then write_file the new content in parts of at most 100 lines.",
    "read_range": "How to use read_file on a long file: use outline to find the line numbers of the function you need, then read_file with start and end around it (at most 150 lines per call).",
    "too_long": "How to write long text: at most 6000 characters (about 100 lines) per call. Write the first part with write_file, then add the next parts with append_file. For edit_file, change smaller pieces.",
    "missing_arg": "How to call a tool: give every required argument as a JSON field with the exact name from the tool description (for example `path`, `content`, `old`, `new`).",
}
