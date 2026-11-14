"""Main Entry Point — Factory Studio Desktop App Bootstrap."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from .di import ServiceContainer, get_container, close_container
from ..infrastructure.config import get_config


async def initialize_factory_studio(config: Any = None) -> ServiceContainer:
    """Initialisiert Factory Studio Module für One Sedra Integration.
    
    Wird von One Sedra Shell aufgerufen beim Laden des Factory Studio Tabs.
    """
    config = config or get_config()
    container = get_container(config)
    
    # Health-Check: externe Services erreichbar?
    if not config.mock_external_services:
        try:
            # Test-Verbindung zu Factory Registry
            types = await container.factory_registry.list_types()
            print(f"[Factory Studio] Connected to Factory Registry: {len(types)} types")
        except Exception as e:
            print(f"[Factory Studio] WARNING: Factory Registry not reachable: {e}")
    
    return container


async def shutdown_factory_studio():
    """Sauberes Herunterfahren beim Schließen des Tabs."""
    await close_container()
    print("[Factory Studio] Shutdown complete")


# Für direkte Ausführung (Testing)
async def main():
    """Standalone-Modus für Testing."""
    print("[Factory Studio] Starting standalone...")
    
    container = await initialize_factory_studio()
    
    # Demo: Projekt erstellen
    from ..application.use_cases.project_use_cases import CreateProjectRequest
    
    result = await container.create_project.execute(CreateProjectRequest(
        name="demo_project",
        display_name="Demo Project",
        description="Factory Studio Demo",
        factory_type_id="project_type",
    ))
    
    if result.success:
        print(f"Created project: {result.project.id}")
        
        # Module hinzufügen
        from ..application.use_cases.module_use_cases import AddModuleRequest
        
        module_result = await container.add_module.execute(AddModuleRequest(
            project_id=result.project.id,
            name="demo_module",
            display_name="Demo Module",
            module_type_id="module_type",
            layer="domain",
        ))
        if module_result.success:
            print(f"Added module: {module_result.module.id}")
    
    await shutdown_factory_studio()


if __name__ == "__main__":
    asyncio.run(main())