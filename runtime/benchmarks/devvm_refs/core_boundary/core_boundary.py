import ast
from collections import deque


def _inside(name, groups):
    return any(name == group or name.startswith(group + ".") for group in groups)


def _base(module, level):
    parts = module.split(".")
    if level >= len(parts):
        raise ValueError("relative_import_beyond_top")
    return ".".join(parts[:-level])


def imports_of(source, module):
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError("unparsable") from exc
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level:
            base = _base(module, node.level)
            if node.module:
                found.add(base + "." + node.module)
            else:
                found.update(base + "." + alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add(node.module)
    return sorted(found)


def violations(sources, core, forbidden):
    found = set()
    for module in sorted(sources):
        if _inside(module, core):
            found.update((module, name) for name in imports_of(sources[module], module) if _inside(name, forbidden))
    return sorted(found)


def chains(sources, core, forbidden):
    paths = []
    for start in sorted(sources):
        if not _inside(start, core):
            continue
        queue, seen = deque([[start]]), {start}
        while queue:
            path = queue.popleft()
            hit = None
            for name in imports_of(sources[path[-1]], path[-1]):
                if _inside(name, forbidden):
                    hit = path + [name]
                    break
                if name in sources and name not in seen:
                    seen.add(name)
                    queue.append(path + [name])
            if hit:
                paths.append(hit)
                break
    return paths
