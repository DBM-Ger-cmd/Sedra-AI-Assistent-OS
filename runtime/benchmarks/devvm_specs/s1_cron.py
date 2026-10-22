"""Spec 1, Bau-Spec s1_cron (docs/SPEC_AGENTEN_ORCHESTRIERUNG_v1.md, Design Stufe 2, D1.1 `cron.py`, ORC-10; gates G1-S1-11 (own build, no library), G2-S1-22):
`orchestra/cron.py`, the pure cron of the routines: five fields (minute, hour, day, month, weekday) with *, number, list, range, step and English names; the next
date strictly after a UTC time, computed in the local time of a zone (daylight saving: a date in the skipped hour of spring moves to the first valid minute after it,
once; a date in the doubled hour of autumn runs once, at its first occurrence, fold=0); all dates of an interval with a recognisable cap; and the German sentence of
Shell D's cronText for the common forms (display only). A zone is a name ("UTC" always works; other names need the zone data of zoneinfo, unknown ->
cron_timezone_unknown) or a tzinfo object. OP-S1-03 (21.10.2026): the .venv has no tzdata, so on Windows only "UTC" and tzinfo objects work until tzdata gets its gate;
the hidden tests therefore bring their own Europe/Berlin rule as a tzinfo class (EU rule, PEP 495 fold) and never need zone data. routines.py imports it (seed of s1_routines).
GUPPI/SEDRA builds it; Claude only wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/s1_cron)."""

NOTES = '''# Notes for s1_cron
Python 3 standard library only (datetime; zoneinfo imported only inside the zone lookup); no sqlite3, no files of your own, no clock (never datetime.now), no network.
Times are UTC texts in the form 2026-10-21T08:00:00Z. Every function is pure and never modifies its arguments. Every refusal is a ValueError with exactly the text the task names.
No comments and no docstrings, small private helpers instead of copied code (one helper parses one field). No recursion; the search for the next date goes day by day over the matching
days and over the hours and minutes of the expression (never minute by minute over years).
'''

HEAD = r'''
import copy
from datetime import datetime, timedelta, timezone, tzinfo
from cron import IMPORTS


def raises(text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except ValueError as e:
        assert str(e) == text, (str(e), text)
        return
    raise AssertionError(f"no ValueError({text!r})")


def last_sunday(year, month):
    day = datetime(year, month, 31)
    return day - timedelta(days=(day.weekday() + 1) % 7)


class Berlin(tzinfo):
    def _switch(self, year):
        return last_sunday(year, 3).replace(hour=1), last_sunday(year, 10).replace(hour=1)

    def utcoffset(self, dt):
        start, end = self._switch(dt.year)
        wall = dt.replace(tzinfo=None)
        if start + timedelta(hours=1) <= wall < start + timedelta(hours=2):
            return timedelta(hours=2 if dt.fold else 1)
        if end + timedelta(hours=1) <= wall < end + timedelta(hours=2):
            return timedelta(hours=1 if dt.fold else 2)
        return timedelta(hours=2 if start + timedelta(hours=2) <= wall < end + timedelta(hours=1) else 1)

    def dst(self, dt):
        return self.utcoffset(dt) - timedelta(hours=1)

    def tzname(self, dt):
        return "Berlin"

    def fromutc(self, dt):
        start, end = self._switch(dt.year)
        utc = dt.replace(tzinfo=None)
        if start <= utc < end:
            return (utc + timedelta(hours=2)).replace(tzinfo=self)
        return (utc + timedelta(hours=1)).replace(tzinfo=self, fold=1 if end <= utc < end + timedelta(hours=1) else 0)


BER = Berlin()
BODY
print("ok")
'''


def hidden(imports, body):
    return HEAD.replace("IMPORTS", imports).replace("BODY", body)


