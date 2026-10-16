"""Strict YAML loading for agent manager imports (host side; the microVM never parses YAML).

`yaml.safe_load` silently overwrites duplicate keys and resolves anchors, aliases and tags, so an imported template could hide a value. This loader refuses all of that:
duplicate keys, anchors and aliases, tags (also `<<` merge keys), keys that are not strings, non-finite numbers, more than MAX_BYTES bytes and nesting deeper than MAX_DEPTH.
It returns plain dict/list/str/int/float/bool/None, nothing else, and raises ContractError with the code "yaml_refused".
"""
import math

import yaml

from .agent_contracts import ContractError

MAX_BYTES = 262144
MAX_DEPTH = 32


class _StrictLoader(yaml.SafeLoader):
    pass


def _refuse(message, node=None):
    line = f" (line {node.start_mark.line + 1})" if node is not None else ""
    raise ContractError("yaml_refused", message + line)


def _construct_mapping(loader, node, deep=False):
    if node.tag == "tag:yaml.org,2002:merge":
        _refuse("merge keys are refused", node)
    seen = set()
    for key_node, _ in node.value:
        if key_node.tag == "tag:yaml.org,2002:merge":
            _refuse("merge keys are refused", key_node)
        if not isinstance(key_node, yaml.ScalarNode) or key_node.tag != "tag:yaml.org,2002:str":
            _refuse("only plain string keys are allowed", key_node)
        if key_node.value in seen:
            _refuse(f"duplicate key {key_node.value!r}", key_node)
        seen.add(key_node.value)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


_StrictLoader.add_constructor("tag:yaml.org,2002:map", _construct_mapping)


def _check_events(text):
    depth = 0
    for event in yaml.parse(text, Loader=_StrictLoader):
        if isinstance(event, yaml.AliasEvent):
            _refuse("aliases are refused", event)
        anchor = getattr(event, "anchor", None)
        if anchor is not None:
            _refuse("anchors are refused", event)
        if getattr(event, "tag", None) is not None:
            _refuse("explicit tags are refused", event)
        if isinstance(event, (yaml.MappingStartEvent, yaml.SequenceStartEvent)):
            depth += 1
            if depth > MAX_DEPTH:
                _refuse("nesting is too deep", event)
        elif isinstance(event, (yaml.MappingEndEvent, yaml.SequenceEndEvent)):
            depth -= 1


def _check_values(value):
    if isinstance(value, float) and not math.isfinite(value):
        _refuse("non-finite numbers are refused")
    if isinstance(value, dict):
        for item in value.values():
            _check_values(item)
    elif isinstance(value, list):
        for item in value:
            _check_values(item)
    elif not (value is None or isinstance(value, (str, int, float, bool))):
        _refuse(f"values of type {type(value).__name__} are refused")


def load_strict(data):
    """Parse YAML text or bytes. Exactly one document is allowed."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    if not isinstance(data, (bytes, bytearray)):
        raise ContractError("yaml_refused", "the input must be text or bytes")
    if len(data) > MAX_BYTES:
        raise ContractError("yaml_refused", f"the input is larger than {MAX_BYTES} bytes")
    try:
        text = bytes(data).decode("utf-8")
        _check_events(text)
        documents = list(yaml.load_all(text, Loader=_StrictLoader))
    except ContractError:
        raise
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise ContractError("yaml_refused", f"not valid YAML: {str(exc)[:120]}") from None
    if len(documents) != 1:
        raise ContractError("yaml_refused", "exactly one YAML document is required")
    _check_values(documents[0])
    return documents[0]
