"""python -m guppi_runtime.skill_library build [NAME|all]   |   list"""
import sys

from . import SkillLibrary
from .config import build_configured, library_path, load


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    libraries = load()
    if args[:1] == ["list"]:
        for name, entry in libraries.items():
            try:
                count = len(SkillLibrary(library_path(name, libraries)))
                state = f"{count} skills"
            except (KeyError, OSError, ValueError):
                state = "not built"
            print(f"{name:<8} {state:<14} {entry['output']}  {entry.get('note', '')}")
        return 0
    if args[:1] == ["build"] and len(args) == 2:
        names = list(libraries) if args[1] == "all" else [args[1]]
        for name in names:
            try:
                print(name, build_configured(name, libraries))
            except (KeyError, ValueError) as exc:
                print(f"{name}: {exc}", file=sys.stderr)
                return 2
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