C1 = r'''
c = parse("*/15 * * * *")
assert c["minute"] == [0, 15, 30, 45]
assert c["hour"] == list(range(24))
assert (c["day"], c["month"], c["weekday"]) == (list(range(1, 32)), list(range(1, 13)), list(range(7)))
assert (c["day_any"], c["weekday_any"], c["every"], c["text"]) == (True, True, 15, "*/15 * * * *")
d = parse("  5,10-12,40-50/5  6-8/2 1,15 jan,JUL mon-fri ")
assert d["minute"] == [5, 10, 11, 12, 40, 45, 50]
assert (d["hour"], d["day"], d["month"], d["weekday"]) == ([6, 8], [1, 15], [1, 7], [1, 2, 3, 4, 5])
assert (d["day_any"], d["weekday_any"], d["every"]) == (False, False, None)
assert d["text"] == "5,10-12,40-50/5 6-8/2 1,15 jan,JUL mon-fri"
assert [parse(e)["weekday"] for e in ("0 0 * * 7", "0 0 * * 0,7", "0 0 * * 5-7", "0 0 * * SUN")] == [[0], [0], [0, 5, 6], [0]]
assert parse("10/20 * * * *")["minute"] == [10, 30, 50]
assert parse("0 0 1 oct-dec *")["month"] == [10, 11, 12]
assert parse("0 0 1 * *")["weekday_any"] is True
for expr in ("", "* * * *", "* * * * * *", None, 5):
    raises("cron_invalid:fields", parse, expr)
cases = [("60 * * * *", "minute"), ("*/0 * * * *", "minute"), ("5-1 * * * *", "minute"), ("x * * * *", "minute"), ("1,,2 * * * *", "minute"), ("-1 * * * *", "minute"),
         ("* 24 * * *", "hour"), ("* * 0 * *", "day"), ("* * 32 * *", "day"), ("* * * 13 *", "month"), ("* * * foo *", "month"), ("* * * mon *", "month"),
         ("* * * * 8", "weekday"), ("* * * * mon-sun", "weekday"), ("* * * * jan", "weekday"), ("* * * * */x", "weekday"), ("* * * * ²", "weekday"),
         ("60 24 * * *", "minute"), ("* * * dec-feb *", "month"),
         ("0 0-99 * * *", "hour"), ("50-60 * * * *", "minute"), ("* * 0-5 * *", "day"), ("* * * 1-13 *", "month"), ("* * * * 0-8", "weekday"),
         ("70/5 * * * *", "minute"), ("* 25/2 * * *", "hour"), ("* * 32/1 * *", "day")]
for expr, field in cases:
    raises("cron_invalid:" + field, parse, expr)
'''

C2 = r'''
U = "UTC"
table = [("30 6 * * *", "2026-10-21T05:00:00Z", "2026-10-21T06:30:00Z"), ("30 6 * * *", "2026-10-21T06:30:00Z", "2026-10-22T06:30:00Z"),
         ("30 6 * * *", "2026-10-21T06:29:59Z", "2026-10-21T06:30:00Z"), ("0 9 * * 1-5", "2026-10-21T10:00:00Z", "2026-10-22T09:00:00Z"),
         ("0 9 * * 1-5", "2026-10-23T10:00:00Z", "2026-10-26T09:00:00Z"), ("0 8 * * sat,sun", "2026-10-21T00:00:00Z", "2026-10-24T08:00:00Z"),
         ("0 6 1 * *", "2026-10-21T00:00:00Z", "2026-11-01T06:00:00Z"), ("0 6 1 * 1", "2026-10-21T00:00:00Z", "2026-10-26T06:00:00Z"),
         ("0 6 13 * 5", "2026-10-21T00:00:00Z", "2026-10-23T06:00:00Z"), ("0 0 29 2 *", "2026-10-21T00:00:00Z", "2028-02-29T00:00:00Z"),
         ("0 0 * 2 *", "2026-10-21T00:00:00Z", "2027-02-01T00:00:00Z"), ("59 23 31 12 *", "2026-12-31T23:59:00Z", "2027-12-31T23:59:00Z"),
         ("*/15 * * * *", "2026-10-21T06:07:00Z", "2026-10-21T06:15:00Z"), ("*/15 * * * *", "2026-10-21T06:45:00Z", "2026-10-21T07:00:00Z"),
         ("*/15 * * * *", "2026-12-31T23:50:00Z", "2027-01-01T00:00:00Z"), ("0 12 * * 0", "2026-10-21T00:00:00Z", "2026-10-25T12:00:00Z"),
         ("0 12 * * 7", "2026-10-21T00:00:00Z", "2026-10-25T12:00:00Z"), ("0 6 * jan mon", "2026-10-21T00:00:00Z", "2027-01-04T06:00:00Z"),
         ("0 6 * jan *", "2026-10-21T00:00:00Z", "2027-01-01T06:00:00Z"), ("0 6 31 * *", "2026-10-31T06:00:00Z", "2026-12-31T06:00:00Z")]
for expr, after, want in table:
    assert next_after(parse(expr), after, U) == want, (expr, after)
c = parse("0 6 1 * 1")
keep = copy.deepcopy(c)
assert next_after(c, "2026-10-26T06:00:00Z", U) == "2026-11-01T06:00:00Z"
assert c == keep
assert next_after(parse("0 6 13 * 5"), "2026-10-23T06:00:00Z", U) == "2026-10-30T06:00:00Z"
assert next_after(parse("0 6 * * 5"), "2026-11-12T06:00:00Z", U) == "2026-11-13T06:00:00Z"
assert next_after(parse("0 6 13 * *"), "2026-10-21T00:00:00Z", U) == "2026-11-13T06:00:00Z"
'''

