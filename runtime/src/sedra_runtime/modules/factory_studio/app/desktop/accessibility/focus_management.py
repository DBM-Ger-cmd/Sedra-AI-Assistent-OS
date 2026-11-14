"""Focus Management — Factory Studio Fokus-Management (Focus Scope, Restore, Trap)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from contextlib import contextmanager
from sedra_runtime.modules.factory_studio._mvvm import ObservableObject


@dataclass
class FocusState:
    """Gespeicherter Fokus-Zustand."""
    element: Any
    timestamp: float
    context: str = ""


class FocusScope(ObservableObject):
    """Fokus-Bereich (Scope) für modulare UI-Bereiche.
    
    Jeder Scope hat eigenen Fokus-Stack und kann unabhängig
    Fokus verwalten (z.B. Dialog, Flyout, Panel).
    """
    
    def __init__(self, name: str, parent: Optional["FocusScope"] = None):
        self.name = name
        self.parent = parent
        self._focus_stack: list[Any] = []
        self._current_focus: Any = None
        self._is_active = False
        
        # Children Scopes
        self._children: list[FocusScope] = []
        if parent:
            parent._children.append(self)
    
    @property
    def is_active(self) -> bool:
        return self._is_active
    
    @property
    def current_focus(self) -> Any:
        return self._current_focus
    
    def activate(self):
        """Aktiviert Scope (Fokus wird hier verwaltet)."""
        self._is_active = True
    
    def deactivate(self):
        """Deaktiviert Scope."""
        self._is_active = False
    
    def set_focus(self, element: Any):
        """Setzt Fokus innerhalb dieses Scope."""
        if self._current_focus:
            self._focus_stack.append(self._current_focus)
        self._current_focus = element
        # element.Focus(FocusState.Programmatic)
    
    def restore_focus(self) -> bool:
        """Stellt letzten Fokus in diesem Scope wieder her."""
        if self._focus_stack:
            previous = self._focus_stack.pop()
            self._current_focus = previous
            return True
        return False
    
    def clear_stack(self):
        self._focus_stack.clear()
    
    def get_focus_path(self) -> list[Any]:
        """Gibt Fokus-Pfad von Root bis aktuell."""
        path = []
        current = self
        while current:
            if current._current_focus:
                path.append(current._current_focus)
            current = current.parent
        return list(reversed(path))


class FocusTrap(ObservableObject):
    """Fokus-Falle für modale Dialogs/Flyouts.
    
    Hält Fokus innerhalb eines Containers (Tab/Shift+Tab zirkulieren).
    """
    
    def __init__(self, container: Any, restore_on_release: bool = True):
        self.container = container
        self.restore_on_release = restore_on_release
        self._previous_focus: Any = None
        self._is_active = False
        self._first_focusable: Any = None
        self._last_focusable: Any = None
    
    @property
    def is_active(self) -> bool:
        return self._is_active
    
    def activate(self):
        """Aktiviert Fokus-Falle."""
        if self._is_active:
            return
        
        # Vorherigen Fokus merken
        self._previous_focus = self._get_current_focus()
        
        # Erste/Letzte fokussierbare Elemente finden
        self._scan_focusable_elements()
        
        # Fokus auf erstes Element setzen
        if self._first_focusable:
            self._set_focus(self._first_focusable)
        
        self._is_active = True
        
        # Event Handler registrieren (Tab/Shift+Tab)
        self._register_key_handlers()
    
    def deactivate(self):
        """Deaktiviert Fokus-Falle."""
        if not self._is_active:
            return
        
        self._unregister_key_handlers()
        
        if self.restore_on_release and self._previous_focus:
            self._set_focus(self._previous_focus)
        
        self._is_active = False
    
    def _get_current_focus(self) -> Any:
        # In echt: FocusManager.GetFocusedElement()
        return None
    
    def _scan_focusable_elements(self):
        # Findet alle fokussierbaren Elemente im Container
        # TabIndex >= 0, nicht Hidden, nicht Disabled
        self._first_focusable = None
        self._last_focusable = None
    
    def _register_key_handlers(self):
        # Registriert Tab/Shift+Tab Handler für Zirkulation
        pass
    
    def _unregister_key_handlers(self):
        pass
    
    def _set_focus(self, element: Any):
        pass


class FocusRestorer(ObservableObject):
    """Stellt Fokus nach Operationen wieder her (Async/Ops)."""
    
    def __init__(self):
        self._saved_states: dict[str, Any] = {}
        self._auto_restore = True
    
    def save(self, key: str, element: Any):
        """Speichert Fokus für Key."""
        self._saved_states[key] = element
    
    def restore(self, key: str) -> bool:
        """Stellt Fokus für Key wieder her."""
        if key in self._saved_states:
            element = self._saved_states.pop(key)
            # element.Focus(FocusState.Programmatic)
            return True
        return False
    
    def restore_all(self):
        """Stellt alle gespeicherten Fokusse wieder her."""
        for key, element in self._saved_states.items():
            # element.Focus(FocusState.Programmatic)
            pass
        self._saved_states.clear()
    
    def clear(self, key: Optional[str] = None):
        if key:
            self._saved_states.pop(key, None)
        else:
            self._saved_states.clear()
    
    @contextmanager
    def save_restore(self, key: str):
        """Context Manager für Save/Restore."""
        self.save(key, self._get_current_focus())
        try:
            yield
        finally:
            if self._auto_restore:
                self.restore(key)
    
    def _get_current_focus(self) -> Any:
        return None


class FocusManager(ObservableObject):
    """Zentraler Fokus-Manager für gesamte App."""
    
    def __init__(self):
        self._root_scope = FocusScope("root")
        self._current_scope = self._root_scope
        self._focus_traps: list[Any] = []
        self._focus_restorer = FocusRestorer()
        self._global_shortcuts: dict[str, Any] = {}
    
    @property
    def root_scope(self) -> FocusScope:
        return self._root_scope
    
    @property
    def current_scope(self) -> FocusScope:
        return self._current_scope
    
    @property
    def focus_restorer(self) -> FocusRestorer:
        return self._focus_restorer
    
    def push_scope(self, name: str) -> FocusScope:
        """Erstellt neuen Child-Scope und macht ihn aktuell."""
        new_scope = FocusScope(name, self._current_scope)
        self._current_scope = new_scope
        return new_scope
    
    def pop_scope(self) -> Optional[FocusScope]:
        """Entfernt aktuellen Scope, kehrt zu Parent zurück."""
        if self._current_scope.parent:
            popped = self._current_scope
            self._current_scope = self._current_scope.parent
            return popped
        return None
    
    def activate_trap(self, container: Any, restore_on_release: bool = True) -> Any:
        """Aktiviert Focus Trap für Container."""
        trap = FocusTrap(container, restore_on_release)
        trap.activate()
        self._focus_traps.append(trap)
        return trap
    
    def deactivate_trap(self, trap: Any):
        """Deaktiviert Focus Trap."""
        if trap in self._focus_traps:
            trap.deactivate()
            self._focus_traps.remove(trap)
    
    def deactivate_all_traps(self):
        for trap in self._focus_traps:
            trap.deactivate()
        self._focus_traps.clear()
    
    def register_global_shortcut(self, key: str, callback: Any):
        self._global_shortcuts[key] = callback
    
    def handle_key(self, key: str, modifiers: list[str] = None) -> bool:
        """Behandelt globale Tastatur-Shortcuts."""
        combo = "+".join(sorted([m.lower() for m in (modifiers or [])] + [key.lower()]))
        if combo in self._global_shortcuts:
            self._global_shortcuts[combo]()
            return True
        return False
    
    def get_focus_path(self) -> list[Any]:
        """Gibt aktuellen Fokus-Pfad zurück."""
        return self._current_scope.get_focus_path()
    
    def save_focus(self, key: str):
        self._focus_restorer.save(key, self._get_current_focus())
    
    def restore_focus(self, key: str) -> bool:
        return self._focus_restorer.restore(key)
    
    def _get_current_focus(self) -> Any:
        return self._current_scope.current_focus


# Globaler Focus Manager (Singleton)
_focus_manager: Optional["FocusManager"] = None


def get_focus_manager() -> FocusManager:
    global _focus_manager
    if _focus_manager is None:
        _focus_manager = FocusManager()
    return _focus_manager


# XAML Integration
FOCUS_MANAGEMENT_XAML = """
<!-- 
Focus Management XAML Integration
In App.xaml oder Page Resources:
-->

