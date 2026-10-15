"""Records for the Guppy meter (code_meter) from `git log --numstat --pretty=format:@%ad --date=short` text and from the candidate folders of the DevVM builds. Pure functions (AM-009, written by Claude on the Captain's decision of 2026-10-09 after two GUPPI attempts failed)."""
import datetime
import re

NUMSTAT = re.compile(r"(\d+)\t(\d+)\t(.+)")
STAMP = re.compile(r"_(\d{8})_(\d{6})$")


def _date(text):
    try:
        return datetime.date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _added(line, ignore, guppi):
    found = NUMSTAT.fullmatch(line)
    if not found or found.group(3).startswith(ignore):
        return None
    return ("guppi" if found.group(3) in guppi else "claude"), int(found.group(1))


def records_from_numstat(text, guppi_paths=(), ignore_prefixes=()):
    if not isinstance(text, str):
        return []
    guppi, ignore, totals, day = set(guppi_paths), tuple(ignore_prefixes), {}, None
    for line in text.splitlines():
        if line.startswith("@"):
            day = _date(line[1:].strip())
            continue
        counted = _added(line, ignore, guppi) if day else None
        if counted and counted[1] > 0:
            totals[(day, counted[0])] = totals.get((day, counted[0]), 0) + counted[1]
    return [{"date": d, "author": a, "added": n} for (d, a), n in sorted(totals.items())]


def _stamp(entry):
    if not isinstance(entry, dict) or not isinstance(entry.get("spec"), str) or not isinstance(entry.get("attempt"), str):
        return None
    lines, found = entry.get("lines"), STAMP.search(entry["attempt"])
    if type(lines) is not int or lines <= 0 or not found:
        return None
    day = _date("%s-%s-%s" % (found.group(1)[:4], found.group(1)[4:6], found.group(1)[6:]))
    return (day, found.group(2), entry["attempt"], entry["spec"], lines) if day else None


def candidate_records(entries):
    latest = {}
    for entry in entries or ():
        stamp = _stamp(entry)
        if stamp and (stamp[3] not in latest or stamp[:3] > latest[stamp[3]][:3]):
            latest[stamp[3]] = stamp
    totals = {}
    for stamp in latest.values():
        totals[stamp[0]] = totals.get(stamp[0], 0) + stamp[4]
    return [{"date": d, "author": "guppi", "added": n} for d, n in sorted(totals.items())]