C3 = r'''
plus2, minus5 = timezone(timedelta(hours=2)), timezone(timedelta(hours=-5))
assert next_after(parse("30 6 * * *"), "2026-10-21T05:00:00Z", plus2) == "2026-10-22T04:30:00Z"
assert next_after(parse("30 6 * * *"), "2026-10-21T04:00:00Z", plus2) == "2026-10-21T04:30:00Z"
assert next_after(parse("0 23 * * *"), "2026-10-21T00:00:00Z", minus5) == "2026-10-21T04:00:00Z"
assert next_after(parse("0 9 * * 3"), "2026-10-21T13:00:00Z", minus5) == "2026-10-21T14:00:00Z"
assert next_after(parse("0 9 * * 3"), "2026-10-21T13:00:00Z", plus2) == "2026-10-28T07:00:00Z"
assert next_after(parse("0 0 1 * *"), "2026-10-31T21:00:00Z", plus2) == "2026-10-31T22:00:00Z"
assert next_after(parse("* * * * *"), "2026-10-21T06:30:30Z", "UTC") == "2026-10-21T06:31:00Z"
assert next_after(parse("* * * * *"), "2026-10-21T06:30:00Z", "UTC") == "2026-10-21T06:31:00Z"
assert next_after(parse("0 0 30 2 *"), "2026-10-21T00:00:00Z", "UTC") is None
assert next_after(parse("0 0 31 4,6 *"), "2026-10-21T00:00:00Z", plus2) is None
for zone in ("Mars/Base", "", None, 5, "../etc/passwd", "Europe/Nirgendwo"):
    raises("cron_timezone_unknown", next_after, parse("0 6 * * *"), "2026-10-21T00:00:00Z", zone)
out = next_after(parse("5 4 * * *"), "2026-10-21T00:00:00Z", "UTC")
assert isinstance(out, str)
assert datetime.strptime(out, "%Y-%m-%dT%H:%M:%SZ") == datetime(2026, 10, 21, 4, 5)
'''

