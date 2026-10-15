import ast


def _resolve_relative(module, level):
    parts = module.split(".")
    if level >= len(parts):
        raise ValueError("relative_import_beyond_top")
    base_parts = parts[:len(parts) - level]
    return ".".join(base_parts)


def _collect_imports(node, module):
    names = []
    for child in ast.walk(node):
        if isinstance(child, ast.Import):
            for alias in child.names:
                names.append(alias.name)
        elif isinstance(child, ast.ImportFrom):
            level = child.level or 0
            if level > 0:
                base = _resolve_relative(module, level)
            else:
                base = None
            if child.module:
                if level > 0:
                    names.append(base + "." + child.module)
                else:
                    names.append(child.module)
            else:
                if level > 0:
                    for alias in child.names:
                        names.append(base + "." + alias.name)
    return names


def imports_of(source, module):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        raise ValueError("unparsable")
    names = _collect_imports(tree, module)
    return sorted(set(names))


def _belongs_to_group(name, group):
    return name == group or name.startswith(group + ".")


def _is_in_any_group(name, groups):
    return any(_belongs_to_group(name, g) for g in groups)


def violations(sources, core, forbidden):
    core_set = set(core)
    forbidden_set = set(forbidden)
    result = set()
    for module, source in sources.items():
        if not _is_in_any_group(module, core):
            continue
        names = imports_of(source, module)
        for name in names:
            if _is_in_any_group(name, forbidden):
                result.add((module, name))
    return sorted(result)

def chains(sources, core, forbidden):
    core_set = set(core)
    forbidden_set = set(forbidden)
    result = []
    for start in sorted(sources.keys()):
        if not _is_in_any_group(start, core):
            continue
        seen = {start}
        queue = [[start]]
        found = None
        while queue and found is None:
            path = queue.pop(0)
            last = path[-1]
            source = sources[last]
            names = imports_of(source, last)
            for name in names:
                if _is_in_any_group(name, forbidden):
                    found = path + [name]
                    break
                if name in sources and name not in seen:
                    seen.add(name)
                    queue.append(path + [name])
        if found is not None:
            result.append(found)
    return result
