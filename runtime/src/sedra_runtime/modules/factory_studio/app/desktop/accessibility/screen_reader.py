"""Screen Reader Helper — Factory Studio Screen Reader Support (Live Regions, Announcements)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional
from communitytoolkit_mvvm import ObservableObject, RelayCommand


class LiveRegionPoliteness(Enum):
    """Live Region Höflichkeit (wie dringend soll angesagt werden)."""
    OFF = "off"           # Nicht ansagen
    POLITE = "polite"     # Wenn Nutzer pausiert
    ASSERTIVE = "assertive"  # Sofort unterbrechen


class AnnouncementPriority(Enum):
    """Priorität für Ansagen."""
    LOW = "low"           # Info, kann warten
    NORMAL = "normal"     # Standard
    HIGH = "high"         # Wichtig (Errors, Warnings)
    CRITICAL = "critical" # Kritisch (System-down, Data-loss)


@dataclass
class Announcement:
    """Eine Ansage für Screen Reader."""
    message: str
    priority: AnnouncementPriority = AnnouncementPriority.NORMAL
    politeness: LiveRegionPoliteness = LiveRegionPoliteness.POLITE
    category: str = "info"  # info, warning, error, success, progress


class LiveRegion(ObservableObject):
    """Live Region für Screen Reader Ansagen (ARIA Live Region Pattern)."""
    
    def __init__(self, politeness: LiveRegionPoliteness = LiveRegionPoliteness.POLITE):
        self._politeness = politeness
        self._current_message: str = ""
        self._message_history: list[str] = []
        self._max_history = 50
    
    @property
    def politeness(self) -> LiveRegionPoliteness:
        return self._politeness
    
    @politeness.setter
    def politeness(self, value: LiveRegionPoliteness):
        self._politeness = value
        self.notify_property_changed("politeness")
    
    @property
    def current_message(self) -> str:
        return self._current_message
    
    def announce(self, message: str, politeness: LiveRegionPoliteness | None = None):
        """Sendet Nachricht an Live Region (wird von Screen Reader vorgelesen)."""
        if politeness:
            self._politeness = politeness
        
        self._current_message = message
        self._message_history.append(message)
        if len(self._message_history) > self._max_history:
            self._message_history.pop(0)
        
        self.notify_property_changed("current_message")
        self.notify_property_changed("politeness")
        
        # In echt: Live Region im DOM aktualisieren
        # <div aria-live="polite" aria-atomic="true">{message}</div>
    
    def clear(self):
        """Leert Live Region."""
        self._current_message = ""
        self.notify_property_changed("current_message")


class Announcer(ObservableObject):
    """Zentrale Ansage-Instanz für Factory Studio."""
    
    def __init__(self):
        self._live_regions: dict[str, LiveRegion] = {
            "default": LiveRegion(LiveRegionPoliteness.POLITE),
            "alerts": LiveRegion(LiveRegionPoliteness.ASSERTIVE),
            "status": LiveRegion(LiveRegionPoliteness.POLITE),
            "progress": LiveRegion(LiveRegionPoliteness.POLITE),
        }
        self._announcement_queue: list[tuple[str, Announcement]] = []
        self._is_processing = False
    
    def get_region(self, name: str = "default") -> LiveRegion:
        """Holt oder erstellt Live Region."""
        if name not in self._live_regions:
            self._live_regions[name] = LiveRegion(LiveRegionPoliteness.POLITE)
        return self._live_regions[name]
    
    def announce(self, message: str, region: str = "default", 
                 priority: str = "normal", politeness: str = "polite"):
        """Sendet Ansage an Region."""
        live_region = self.get_region(region)
        
        # Politeness aus String
        polite_map = {
            "off": LiveRegionPoliteness.OFF,
            "polite": LiveRegionPoliteness.POLITE,
            "assertive": LiveRegionPoliteness.ASSERTIVE,
        }
        live_region.announce(message, polite_map.get(politeness, LiveRegionPoliteness.POLITE))
    
    # Convenience Methods
    def info(self, message: str, region: str = "default"):
        self.announce(message, region, "normal", "polite")
    
    def warning(self, message: str, region: str = "alerts"):
        self.announce(message, region, "high", "assertive")
    
    def error(self, message: str, region: str = "alerts"):
        self.announce(message, region, "high", "assertive")
    
    def success(self, message: str, region: str = "status"):
        self.announce(message, region, "normal", "polite")
    
    def progress(self, message: str, region: str = "progress"):
        self.announce(message, region, "normal", "polite")
    
    # Factory Studio spezifische Ansagen
    def project_created(self, project_name: str):
        self.success(f"Projekt \'{project_name}\' erstellt")
    
    def project_deleted(self, project_name: str):
        self.info(f"Projekt \'{project_name}\' gelöscht")
    
    def module_added(self, module_name: str, project_name: str):
        self.info(f"Modul \'{module_name}\' zu Projekt \'{project_name}\' hinzugefügt")
    
    def build_started(self, project_name: str):
        self.progress(f"Build gestartet für \'{project_name}\'")
    
    def build_completed(self, project_name: str, success: bool):
        if success:
            self.success(f"Build für \'{project_name}\' erfolgreich abgeschlossen")
        else:
            self.error(f"Build für \'{project_name}\' fehlgeschlagen")
    
    def benchmark_completed(self, factory_type: str, score: float):
        self.info(f"Benchmark für \'{factory_type}\' abgeschlossen. Score: {score:.2f}")
    
    def gate_pending(self, gate_type: str, target: str):
        self.warning(f"Neues Gate: {gate_type} für {target} wartet auf Entscheidung")
    
    def gate_decided(self, gate_type: str, target: str, decision: str):
        if decision == "approved":
            self.success(f"Gate {gate_type} für {target} genehmigt")
        else:
            self.error(f"Gate {gate_type} für {target} abgelehnt")
    
    def benchmark_completed(self, factory_type: str, score: float):
        self.info(f"Benchmark für \'{factory_type}\' abgeschlossen. Score: {score:.2f}")


# Singleton für App-weiten Zugriff
_announcer: Announcer | None = None


def get_announcer() -> Announcer:
    """Liefert globale Announcer-Instanz."""
    global _announcer
    if _announcer is None:
        _announcer = Announcer()
    return _announcer


def announce(message: str, region: str = "default", priority: str = "normal", politeness: str = "polite"):
    """Kurzform für globale Ansage."""
    get_announcer().announce(message, region, priority, politeness)


# XAML Integration für Live Regions
LIVE_REGION_XAML = """
<!-- 
Live Regions für XAML
In MainWindow/Page Resources einbinden:
-->

