"""Minimale MVVM-Basis fuer das Factory-Studio-Modul.

Ersetzt das nicht verfuegbare Paket `communitytoolkit_mvvm` (es gibt es nicht auf PyPI).
Umfang nur das, was die Module nutzen:
- ObservableObject: Eigenschaftsaenderungen melden (notify_property_changed, set_property)
- ObservableCollection: Liste, die bei Aenderungen meldet
- RelayCommand: Befehl mit execute und optionalem can_execute
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Optional


class ObservableObject:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._property_changed_handlers: list[Callable[[str], None]] = []

    def add_property_changed(self, handler: Callable[[str], None]) -> None:
        self._property_changed_handlers.append(handler)

    def remove_property_changed(self, handler: Callable[[str], None]) -> None:
        if handler in self._property_changed_handlers:
            self._property_changed_handlers.remove(handler)

    def notify_property_changed(self, name: str) -> None:
        for handler in list(self.__dict__.get("_property_changed_handlers", [])):
            handler(name)

    def set_property(self, name: str, value: Any) -> bool:
        """Setzt das Attribut und meldet nur bei geaenderten Werten."""
        if getattr(self, name, None) == value:
            return False
        setattr(self, name, value)
        self.notify_property_changed(name)
        return True


class ObservableCollection(list):
    def __init__(self, items: Optional[Iterable[Any]] = None) -> None:
        super().__init__(items or [])
        self._changed_handlers: list[Callable[[], None]] = []

    def add_changed(self, handler: Callable[[], None]) -> None:
        self._changed_handlers.append(handler)

    def _changed(self) -> None:
        for handler in list(self.__dict__.get("_changed_handlers", [])):
            handler()

    def append(self, item: Any) -> None:
        super().append(item)
        self._changed()

    def extend(self, items: Iterable[Any]) -> None:
        super().extend(items)
        self._changed()

    def insert(self, index: int, item: Any) -> None:
        super().insert(index, item)
        self._changed()

    def remove(self, item: Any) -> None:
        super().remove(item)
        self._changed()

    def clear(self) -> None:
        super().clear()
        self._changed()


class RelayCommand:
    def __init__(self, execute: Callable[..., Any],
                 can_execute: Optional[Callable[..., bool]] = None) -> None:
        self._execute = execute
        self._can_execute = can_execute

    def can_execute(self, parameter: Any = None) -> bool:
        if self._can_execute is None:
            return True
        return bool(self._can_execute(parameter))

    def execute(self, parameter: Any = None) -> Any:
        if not self.can_execute(parameter):
            return None
        return self._execute(parameter) if parameter is not None else self._execute()