C4 = r'''
assert BER.fromutc(datetime(2026, 10, 25, 1, 30, tzinfo=BER)).fold == 1
spring = [("30 2 * * *", "2026-03-28T12:00:00Z", "2026-03-29T01:00:00Z"), ("30 2 * * *", "2026-03-29T01:00:00Z", "2026-03-30T00:30:00Z"),
          ("0 3 * * *", "2026-03-28T12:00:00Z", "2026-03-29T01:00:00Z"), ("0 1 * * *", "2026-03-28T12:00:00Z", "2026-03-29T00:00:00Z"),
          ("*/15 2-3 * * *", "2026-03-29T00:50:00Z", "2026-03-29T01:00:00Z"), ("*/15 2-3 * * *", "2026-03-29T01:00:00Z", "2026-03-29T01:15:00Z"),
          ("30 6 * * *", "2026-07-01T00:00:00Z", "2026-07-01T04:30:00Z"), ("30 6 * * *", "2026-12-01T00:00:00Z", "2026-12-01T05:30:00Z")]
for expr, after, want in spring:
    assert next_after(parse(expr), after, BER) == want, (expr, after)
autumn = [("30 2 * * *", "2026-10-24T12:00:00Z", "2026-10-25T00:30:00Z"), ("30 2 * * *", "2026-10-25T00:30:00Z", "2026-10-26T01:30:00Z"),
          ("*/30 * * * *", "2026-10-25T00:30:00Z", "2026-10-25T02:00:00Z"), ("*/30 * * * *", "2026-10-25T01:10:00Z", "2026-10-25T02:00:00Z"),
          ("0 2 * * *", "2026-10-24T12:00:00Z", "2026-10-25T00:00:00Z"), ("0 3 * * *", "2026-10-24T12:00:00Z", "2026-10-25T02:00:00Z"),
          ("59 1 * * *", "2026-10-24T12:00:00Z", "2026-10-24T23:59:00Z")]
for expr, after, want in autumn:
    assert next_after(parse(expr), after, BER) == want, (expr, after)
assert next_after(parse("0 9 * * 1-5"), "2026-10-23T08:00:00Z", BER) == "2026-10-26T08:00:00Z"
assert next_after(parse("0 9 * * 1-5"), "2026-03-27T08:00:00Z", BER) == "2026-03-30T07:00:00Z"
'''

C5 = r'''
hourly = parse("0 * * * *")
keep = copy.deepcopy(hourly)
assert due_between(hourly, "2026-10-21T05:00:00Z", "2026-10-21T08:00:00Z", "UTC", 10) == ["2026-10-21T06:00:00Z", "2026-10-21T07:00:00Z", "2026-10-21T08:00:00Z"]
assert due_between(hourly, "2026-10-21T05:00:00Z", "2026-10-21T08:00:00Z", "UTC", 1) == ["2026-10-21T06:00:00Z", "2026-10-21T07:00:00Z"]
assert due_between(hourly, "2026-10-21T05:00:00Z", "2026-10-21T08:00:00Z", "UTC", 0) == ["2026-10-21T06:00:00Z"]
assert due_between(hourly, "2026-10-21T05:30:00Z", "2026-10-21T05:59:59Z", "UTC", 5) == []
assert due_between(hourly, "2026-10-21T06:00:00Z", "2026-10-21T06:00:00Z", "UTC", 5) == []
assert due_between(hourly, "2026-10-21T08:00:00Z", "2026-10-21T06:00:00Z", "UTC", 5) == []
assert hourly == keep
assert len(due_between(parse("* * * * *"), "2026-10-21T00:00:00Z", "2026-10-28T00:00:00Z", "UTC", 50)) == 51
assert due_between(parse("0 0 30 2 *"), "2026-10-21T00:00:00Z", "2030-10-21T00:00:00Z", "UTC", 5) == []
assert due_between(parse("30 2 * * *"), "2026-10-24T12:00:00Z", "2026-10-26T12:00:00Z", BER, 5) == ["2026-10-25T00:30:00Z", "2026-10-26T01:30:00Z"]
assert due_between(parse("*/30 2 * * *"), "2026-03-28T12:00:00Z", "2026-03-29T12:00:00Z", BER, 5) == ["2026-03-29T01:00:00Z"]
assert due_between(parse("0 6 * * 1"), "2026-10-01T00:00:00Z", "2026-11-01T00:00:00Z", "UTC", 9) == ["2026-10-05T06:00:00Z", "2026-10-12T06:00:00Z", "2026-10-19T06:00:00Z", "2026-10-26T06:00:00Z"]
raises("cron_timezone_unknown", due_between, hourly, "2026-10-21T05:00:00Z", "2026-10-21T08:00:00Z", "Mars/Base", 5)
'''