<ResourceDictionary
    xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">

    <!-- Focus Scope für Container -->
    <Style TargetType="Grid" x:Key="FocusScopeGridStyle">
        <Setter Property="IsTabStop" Value="True"/>
        <Setter Property="TabNavigation" Value="Cycle"/>
    </Style>

    <!-- Focus Trap für Dialogs -->
    <Style TargetType="ContentDialog" x:Key="FocusTrapDialogStyle">
        <Setter Property="IsTabStop" Value="True"/>
        <Setter Property="TabNavigation" Value="Cycle"/>
    </Style>

    <!-- Skip Link für Accessibility -->
    <Style TargetType="HyperlinkButton" x:Key="SkipLinkStyle">
        <Setter Property="Content" Value="Zum Hauptinhalt springen"/>
        <Setter Property="FontSize" Value="14"/>
        <Setter Property="Padding" Value="12"/>
        <Setter Property="Background" Value="{ThemeResource SystemControlBackgroundAccentBrush}"/>
        <Setter Property="Foreground" Value="{ThemeResource SystemControlForegroundOnAccentBrush}"/>
        <Setter Property="Visibility" Value="Collapsed"/>
        <Setter Property="Template">
            <Setter.Value>
                <ControlTemplate TargetType="HyperlinkButton">
                    <Border Background="{TemplateBinding Background}" 
                            Padding="{TemplateBinding Padding}"
                            Visibility="{TemplateBinding Visibility}">
                        <ContentPresenter Content="{TemplateBinding Content}"/>
                    </Border>
                </ControlTemplate>
            </Setter.Value>
        </Setter>
        </Style>
        <!-- Bei Fokus anzeigen -->
        <Style TargetType="HyperlinkButton" x:Key="SkipLinkVisibleStyle" BasedOn="{StaticResource SkipLinkStyle}">
            <Setter Property="Visibility" Value="Visible"/>
        </Style>
        </ResourceDictionary>
"""
