def summarize(values):
    numbers = [v for v in (values if isinstance(values, (list, tuple)) else []) if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not numbers:
        return None
    ordered = sorted(numbers)
    middle = len(ordered) // 2
    median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    return {"count": len(ordered), "mean": round(sum(ordered) / len(ordered), 2), "median": median, "min": ordered[0], "max": ordered[-1]}
