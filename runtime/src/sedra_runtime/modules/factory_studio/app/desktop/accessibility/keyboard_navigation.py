"""Keyboard Navigation Helper — WinUI 3 Tastatur-Navigation für Factory Studio."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable
from enum import Enum

from sedra_runtime.modules.factory_studio._mvvm import ObservableObject, RelayCommand


class NavigationDirection(Enum):
    """Navigations-Richtung."""
    NEXT = "next"
    PREVIOUS = "previous"
    FIRST = "first"
    LAST = "last"
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


@dataclass
class Shortcut:
    """Tastatur-Shortcut Definition."""
    key: str  # z.B. "Ctrl+N", "F5", "Delete"
    description: str
    command: Any  # RelayCommand oder Callable
    category: str = "General"
    enabled: bool = True


class ShortcutManager(ObservableObject):
    """Verwaltet globale Tastatur-Shortcuts."""
    
    def __init__(self):
        self._shortcuts: dict[str, Shortcut] = {}
        self._category_shortcuts: dict[str, list[Shortcut]] = {}
    
    def register(self, shortcut: Shortcut):
        """Registriert einen Shortcut."""
        self._shortcuts[shortcut.key.lower()] = shortcut
        
        if shortcut.category not in self._category_shortcuts:
            self._category_shortcuts[shortcut.category] = []
        self._category_shortcuts[shortcut.category].append(shortcut)
    
    def unregister(self, key: str):
        """Entfernt einen Shortcut."""
        key = key.lower()
        if key in self._shortcuts:
            shortcut = self._shortcuts.pop(key)
            if shortcut.category in self._category_shortcuts:
                self._category_shortcuts[shortcut.category].remove(shortcut)
    
    def get_shortcut(self, key: str) -> Shortcut | None:
        return self._shortcuts.get(key.lower())
    
    def get_category_shortcuts(self, category: str) -> list[Shortcut]:
        return self._category_shortcuts.get(category, [])
    
    def get_all_shortcuts(self) -> list[Shortcut]:
        return list(self._shortcuts.values())
    
    async def handle_key(self, key: str, modifiers: list[str] = None):
        """Behandelt Tastendruck."""
        modifiers = modifiers or []
        key_combo = "+".join(sorted([m.lower() for m in modifiers] + [key.lower()]))
        
        shortcut = self.get_shortcut(key_combo)
        if shortcut and shortcut.enabled:
            if callable(shortcut.command):
                if asyncio.iscoroutinefunction(shortcut.command):
                    await shortcut.command()
                else:
                    shortcut.command()
            return True
        return False


class FocusManager(ObservableObject):
    """Fokus-Management für komplexe UI."""
    
    def __init__(self):
        self._focus_stack: list[Any] = []  # Fokus-History
        self._focused_element: Any = None
        self._focus_restored_callback: Callable[[Any], None] | None = None
    
    @property
    def focused_element(self) -> Any:
        return self._focused_element
    
    def set_focus(self, element: Any, record_history: bool = True):
        """Setzt Fokus auf Element."""
        if self._focused_element and record_history:
            self._focus_stack.append(self._focused_element)
        
        self._focused_element = element
        # In echt: element.Focus(FocusState.Programmatic)
    
    def restore_focus(self):
        """Stellt vorherigen Fokus wieder her."""
        if self._focus_stack:
            previous = self._focus_stack.pop()
            self.set_focus(previous, record_history=False)
    
    def clear_history(self):
        self._focus_stack.clear()
    
    def set_focus_restored_callback(self, callback: Callable[[Any], None]):
        self._focus_restored_callback = callback


class TabNavigation(ObservableObject):
    """Tab-Navigation zwischen Views/Tabs."""
    
    def __init__(self, tab_items: list[Any]):
        self.tab_items = tab_items
        self._current_index = 0
        self._wrap_around = True
    
    @property
    def current_index(self) -> int:
        return self._current_index
    
    @property
    def current_item(self) -> Any:
        if 0 <= self._current_index < len(self.tab_items):
            return self.tab_items[self._current_index]
        return None
    
    def next(self) -> bool:
        """Nächstes Tab."""
        if self._current_index < len(self.tab_items) - 1:
            self._current_index += 1
            return True
        elif self._wrap_around:
            self._current_index = 0
            return True
        return False
    
    def previous(self) -> bool:
        """Vorheriges Tab."""
        if self._current_index > 0:
            self._current_index -= 1
            return True
        elif self._wrap_around:
            self._current_index = len(self.tab_items) - 1
            return True
        return False
    
    def first(self) -> bool:
        if self.tab_items:
            self._current_index = 0
            return True
        return False
    
    def last(self) -> bool:
        if self.tab_items:
            self._current_index = len(self.tab_items) - 1
            return True
        return False
    
    def go_to(self, index: int) -> bool:
        if 0 <= index < len(self.tab_items):
            self._current_index = index
            return True
        return False


class KeyboardNavigationHelper:
    """Hilfsklasse für Tastatur-Navigation in komplexen Controls."""
    
    # Standard Shortcuts für Factory Studio
    DEFAULT_SHORTCUTS = {
        # Navigation
        "Ctrl+Tab": ("Next Tab", "next_tab"),
        "Ctrl+Shift+Tab": ("Previous Tab", "prev_tab"),
        "Ctrl+1": ("Tab 1", "tab_1"),
        "Ctrl+2": ("Tab 2", "tab_2"),
        "Ctrl+3": ("Tab 3", "tab_3"),
        "Ctrl+4": ("Tab 4", "tab_4"),
        
        # Project Browser
        "Ctrl+N": ("New Project", "create_project"),
        "F5": ("Refresh", "refresh"),
        "Delete": ("Delete Selected", "delete"),
        "F2": ("Rename", "rename"),
        "Enter": ("Open/Select", "open"),
        
        # Graph View
        "Ctrl++": ("Zoom In", "zoom_in"),
        "Ctrl+-": ("Zoom Out", "zoom_out"),
        "Ctrl+0": ("Reset Zoom", "reset_zoom"),
        "R": ("Relayout", "relayout"),
        
        # Execution
        "Ctrl+B": ("Run Benchmark", "run_benchmark"),
        "Ctrl+E": ("Export", "export"),
        
        # Gates
        "Ctrl+A": ("Approve", "approve"),
        "Ctrl+R": ("Reject", "reject"),
        
        # General
        "Escape": ("Cancel/Close", "cancel"),
        "F1": ("Help", "help"),
    }
    
    @classmethod
    def create_shortcut_manager(cls) -> ShortcutManager:
        """Erstellt ShortcutManager mit Factory Studio Defaults."""
        manager = ShortcutManager()
        
        for key, (desc, action) in cls.DEFAULT_SHORTCUTS.items():
            shortcut = Shortcut(
                key=key,
                description=desc,
                command=action,
                category=cls._get_category(key),
            )
            manager.register(shortcut)
        
        return manager
    
    @staticmethod
    def _get_category(key: str) -> str:
        if key.startswith("Ctrl+Tab") or key.startswith("Ctrl+Shift+Tab") or key.startswith("Ctrl+1") or key.startswith("Ctrl+2"):
            return "Navigation"
        elif key in ["Ctrl+N", "F5", "Delete", "F2", "Enter"]:
            return "Project Browser"
        elif key in ["Ctrl++", "Ctrl+-", "Ctrl+0", "R"]:
            return "Graph View"
        elif key in ["Ctrl+B", "Ctrl+E"]:
            return "Execution"
        elif key in ["Ctrl+A", "Ctrl+R"]:
            return "Gates"
        return "General"


# =============================================================================
# XAML Helpers für KeyboardNavigation
# =============================================================================

KEYBOARD_NAVIGATION_XAML = """
<!-- 
KeyboardNavigation Helpers für XAML
Verwendung in Page/UserControl Resources:
-->

