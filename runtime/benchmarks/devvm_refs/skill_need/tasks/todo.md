# Task list

## Task 1: Collect all notes

**Description:** Read all notes from the store in creation order.

**Acceptance criteria:**
- [ ] A function returns every note, oldest first

**Verification:**
- [ ] Tests pass: python3 -m unittest
- [ ] Build succeeds: python3 -m compileall .
- [ ] Manual check: call it on a sample database

**Dependencies:** None

**Files likely touched:**
- `store.py`

**Estimated scope:** Small: 1-2 files

## Task 2: Render notes as Markdown

**Description:** Turn the notes into one Markdown text with a heading per note.

**Acceptance criteria:**
- [ ] One heading per note
- [ ] Notes keep their order

**Verification:**
- [ ] Tests pass: python3 -m unittest
- [ ] Build succeeds: python3 -m compileall .
- [ ] Manual check: read the rendered text

**Dependencies:** Task 1

**Files likely touched:**
- `export.py`
- `tests/test_export.py`

**Estimated scope:** Small: 1-2 files

## Task 3: Add the export command

**Description:** Write the Markdown to a file from the command line.

**Acceptance criteria:**
- [ ] `main.py export FILE` writes the file

**Verification:**
- [ ] Tests pass: python3 -m unittest
- [ ] Build succeeds: python3 -m compileall .
- [ ] Manual check: run the command

**Dependencies:** Task 2

**Files likely touched:**
- `main.py`

**Estimated scope:** Small: 1-2 files
