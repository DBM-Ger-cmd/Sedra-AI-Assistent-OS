"""Status to Color Converter — Projekt/Modul/Build Status Farben."""

from __future__ import annotations

from sedra_runtime.modules.factory_studio._mvvm import ObservableObject


class StatusToColorConverter(ObservableObject):
    """Konvertiert Status-String in Farbe."""
    
    _COLORS = {
        # Project Status
        "created": "#0078D7",       # Blue
        "building": "#FF8C00",      # Orange
        "ready": "#107C10",         # Green
        "archived": "#666666",      # Gray
        "failed": "#D13438",        # Red
        
        # Module Status
        "planned": "#0078D7",
        "generating": "#FF8C00",
        "generated": "#107C10",
        "built": "#107C10",
        
        # Build Status
        "pending": "#666666",
        "running": "#0078D7",
        "success": "#107C10",
        "failed": "#D13438",
        "cancelled": "#666666",
        
        # Gate Status
        "approved": "#107C10",
        "rejected": "#D13438",
    }
    
    def convert(self, value: str) -> str:
        if not value:
            return "#666666"
        return self._COLORS.get(value.lower(), "#666666")
    
    def convert_back(self, value: str) -> str:
        raise NotImplementedError("One-way converter")


class BoolToVisibilityConverter(ObservableObject):
    """Konvertiert Boolean in Visibility."""
    
    def convert(self, value: bool, parameter: str = "") -> str:
        if parameter == "inverted":
            return "Collapsed" if value else "Visible"
        return "Visible" if value else "Collapsed"
    
    def convert_back(self, value: str) -> bool:
        return value == "Visible"


class StringToVisibilityConverter(ObservableObject):
    """Konvertiert String (leer/nicht leer) in Visibility."""
    
    def convert(self, value: str, parameter: str = "") -> str:
        if parameter == "inverted":
            return "Collapsed" if value and value.strip() else "Visible"
        return "Visible" if value and value.strip() else "Collapsed"
    
    def convert_back(self, value: str) -> str:
        return value


class IntToStringConverter(ObservableObject):
    """Konvertiert Int zu String mit Format."""
    
    def convert(self, value: int, parameter: str = "") -> str:
        if not parameter:
            return str(value)
        # Parameter: "Prefix {0} Suffix"
        if "{0}" in parameter:
            return parameter.replace("{0}", str(value))
        return f"{parameter}{value}"
    
    def convert_back(self, value: str) -> int:
        try:
            return int(value)
        except ValueError:
            return 0


class BuildStatusToGlyphConverter(ObservableObject):
    """Konvertiert Build-Status in FontIcon Glyph."""
    
    _GLYPHS = {
        "pending": "\uE70E",      # Clock
        "running": "\uE76C",      # Spinner/Play
        "success": "\uE73E",      # Checkmark
        "failed": "\uE711",       # X/Cancel
        "cancelled": "\uE711",    # X
    }
    
    def convert(self, value: str) -> str:
        if not value:
            return "\uE70E"
        return self._GLYPHS.get(value.lower(), "\uE70E")
    
    def convert_back(self, value: str) -> str:
        raise NotImplementedError("One-way converter")


class BuildStatusToColorConverter(ObservableObject):
    """Konvertiert Build-Status in Farbe für Glyph."""
    
    _COLORS = {
        "pending": "#666666",
        "running": "#0078D7",
        "success": "#107C10",
        "failed": "#D13438",
        "cancelled": "#666666",
    }
    
    def convert(self, value: str) -> str:
        if not value:
            return "#666666"
        return self._COLORS.get(value.lower(), "#666666")
    
    def convert_back(self, value: str) -> str:
        raise NotImplementedError("One-way converter")


class NodeTypeToColorConverter(ObservableObject):
    """Konvertiert Node-Type in Farbe für Graph-Knoten."""
    
    _COLORS = {
        "project": "#0078D7",    # Blue
        "module": "#107C10",     # Green
        "service": "#FF8C00",    # Orange
        "build": "#8764B8",      # Purple
    }
    
    def convert(self, value: str) -> str:
        if not value:
            return "#666666"
        return self._COLORS.get(value.lower(), "#666666")
    
    def convert_back(self, value: str) -> str:
        raise NotImplementedError("One-way converter")


class NodeTypeToIconConverter(ObservableObject):
    """Konvertiert Node-Type in FontIcon Glyph."""
    
    _ICONS = {
        "project": "\uE70D",      # Folder
        "module": "\uE95D",       # Cube
        "service": "\uE70E",      # Globe
        "build": "\uE76C",        # Hammer
    }
    
    def convert(self, value: str) -> str:
        if not value:
            return "\uE711"
        return self._ICONS.get(value.lower(), "\uE711")
    
    def convert_back(self, value: str) -> str:
        raise NotImplementedError("One-way converter")