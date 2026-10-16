# Spec: Export notes as Markdown

## Objective
Let users export all notes of the tool as one Markdown file. Users can back up and share their notes.

## Tech Stack
Python 3 standard library only.

## Commands
- Test: python3 -m unittest discover -v
- Export: python3 main.py export notes.md

## Project Structure
- store.py: database access
- export.py: renders notes as Markdown
- main.py: command line

## Code Style
Small functions, snake_case names, no comments.

## Testing Strategy
unittest, tests in tests/, one test per rendering rule.

## Boundaries
- Always: run the tests before a commit
- Ask first: adding a dependency
- Never: overwrite an existing export file without a flag

## Success Criteria
The export file contains every note, one heading per note, in creation order.

## Open Questions
Should attachments be exported?
