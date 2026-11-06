def _check_int(v, lowest, name):
    if type(v) is not int or v < lowest:
        raise ValueError(f"{name} must be an int >= {lowest}")

def _is_tool_str(msg):
    return msg.get("role") == "tool" and isinstance(msg.get("content"), str)

def _shorten_content(content, max_lines):
    lines = content.split("\n")
    total = len(lines)
    keep_first = max_lines // 2
    keep_last = max_lines // 4
    cut = total - keep_first - keep_last
    first_part = lines[:keep_first]
    last_part = lines[-keep_last:]
    ellipsis = f"[... {cut} lines cut: read the file again if you need them ...]"
    result_parts = first_part + [ellipsis] + last_part
    return "\n".join(result_parts)

def _mark_duplicate_tool_messages(messages):
    tool_indices = [i for i, msg in enumerate(messages) if _is_tool_str(msg)]
    content_to_latest = {}
    for i in reversed(tool_indices):
        content = messages[i]["content"]
        if len(content) > 200:
            if content not in content_to_latest:
                content_to_latest[content] = i
    result = list(messages)
    for i in tool_indices:
        content = messages[i]["content"]
        if len(content) > 200 and content in content_to_latest:
            latest_idx = content_to_latest[content]
            if i != latest_idx:
                new_msg = dict(messages[i])
                new_msg["content"] = "[same result as a later call]"
                result[i] = new_msg
    return result

def prune(messages, keep_last=6, max_lines=40):
    _check_int(keep_last, 0, "keep_last")
    _check_int(max_lines, 4, "max_lines")
    messages = _mark_duplicate_tool_messages(messages)
    result = []
    tool_count = sum(1 for m in messages if _is_tool_str(m))
    tool_seen = 0
    for msg in messages:
        if _is_tool_str(msg):
            tool_seen += 1
            remaining = tool_count - tool_seen
            if remaining >= keep_last and _is_shortenable(msg, max_lines):
                new_msg = dict(msg)
                new_msg["content"] = _shorten_content(msg["content"], max_lines)
                result.append(new_msg)
            else:
                result.append(msg)
        else:
            result.append(msg)
    return result

def _is_shortenable(msg, max_lines):
    return (_is_tool_str(msg)
            and len(msg["content"].split("\n")) > max_lines)