C6 = r'''
table = [("30 6 * * *", "jeden Tag um 06:30 Uhr"), ("0 9 * * 1-5", "montags bis freitags um 09:00 Uhr"), ("0 9 * * 5,1,3", "montags, mittwochs und freitags um 09:00 Uhr"),
         ("0 8 * * sat,SUN", "samstags und sonntags um 08:00 Uhr"), ("0 7 * * 7", "sonntags um 07:00 Uhr"), ("*/15 * * * *", "alle 15 Minuten"),
         ("15 * * * *", "stündlich zur Minute 15"), ("0 * * * *", "stündlich zur vollen Stunde"), ("0,30 * * * *", "stündlich zu den Minuten 00 und 30"),
         ("0,30 6,18 * * *", "jeden Tag um 06:00, 06:30, 18:00 und 18:30 Uhr"), ("0 6 1,15 * *", "am 1. und 15. des Monats um 06:00 Uhr"),
         ("0 6 1 jan,jul *", "am 1. des Monats im Januar und Juli um 06:00 Uhr"), ("0 6 1 * 1", "am 1. des Monats oder montags um 06:00 Uhr"),
         ("*/15 * * * 1", "montags alle 15 Minuten"), ("0 6 * 3 *", "jeden Tag im März um 06:00 Uhr"), ("0 * * 12 *", "jeden Tag im Dezember stündlich zur vollen Stunde"),
         ("0 9 * * 6-7", "samstags und sonntags um 09:00 Uhr"), ("0 6 1,10,15 * *", "am 1., 10. und 15. des Monats um 06:00 Uhr"),
         ("0 9 * * 5-7", "freitags bis sonntags um 09:00 Uhr"), ("0 9 * * 0-5", "montags, dienstags, mittwochs, donnerstags, freitags und sonntags um 09:00 Uhr"),
         ("0 9 * * 5,6,0,1", "montags, freitags, samstags und sonntags um 09:00 Uhr")]
for expr, want in table:
    assert describe(parse(expr)) == want, expr
for expr in ("* * * * *", "0 */2 * * *", "*/15 9-17 * * 1-5", "* 6 * * *", "0 0,1,2,3,4,5,6,7,8 * * *"):
    assert describe(parse(expr)) is None, expr
c = parse("0 6 1 * 1")
keep = copy.deepcopy(c)
describe(c)
assert c == keep
'''

H1 = {"hidden_cron_1.py": hidden("parse", C1)}
H2 = {**H1, "hidden_cron_2.py": hidden("parse, next_after", C2)}
H3 = {**H2, "hidden_cron_3.py": hidden("parse, next_after", C3)}
H4 = {**H3, "hidden_cron_4.py": hidden("parse, next_after", C4)}
H5 = {**H4, "hidden_cron_5.py": hidden("parse, due_between", C5)}
H6 = {**H5, "hidden_cron_6.py": hidden("parse, describe", C6)}

