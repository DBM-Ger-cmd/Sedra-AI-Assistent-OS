import json


def sse_frame(obj):
    return b"data: " + json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n\n"


def stream_frames(deltas, model, max_chars=8000):
    used = 0
    truncated = False
    error = None
    try:
        for delta in deltas:
            if not isinstance(delta, str) or not delta:
                continue
            piece = delta[:max_chars - used]
            used += len(piece)
            yield sse_frame({"delta": piece})
            if used >= max_chars:
                truncated = len(piece) < len(delta) or truncated
                break
    except Exception as exc:
        error = str(exc)[:200]
    last = {"done": True, "model": model, "truncated": truncated}
    if error is not None:
        last["error"] = error
    yield sse_frame(last)
