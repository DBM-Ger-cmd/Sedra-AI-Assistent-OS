import datetime
from collections import defaultdict

def _is_valid_record(record):
    if not isinstance(record, dict):
        return False
    if record.get("author") not in ("guppi", "claude"):
        return False
    try:
        datetime.date.fromisoformat(record.get("date", ""))
    except (ValueError, TypeError):
        return False
    added = record.get("added")
    if added is None or not isinstance(added, int) or added < 0:
        return False
    if isinstance(added, bool):
        return False
    return True

def _normalize_date(date_str):
    return datetime.date.fromisoformat(date_str).isoformat()

def daily_totals(records):
    totals = defaultdict(lambda: {"guppi": 0, "claude": 0})
    
    for record in records:
        if not _is_valid_record(record):
            continue
            
        date = _normalize_date(record["date"])
        author = record["author"]
        added = record["added"]
        
        totals[date][author] += added
    
    result = {}
    for date in sorted(totals.keys()):
        result[date] = totals[date]
    
    return result

def _get_week_start(date_str):
    date = datetime.date.fromisoformat(date_str)
    days_since_monday = date.weekday()
    monday = date - datetime.timedelta(days=days_since_monday)
    return monday.isoformat()

def _get_weeks_range(today, weeks):
    today_date = datetime.date.fromisoformat(today)
    start_date = today_date - datetime.timedelta(weeks=weeks-1)
    start_monday = start_date - datetime.timedelta(days=start_date.weekday())
    
    weeks_list = []
    for i in range(weeks):
        week_start = start_monday + datetime.timedelta(weeks=i)
        weeks_list.append(week_start.isoformat())
    
    return weeks_list

def _get_active_days(daily):
    return [date for date, data in daily.items() if data["guppi"] + data["claude"] > 0]

def _get_peak_date(daily):
    if not daily:
        return None
    
    max_lines = 0
    peak_date = None
    
    for date, data in daily.items():
        total_lines = data["guppi"] + data["claude"]
        if total_lines > max_lines:
            max_lines = total_lines
            peak_date = date
        elif total_lines == max_lines and max_lines > 0:
            if peak_date is None or date < peak_date:
                peak_date = date
    
    return peak_date

def _get_last_30_days(daily, today):
    today_date = datetime.date.fromisoformat(today)
    last_30_lines = 0
    
    for i in range(30):
        date = today_date - datetime.timedelta(days=i)
        date_str = date.isoformat()
        data = daily.get(date_str, {"guppi": 0, "claude": 0})
        last_30_lines += data["guppi"] + data["claude"]
    
    return last_30_lines

def cards(daily, today):
    total_lines = 0
    guppi_lines = 0
    claude_lines = 0
    
    for data in daily.values():
        total_lines += data["guppi"] + data["claude"]
        guppi_lines += data["guppi"]
        claude_lines += data["claude"]
    
    if total_lines == 0:
        guppi_share = 0
    else:
        guppi_share = (guppi_lines * 100 + total_lines // 2) // total_lines
    
    active_days = len(_get_active_days(daily))
    
    peak_date = _get_peak_date(daily)
    
    last_30_lines = _get_last_30_days(daily, today)
    
    return {
        "total_lines": total_lines,
        "guppi_lines": guppi_lines,
        "claude_lines": claude_lines,
        "guppi_share": guppi_share,
        "active_days": active_days,
        "peak_date": peak_date,
        "last_30_lines": last_30_lines
    }

def heatmap(daily, today, weeks=20):
    weeks_list = _get_weeks_range(today, weeks)
    
    grid = []
    for day_of_week in range(7):
        row = []
        for week_start in weeks_list:
            date = datetime.date.fromisoformat(week_start) + datetime.timedelta(days=day_of_week)
            date_str = date.isoformat()
            
            if date > datetime.date.fromisoformat(today):
                row.append(None)
            else:
                data = daily.get(date_str, {"guppi": 0, "claude": 0})
                lines = data["guppi"] + data["claude"]
                row.append({
                    "date": date_str,
                    "guppi": data["guppi"],
                    "claude": data["claude"],
                    "lines": lines,
                    "level": 0
                })
        grid.append(row)
    
    peak = 0
    for row in grid:
        for cell in row:
            if cell is not None and cell["lines"] > peak:
                peak = cell["lines"]
    
    for row in grid:
        for cell in row:
            if cell is not None:
                if peak > 0:
                    cell["level"] = 1 + (cell["lines"] * 4 - 1) // peak
                else:
                    cell["level"] = 0
    
    return grid