STAGES = [
    {"name": "parse",
     "task": """Create `cron.py` (Python 3 standard library only) with `parse(expr)` -> dict, a checked cron expression. expr is a string of exactly 5 fields separated by whitespace (leading and trailing spaces allowed): minute 0-59, hour 0-23, day 1-31, month 1-12, weekday 0-7 (0 and 7 are Sunday).
- A field is a comma list of parts; a part is '*', a number, a range 'a-b' (a <= b), each of them optionally with a step '/s' (s a positive integer). 'n/s' means from n to the field's maximum in steps of s ('10/20' minute = 10, 30, 50). Month names jan..dec and weekday names sun..sat are allowed (any case) wherever a number is; numbers are ASCII digits only.
- Result: {"minute": [...], "hour": [...], "day": [...], "month": [...], "weekday": [...]} each a sorted list of the matching values without doubles (weekday 7 becomes 0), plus "day_any" (the day field is exactly '*'), "weekday_any" (the weekday field is exactly '*'), "every" (s when the minute field is exactly '*/s', else None) and "text" (the five fields joined with one space).
- Errors: not a string or not exactly 5 fields -> ValueError('cron_invalid:fields'); otherwise the first bad field from the left -> ValueError('cron_invalid:<name>') with name minute, hour, day, month or weekday (unknown name, value out of range – this includes both ends of a range 'a-b' and the start n of 'n/s' –, empty part, step 0 or not a number, range with a > b).""",
     "hidden": H1},
    {"name": "match",
     "task": """Add `next_after(cron, after_utc, tz)` to `cron.py` (keep everything else). cron is the dict of parse; after_utc a UTC text '2026-10-21T08:00:00Z' (format '%Y-%m-%dT%H:%M:%SZ'); in this stage tz is always 'UTC'.
Return the first date of the expression STRICTLY after after_utc, as such a text (seconds 00). A minute matches when its minute, hour and month are in the lists and its day matches: when BOTH day_any and weekday_any are False, the day matches if its day of month OR its weekday is in the lists (classic cron); otherwise both must be in their lists. Weekday: 0 Sunday, 1 Monday ... 6 Saturday.
Search day by day from the day of after_utc on; on a matching day go through the listed hours and minutes in order (never minute by minute over years).""",
     "hidden": H2},
    {"name": "next",
     "task": """Extend `next_after(cron, after_utc, tz)` in `cron.py` (keep everything else):
- tz is 'UTC' (always works, no zone data needed), another zone name (looked up with zoneinfo.ZoneInfo, imported inside the lookup), or a datetime.tzinfo object (used as it is). Any other value, an empty name, or a name zoneinfo cannot load (any exception) -> ValueError('cron_timezone_unknown').
- The expression is matched in the LOCAL wall time of the zone: convert after_utc to local time, search from that local day and minute on, convert each candidate back to UTC and return the first one strictly after after_utc (a UTC text). Seconds of after_utc are allowed; dates always have seconds 00.
- When no date exists within 2930 days (8 years) of the search start, return None (e.g. '0 0 30 2 *').""",
     "hidden": H3},
    {"name": "dst",
     "task": """Daylight saving in `next_after` of `cron.py` (keep everything else). A local candidate is converted with fold=0 (`local.replace(tzinfo=zone, fold=0)`, then to UTC); it exists when converting that UTC time back to the zone gives the same wall time.
- Spring (skipped hour): a candidate that does not exist moves to the first existing local minute after it (step one minute until it exists); several candidates in the gap therefore give the same UTC time, and because the result must be strictly after after_utc that time is returned only once.
- Autumn (doubled hour): a wall time that occurs twice is taken at its first occurrence (fold=0) only; the second occurrence is never a date.
The tests give the zone as a tzinfo object with the EU rule (PEP 495 fold), so no zone data is needed.""",
     "hidden": H4},
    {"name": "due",
     "task": """Add `due_between(cron, from_utc, to_utc, tz, limit)` -> list to `cron.py` (keep everything else): all dates of the expression in (from_utc, to_utc] (from exclusive, to inclusive), in order, as UTC texts, computed with next_after (same tz rules, same errors), but at most limit + 1 entries – one more than the limit, so the caller sees that the list was capped. An empty interval or to before from gives [].""",
     "hidden": H5},
    {"name": "describe",
     "task": """Add `describe(cron)` -> German sentence or None to `cron.py` (keep everything else), display only, the same sentences as Shell D's cronText for these forms (anything else: None):
- time part: "every" set and all 24 hours -> 'alle <s> Minuten'; else all 60 minutes -> None; else all 24 hours: minutes [0] -> 'stündlich zur vollen Stunde', one minute -> 'stündlich zur Minute 15', more -> 'stündlich zu den Minuten 00 und 30'; else every hour x minute combination as 'HH:MM' (hour order, then minute order): at most 8 -> 'um 06:00, 06:30, 18:00 und 18:30 Uhr', more -> None. The first two kinds ('alle ...', 'stündlich ...') are a "pulse".
- day part: day field restricted (not day_any) -> 'am 1. und 15. des Monats'; weekday restricted -> the days in the order Monday..Sunday with the names sonntags, montags, dienstags, mittwochs, donnerstags, freitags, samstags: three or more days in an unbroken row of that order (Sunday is the last day, the row never wraps to Monday) -> 'montags bis freitags', else listed ('samstags und sonntags'); both restricted -> joined with ' oder '; none restricted -> 'jeden Tag'. Months, when not all 12: ' im ' + the month names (Januar, Februar, März, April, Mai, Juni, Juli, August, September, Oktober, November, Dezember) listed.
- Lists: one item as it is, more as 'a, b und c'. Sentence: 'jeden Tag' with a pulse and all months -> only the time part; else day part + month part + ' ' + time part (e.g. 'am 1. des Monats im Januar und Juli um 06:00 Uhr', 'montags alle 15 Minuten').""",
     "hidden": H6},
]