<ResourceDictionary
    xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">

    <!-- TabNavigation für Container -->
    <Style TargetType="Grid" x:Key="TabNavigableGridStyle">
        <Setter Property="TabNavigation" Value="Cycle"/>
        <Setter Property="KeyboardNavigation.TabNavigation" Value="Cycle"/>
        <Setter Property="KeyboardNavigation.ControlTabNavigation" Value="Cycle"/>
        <Setter Property="KeyboardNavigation.DirectionalNavigation" Value="Cycle"/>
    </Style>

    <Style TargetType="StackPanel" x:Key="TabNavigableStackPanelStyle">
        <Setter Property="KeyboardNavigation.TabNavigation" Value="Cycle"/>
        <Setter Property="KeyboardNavigation.DirectionalNavigation" Value="Cycle"/>
    </Style>

    <!-- Focus Visual für alle Controls -->
    <Style TargetType="Control" x:Key="EnhancedFocusStyle">
        <Setter Property="FocusVisualMargin" Value="-3"/>
        <Setter Property="FocusVisualPrimaryBrush" Value="{ThemeResource SystemControlFocusVisualPrimaryBrush}"/>
        <Setter Property="FocusVisualSecondaryBrush" Value="{ThemeResource SystemControlFocusVisualSecondaryBrush}"/>
        <Setter Property="FocusVisualPrimaryThickness" Value="3"/>
        <Setter Property="FocusVisualSecondaryThickness" Value="2"/>
    </Style>

    <!-- AccessKey für Menüs/Buttons -->
    <Style TargetType="Button" x:Key="AccessKeyButtonStyle" BasedOn="{StaticResource DefaultButtonStyle}">
        <Setter Property="AccessKey" Value="{Binding AccessKey, RelativeSource={RelativeSource Self}}"/>
    </Style>

    <!-- ToolTip für Keyboard Shortcuts -->
    <Style TargetType="Button" x:Key="ShortcutTooltipButtonStyle" BasedOn="{StaticResource DefaultButtonStyle}">
        <Setter Property="ToolTipService.ToolTip">
            <Setter.Value>
                <ToolTip Content="{Binding ShortcutDescription, RelativeSource={RelativeSource Self}}"/>
            </Setter.Value>
        </Setter>
    </Style>