<ResourceDictionary
    xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">

    <!-- Live Region Container (unsichtbar, aber Screen Reader lesen vor) -->
    <Style TargetType="TextBlock" x:Key="LiveRegionTextBlockStyle">
        <Setter Property="Visibility" Value="Collapsed"/>
        <Setter Property="AutomationProperties.LiveSetting" Value="Polite"/>
        <Setter Property="AutomationProperties.Atomic" Value="True"/>
    </Style>

    <!-- Assertive Live Region für Alerts -->
    <Style TargetType="TextBlock" x:Key="AssertiveLiveRegionStyle">
        <Setter Property="Visibility" Value="Collapsed"/>
        <Setter Property="AutomationProperties.LiveSetting" Value="Assertive"/>
        <Setter Property="AutomationProperties.Atomic" Value="True"/>
    </Style>

    <!-- Off Live Region (nicht ansagen) -->
    <Style TargetType="TextBlock" x:Key="OffLiveRegionStyle">
        <Setter Property="Visibility" Value="Collapsed"/>
        <Setter Property="AutomationProperties.LiveSetting" Value="Off"/>
    </Style>

    <!-- Live Region Container in Page/Window -->
    <!-- 
    <Grid>
        <!-- Hauptinhalt -->
        <ContentControl Content="{Binding CurrentView}"/>
        
        <!-- Live Regions am Ende (für Screen Reader) -->
        <TextBlock x:Name="LiveRegionDefault" Style="{StaticResource LiveRegionTextBlockStyle}" 
                   Text="{Binding Announcer.DefaultRegion.CurrentMessage, Mode=OneWay}"/>
        <TextBlock x:Name="LiveRegionAlerts" Style="{StaticResource AssertiveLiveRegionStyle}" 
                   Text="{Binding Announcer.AlertsRegion.CurrentMessage, Mode=OneWay}"/>
        <TextBlock x:Name="LiveRegionStatus" Style="{StaticResource LiveRegionTextBlockStyle}" 
                   Text="{Binding Announcer.StatusRegion.CurrentMessage, Mode=OneWay}"/>
        <TextBlock x:Name="LiveRegionProgress" Style="{StaticResource LiveRegionTextBlockStyle}" 
                   Text="{Binding Announcer.ProgressRegion.CurrentMessage, Mode=OneWay}"/>
    </Grid>
    -->
</ResourceDictionary>
"""


# Factory Studio Announcer Integration
def create_factory_studio_announcer() -> Announcer:
    """Erstellt vorkonfigurierten Announcer für Factory Studio."""
    announcer = Announcer()
    return announcer
