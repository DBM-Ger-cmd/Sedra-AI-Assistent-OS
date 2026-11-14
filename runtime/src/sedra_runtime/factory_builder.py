"""F2-02: Factory Builder Core.

Baut Artefakte (Projekte, Module, Services) aus registrierten Factory-Typen.
Der Control Core (FactoryRegistry) bleibt Gate: jede Operation prüft gate_freigabe.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sedra_runtime.factory_registry import FactoryRegistry, FactoryRegistryError, FactoryType, REGISTERED, READY, ACTIVE, RETIRED, VALID_TRANSITIONS


@dataclass
class BuildResult:
    """Ergebnis eines Build-Vorgangs."""
    success: bool
    path: Path | None = None
    message: str = ""
    artifacts: list[Path] = None

    def __post_init__(self):
        if self.artifacts is None:
            self.artifacts = []


class FactoryBuilder:
    """Baut Software-Artefakte aus Factory-Typen.

    Jede Build-Operation erfordert Gate-Freigabe (Control Core).
    Templates liegen unter src/sedra_runtime/factory_templates/.
    """

    def __init__(self, registry: FactoryRegistry, project_root: Path) -> None:
        self.registry = registry
        self.project_root = Path(project_root).resolve()
        self.template_root = Path(__file__).parent / "factory_templates"

    def _require_gate(self, typ_id: str, gate_freigabe: bool) -> BuildResult | None:
        """Prüft Gate-Freigabe für den Factory-Typ. Gibt BuildResult bei Fehler, None bei Erfolg."""
        if not gate_freigabe:
            return BuildResult(False, message=f"gate_required:{typ_id}")
        if typ_id not in self.registry._gate_erlaubt:
            return BuildResult(False, message=f"gate_not_granted:{typ_id}")
        return None

    def _get_type(self, typ_id: str) -> FactoryType:
        """Holt Factory-Typ aus Registry, wirft bei Fehlen."""
        ft = self.registry._typen.get(typ_id)
        if ft is None:
            raise FactoryRegistryError(f"typ_unbekannt:{typ_id}")
        return ft

    def _validate_name(self, name: str) -> BuildResult | None:
        """Validiert Namen gegen Path Traversal und ungültige Zeichen.
        Gibt BuildResult bei Fehler, None bei Erfolg."""
        if not name or not name.strip():
            return BuildResult(False, message="name_leer")
        # Path Traversal Schutz
        if ".." in name or "/" in name or "\\" in name:
            return BuildResult(False, message=f"path_traversal:{name}")
        # Optional: Nur alphanumerisch, -, _ erlauben
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            return BuildResult(False, message=f"ungueltiger_name:{name}")
        return None

    def _render_template(self, template_dir: Path, target_dir: Path, context: dict[str, Any]) -> list[Path]:
        """Rendert Template-Verzeichnis nach Ziel mit Context-Ersetzung (auch Dateinamen)."""
        created = []
        if not template_dir.exists():
            return created

        for src in template_dir.rglob("*"):
            if src.is_file():
                rel = src.relative_to(template_dir)
                # Auch Pfad/Dateiname templaten
                rel_str = str(rel)
                for key, value in context.items():
                    rel_str = rel_str.replace(f"{{{{{key}}}}}", str(value))
                dst = target_dir / rel_str
                dst.parent.mkdir(parents=True, exist_ok=True)

                content = src.read_text(encoding="utf-8")
                for key, value in context.items():
                    content = content.replace(f"{{{{{key}}}}}", str(value))

                dst.write_text(content, encoding="utf-8")
                created.append(dst)

        return created

    def build_project(self, typ_id: str, name: str, *, gate_freigabe: bool = False) -> BuildResult:
        """Erzeugt ein neues Projekt aus Template.

        Args:
            typ_id: Factory-Typ ID (muss in Registry registriert sein)
            name: Projektname (wird als Ordnername verwendet)
            gate_freigabe: Muss True sein (Control Core Autorisierung)

        Returns:
            BuildResult mit Pfad zum erzeugten Projekt
        """
        # 1. Typ validieren (existiert er?)
        try:
            ft = self._get_type(typ_id)
        except FactoryRegistryError as exc:
            return BuildResult(False, message=str(exc))

        # 2. Name validieren (Path Traversal Schutz)
        name_result = self._validate_name(name)
        if name_result is not None:
            return name_result

        # 3. Gate prüfen
        gate_result = self._require_gate(typ_id, gate_freigabe)
        if gate_result is not None:
            return gate_result

        if ft.zustand not in (REGISTERED, READY):
            return BuildResult(False, message=f"typ_zustand_ungueltig:{ft.zustand}")

        # 4. Zielpfad prüfen
        target = self.project_root / name
        if target.exists():
            return BuildResult(False, message=f"projekt_existiert:{target}")

        # 4. Template rendern
        context = {
            "project_name": name,
            "factory_type": typ_id,
            "factory_name": ft.name,
        }

        try:
            artifacts = self._render_template(self.template_root / "project", target, context)
        except Exception as exc:
            return BuildResult(False, message=f"template_fehler:{exc}")

        # 5. Grundvalidierung: pyproject.toml oder setup.py vorhanden?
        if not (target / "pyproject.toml").exists() and not (target / "setup.py").exists():
            # Fallback: minimales pyproject.toml erzeugen
            (target / "pyproject.toml").write_text(
                f"[project]\nname = \"{name}\"\nversion = \"0.1.0\"\nrequires-python = \">=3.11\"\n",
                encoding="utf-8"
            )
            artifacts.append(target / "pyproject.toml")

        # 6. Typ in READY versetzen (Gate-geschützt)
        try:
            self.registry.wechsel_zustand(typ_id, READY, gate_freigabe=True)
        except FactoryRegistryError:
            pass  # Zustandsänderung optional für MVP

        return BuildResult(True, path=target, message="projekt_erzeugt", artifacts=artifacts)

    def build_module(self, typ_id: str, name: str, project: Path, *, gate_freigabe: bool = False) -> BuildResult:
        """Fügt ein Modul zu einem bestehenden Projekt hinzu.

        Args:
            typ_id: Factory-Typ ID für Modul-Typ
            name: Modulname
            project: Pfad zum Projekt-Root
            gate_freigabe: Muss True sein

        Returns:
            BuildResult mit Pfad zum Modul
        """
        # 1. Typ validieren
        try:
            ft = self._get_type(typ_id)
        except FactoryRegistryError as exc:
            return BuildResult(False, message=str(exc))

        # 2. Name validieren (Path Traversal Schutz)
        name_result = self._validate_name(name)
        if name_result is not None:
            return name_result

        # 3. Gate prüfen
        gate_result = self._require_gate(typ_id, gate_freigabe)
        if gate_result is not None:
            return gate_result

        project = Path(project).resolve()

        if not project.exists():
            return BuildResult(False, message=f"projekt_nicht_gefunden:{project}")

        # Modul-Zielpfad: project/src/<name>
        target = project / "src" / name
        if target.exists():
            return BuildResult(False, message=f"modul_existiert:{target}")

        context = {
            "module_name": name,
            "MODULE_NAME": name.replace("-", "_").replace(" ", "_"),
            "factory_type": typ_id,
            "factory_name": ft.name,
            "project_name": project.name,
        }

        try:
            artifacts = self._render_template(self.template_root / "module", target, context)
        except Exception as exc:
            return BuildResult(False, message=f"template_fehler:{exc}")

        # __init__.py sicherstellen
        init_file = target / "__init__.py"
        if not init_file.exists():
            init_file.write_text(f"# {name} module\n", encoding="utf-8")
            artifacts.append(init_file)

        return BuildResult(True, path=target, message="modul_erzeugt", artifacts=artifacts)

    def build_service(self, typ_id: str, name: str, project: Path, *, gate_freigabe: bool = False) -> BuildResult:
        """Erzeugt Service-Definition (systemd, docker-compose, n8n).

        Args:
            typ_id: Factory-Typ ID für Service-Typ
            name: Servicename
            project: Pfad zum Projekt-Root
            gate_freigabe: Muss True sein

        Returns:
            BuildResult mit Pfad zur Service-Definition
        """
        # 1. Typ validieren
        try:
            ft = self._get_type(typ_id)
        except FactoryRegistryError as exc:
            return BuildResult(False, message=str(exc))

        # 2. Name validieren (Path Traversal Schutz)
        name_result = self._validate_name(name)
        if name_result is not None:
            return name_result

        # 3. Gate prüfen
        gate_result = self._require_gate(typ_id, gate_freigabe)
        if gate_result is not None:
            return gate_result

        project = Path(project).resolve()

        if not project.exists():
            return BuildResult(False, message=f"projekt_nicht_gefunden:{project}")

        # Service-Zielpfad: project/services/<name>
        target = project / "services" / name
        if target.exists():
            return BuildResult(False, message=f"service_existiert:{target}")

        context = {
            "service_name": name,
            "factory_type": typ_id,
            "factory_name": ft.name,
            "project_name": project.name,
        }

        try:
            artifacts = self._render_template(self.template_root / "service", target, context)
        except Exception as exc:
            return BuildResult(False, message=f"template_fehler:{exc}")

        return BuildResult(True, path=target, message="service_erzeugt", artifacts=artifacts)

    def build_adapter_project(self, typ_id: str, name: str, *, gate_freigabe: bool = False) -> BuildResult:
        """Erzeugt ein Adapter-Projekt mit Native, n8n und Hybrid Workflows.

        Args:
            typ_id: Factory-Typ ID (muss 'adapter-project' oder ähnlich sein)
            name: Projektname
            gate_freigabe: Muss True sein (Control Core Autorisierung)

        Returns:
            BuildResult mit Pfad zum erzeugten Adapter-Projekt
        """
        # 1. Typ validieren
        try:
            ft = self._get_type(typ_id)
        except FactoryRegistryError as exc:
            return BuildResult(False, message=str(exc))

        # 2. Name validieren (Path Traversal Schutz)
        name_result = self._validate_name(name)
        if name_result is not None:
            return name_result

        # 3. Gate prüfen
        gate_result = self._require_gate(typ_id, gate_freigabe)
        if gate_result is not None:
            return gate_result

        if ft.zustand not in (REGISTERED, READY):
            return BuildResult(False, message=f"typ_zustand_ungueltig:{ft.zustand}")

        # 4. Zielpfad prüfen
        target = self.project_root / name
        if target.exists():
            return BuildResult(False, message=f"projekt_existiert:{target}")

        # 5. Adapter-Templates erstellen
        try:
            from .factory_adapter_templates import create_adapter_templates
            create_adapter_templates(self, target, name)
        except Exception as exc:
            return BuildResult(False, message=f"adapter_template_fehler:{exc}")

        # 6. Grundvalidierung
        if not (target / "pyproject.toml").exists():
            # pyproject.toml aus Template rendern falls vorhanden
            context = {
                "project_name": name,
                "factory_type": typ_id,
                "factory_name": ft.name,
                "PROJECT_NAME_SANITIZED": name.replace("-", "_").replace(" ", "_"),
            }
            artifacts = self._render_template(self.template_root / "adapter_project", target, context)
            if not (target / "pyproject.toml").exists():
                (target / "pyproject.toml").write_text(
                    f"[project]\nname = \"{name}\"\nversion = \"0.1.0\"\nrequires-python = \">=3.11\"\n",
                    encoding="utf-8"
                )

        # 7. Typ in READY versetzen (Gate-geschützt)
        try:
            self.registry.wechsel_zustand(typ_id, READY, gate_freigabe=True)
        except FactoryRegistryError:
            pass

        return BuildResult(True, path=target, message="adapter_projekt_erzeugt", artifacts=list(target.rglob("*")))


# Convenience-Funktion für CLI
def create_builder(registry: FactoryRegistry, project_root: Path) -> FactoryBuilder:
    """Factory-Funktion für CLI-Integration."""
    return FactoryBuilder(registry, project_root)