</ResourceDictionary>
"""


# =============================================================================
# Factory Studio Default Shortcuts Registration
# =============================================================================

class NavigationDirection(Enum):
    """Navigations-Richtung."""
    NEXT = "next"
    PREVIOUS = "previous"
    FIRST = "first"
    LAST = "last"
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


def create_factory_studio_shortcuts() -> ShortcutManager:
    """Erstellt ShortcutManager mit allen Factory Studio Shortcuts."""
    manager = KeyboardNavigationHelper.create_shortcut_manager()
    return manager


def register_view_shortcuts(view_model: Any, shortcut_manager: ShortcutManager):
    """Registriert View-spezifische Shortcuts."""
    # Project Browser
    if hasattr(view_model, 'create_project_command'):
        shortcut_manager.register(Shortcut(
            key="Ctrl+N",
            description="Neues Projekt erstellen",
            command=view_model.create_project_command,
            category="Project Browser",
        ))
    
    if hasattr(view_model, 'refresh_command'):
        shortcut_manager.register(Shortcut(
            key="F5",
            description="Aktualisieren",
            command=view_model.refresh_command,
            category="General",
        ))
    
    if hasattr(view_model, 'delete_project_command'):
        shortcut_manager.register(Shortcut(
            key="Delete",
            description="Projekt löschen",
            command=view_model.delete_project_command,
            category="Project Browser",
        ))
    
    # Graph View
    if hasattr(view_model, 'zoom_in_command'):
        shortcut_manager.register(Shortcut(
            key="Ctrl++",
            description="Vergrößern",
            command=view_model.zoom_in_command,
            category="Graph View",
        ))
    
    if hasattr(view_model, 'relayout_command'):
        shortcut_manager.register(Shortcut(
            key="R",
            description="Layout neu berechnen",
            command=view_model.relayout_command,
            category="Graph View",
        ))
    
    # Execution
    if hasattr(view_model, 'run_benchmark_command'):
        shortcut_manager.register(Shortcut(
            key="Ctrl+B",
            description="Benchmark starten",
            command=view_model.run_benchmark_command,
            category="Execution",
        ))
    
    # Gates
    if hasattr(view_model, 'approve_gate_command'):
        shortcut_manager.register(Shortcut(
            key="Ctrl+A",
            description="Genehmigen",
            command=view_model.approve_gate_command,
            category="Gates",
        ))
    
    if hasattr(view_model, 'reject_gate_command'):
        shortcut_manager.register(Shortcut(
            key="Ctrl+R",
            description="Ablehnen",
            command=view_model.reject_gate_command,
            category="Gates",
        ))

    return shortcut_manager
