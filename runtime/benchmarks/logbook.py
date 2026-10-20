r"""Add one row to the logbook with the REAL time (rule 5 of docs/ENTWICKLUNG.md: the time comes from the clock, never from a guess; Claude estimated six times on 2026-10-13).

    .venv\Scripts\python.exe benchmarks/logbook.py add BAU "what happened" [--ref "file or report"] [--late] [--file PATH]

ART is one word of the fixed list ARTS (ENTSCHEIDUNG, SPEC, BAU, INTEGRATION, MESSUNG, FEHLER, AENDERUNG, DOKU, RECHERCHE, HINWEIS); ÄNDERUNG is taken as AENDERUNG, any other word stops with the list (V2, 2026-10-20). The row is appended in the file's own line ending. A row with a local path (E:\..., C:\Users\...)
is refused (rule 10: placeholders <modelle>, <projekte>, <guppi>). `--late` marks a row that is written after the event ("nachgetragen"). The row is printed."""
import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[2] / "docs" / "LOGBUCH_AGENT_MANAGER.md"
LOCAL_PATH = re.compile(r"[A-Za-z]:[\\/]|/mnt/[a-z]/|/Users/")
# The fixed list of kinds (Captain 2026-10-20, V2): another word is refused with this list. The placeholder of the usage line is refused too
# (three rows said literally "ART" on 2026-10-14). Old rows of the logbook keep their kinds (AUDIT, GATE, PLAN ...); only new rows are checked.
ARTS = ("ENTSCHEIDUNG", "SPEC", "BAU", "INTEGRATION", "MESSUNG", "FEHLER", "AENDERUNG", "DOKU", "RECHERCHE", "HINWEIS")
STANDARD_ARTS = ARTS
PLACEHOLDERS = ("ART", "TYP", "KIND", "TYPE")
UMLAUTS = {"Ä": "AE", "Ö": "OE", "Ü": "UE"}      # ÄNDERUNG on the command line (the terminal may hand over umlauts) is AENDERUNG


def make_row(art, text, ref="", late=False, now=None):
    art = str(art).strip()
    for umlaut, plain in UMLAUTS.items():
        art = art.replace(umlaut, plain)
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,20}", art):
        raise ValueError("ART must be one word in capitals, e.g. BAU")
    if art in PLACEHOLDERS:
        raise ValueError("ART is the placeholder of the usage line; name the kind: " + ", ".join(ARTS))
    if art not in ARTS:
        raise ValueError(f"unknown ART {art}; allowed: " + ", ".join(ARTS))
    text, ref = " ".join(str(text).split()).replace("|", "/"), " ".join(str(ref).split()).replace("|", "/")
    if not text:
        raise ValueError("the text is empty")
    if LOCAL_PATH.search(text) or LOCAL_PATH.search(ref):
        raise ValueError("local path in the row (rule 10): use <modelle>, <projekte>, <guppi> or a path inside the repository")
    stamp = (now or datetime.now()).strftime("%Y-%m-%d %H:%M") + (" (nachgetragen)" if late else "")
    return f"| {stamp} | {art} | {text} | {ref} |"


def append(path, row):
    path = Path(path)
    data = path.read_bytes()
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    if data and not data.endswith(b"\n"):
        data += newline
    path.write_bytes(data + row.encode("utf-8") + newline)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("art")
    add.add_argument("text")
    add.add_argument("--ref", default="")
    add.add_argument("--late", action="store_true")
    add.add_argument("--file", default=str(DEFAULT))
    args = ap.parse_args(argv)
    try:
        row = make_row(args.art, args.text, args.ref, args.late)
    except ValueError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    append(args.file, row)
    print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
