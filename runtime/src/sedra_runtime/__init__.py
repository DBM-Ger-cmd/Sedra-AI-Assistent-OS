__version__ = "1.20.0"

# Übergang (vor 1.23.0): alte Umgebungsvariablen gelten weiter und werden auf die SEDRA-Namen gespiegelt.
from . import legacy_names as _legacy_names

_legacy_names.env_aliase()
