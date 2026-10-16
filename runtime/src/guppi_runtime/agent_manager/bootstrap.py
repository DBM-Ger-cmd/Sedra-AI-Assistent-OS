"""First setup of the agent manager data: export the DevVM role templates and import them (UNVERIFIED) into `<project>/runtime_data/agent_manager/registry.sqlite`.
Run it with `python -m guppi_runtime.agent_manager.bootstrap <project_dir>`; running it again changes nothing."""
import os
import sys

from .devvm_crews import export_devvm_crew
from .devvm_templates import export_role_templates
from .service import AgentManager


def bootstrap(project_dir):
    base = os.path.join(str(project_dir), "runtime_data", "agent_manager")
    folder = os.path.join(base, "templates")
    os.makedirs(folder, exist_ok=True)
    export_role_templates(folder)
    manager = AgentManager(os.path.join(base, "registry.sqlite"))
    try:
        results = manager.import_templates(folder)
        crews = os.path.join(base, "crews")
        os.makedirs(crews, exist_ok=True)
        export_devvm_crew(crews, manager.registry)
        return results + [{**row, "key": row["key"] or row["folder"]} for row in manager.import_crews(crews)]
    finally:
        manager.close()


if __name__ == "__main__":
    for row in bootstrap(sys.argv[1]):
        print(f"{row['status']:10s} {row['key']}  {row['problems']}")
