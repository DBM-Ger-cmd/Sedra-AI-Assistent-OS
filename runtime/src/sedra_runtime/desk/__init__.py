"""The desk: where the desktop modules dock onto the runtime (SHELL_WERKZEUG_VERTRAG_v1 §10).

Build 7 lays down four pieces, with no change in behaviour and with the old routes untouched:

    registry.py   which shell is active, which tools exist (local_config/uix.yaml)
    gateway.py    manifests, files of registered folders, the API allowlist per tool
    decisions.py  one shape for mission gates, change requests and (Build 9) boundaries
    events.py     one stream (/api/events) instead of a poll per window

Build 8 adds objects.py, actions.py and live.py; Build 9 boundaries.py. The desk calls the runtime (brain, guard, missions,
library); it replaces nothing and writes nothing past a gate."""
from .decisions import collect, summary
from .events import EventStream, Poller, diff, sse
from .gateway import Gateway, route_allowed
from .registry import Registry, UixConfigError

__all__ = ['Gateway', 'Registry', 'UixConfigError', 'EventStream', 'Poller', 'collect', 'summary', 'diff', 'sse', 'route_allowed']
