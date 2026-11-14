"""Additional Converters für Factory Studio Views."""

from __future__ import annotations

from communitytoolkit_mvvm import ObservableObject
from datetime import datetime


class GateTypeToIconConverter(ObservableObject):
    """Konvertiert Gate-Type in FontIcon Glyph."""
    
    _ICONS = {
        "register": "\uE710",       # Add
        "transition": "\uE70E",     # Sync/Arrow
        "build": "\uE76C",          # Hammer
        "benchmark": "\uE716",      # Chart
        "approve": "\uE73E",        # Checkmark
        "reject": "\uE711",         # X
    }
    
    def convert(self, value: str) -> str:
        if not value:
            return "\uE711"
        return self._ICONS.get(value.lower(), "\uE711")
    
    def convert_back(self, value: str) -> str:
        raise NotImplementedError("One-way converter")


class ActivityTypeToColorConverter(ObservableObject):
    """Konvertiert Activity-Type in Farbe."""
    
    _COLORS = {
        "build": "#0078D7",        # Blue
        "benchmark": "#8764B8",    # Purple
        "gate": "#FF8C00",         # Orange
        "project": "#107C10",      # Green
        "module": "#8764B8",       # Purple
        "error": "#D13438",        # Red
        "info": "#0078D7",         # Blue
    }
    
    def convert(self, value: str) -> str:
        if not value:
            return "#666666"
        return self._COLORS.get(value.lower(), "#666666")
    
    def convert_back(self, value: str) -> str:
        raise NotImplementedError("One-way converter")


class DateTimeToStringConverter(ObservableObject):
    """Konvertiert ISO8601 DateTime String in lesbares Format."""
    
    def convert(self, value: str, parameter: str = "") -> str:
        if not value:
            return ""
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parameter == "short":
                return dt.strftime("%d.%m.%Y %H:%M")
            elif parameter == "time":
                return dt.strftime("%H:%M:%S")
            return dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            return value
    
    def convert_back(self, value: str) -> str:
        raise NotImplementedError("One-way converter")


class DoubleToPercentConverter(ObservableObject):
    """Konvertiert Double (0-1) in Prozent-String."""
    
    def convert(self, value: float, parameter: str = "") -> str:
        if value is None:
            return "—"
        pct = value * 100
        if parameter and parameter.startswith("P"):
            try:
                precision = int(parameter[1:])
                return f"{pct:.{precision}f}%"
            except ValueError:
                return f"{pct:.1f}%"
        return f"{pct:.1f}%"
    
    def convert_back(self, value: str) -> float:
        raise NotImplementedError("One-way converter")


class ScoreToColorConverter(ObservableObject):
    """Konvertiert Score (0-1) in Farbe (Rot→Gelb→Grün)."""
    
    def convert(self, value: float) -> str:
        if value is None:
            return "#666666"
        if value >= 0.8:
            return "#107C10"  # Green
        elif value >= 0.5:
            return "#FF8C00"  # Orange
        return "#D13438"      # Red
    
    def convert_back(self, value: str) -> float:
        raise NotImplementedError("One-way converter")


class DurationConverter(ObservableObject):
    """Konvertiert Milliseconds in lesbare Dauer."""
    
    def convert(self, value: int) -> str:
        if value is None:
            return "—"
        if value < 1000:
            return f"{value} ms"
        elif value < 60000:
            return f"{value / 1000:.1f} s"
        else:
            minutes = value // 60000
            seconds = (value % 60000) / 1000
            return f"{minutes}m {seconds:.0f}s"
    
    def convert_back(self, value: str) -> int:
        raise NotImplementedError("One-way converter")


class DoubleToStringConverter(ObservableObject):
    """Konvertiert Double in formatierten String."""
    
    def convert(self, value: float, parameter: str = "") -> str:
        if value is None:
            return "—"
        if parameter and parameter.startswith("F"):
            try:
                precision = int(parameter[1:])
                return f"{value:.{precision}f}"
            except ValueError:
                return f"{value:.2f}"
        return f"{value:.2f}"
    
    def convert_back(self, value: str) -> float:
        raise NotImplementedError("One-way converter")