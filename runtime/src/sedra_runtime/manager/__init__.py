"""Der Manager von SEDRA: Verfassung (verfassung.md) und Gesetze (gesetze.yaml), geprüft in verfassung.py."""
from .verfassung import Manager, VerfassungsVerstoss, lade_gesetze

__all__ = ["Manager", "VerfassungsVerstoss", "lade_gesetze"]
