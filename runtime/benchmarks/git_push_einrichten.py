"""Richtet im Git-Repo den festen Push-Ablauf ein: `git push` schiebt main nach origin/main UND nach
origin/spec/agenten-orchestrierung (nur Vorspulen, nie Force); `git nachziehen` pusht, setzt den lokalen
spec-Branch auf main und zeigt die vier Staende. Die Einstellung steht in .git/config und ist nicht versioniert,
darum gehoert dieses Skript ins Repo: auf einem neuen Klon einmal ausfuehren.

Aufruf (im Repo, beliebiges Unterverzeichnis):  python runtime/benchmarks/git_push_einrichten.py [--pruefen]
Nur Standardbibliothek. Wiederholtes Ausfuehren aendert nichts (idempotent). --pruefen schreibt nichts."""
import subprocess
import sys

REMOTE = "origin"
SPEC = "spec/agenten-orchestrierung"
PUSH_REFS = ["refs/heads/main:refs/heads/main", f"refs/heads/main:refs/heads/{SPEC}"]
ALIAS_NAME = "nachziehen"
ALIAS = ("!git push && git branch -f " + SPEC + " main && git fetch -q " + REMOTE +
         " && for r in main " + REMOTE + "/main " + SPEC + " " + REMOTE + "/" + SPEC +
         '; do echo "$r $(git rev-parse --short $r)"; done')


def git(*args, check=True):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit("git " + " ".join(args) + " fehlgeschlagen: " + r.stderr.strip())
    return r.stdout.strip()


def main():
    nur_pruefen = "--pruefen" in sys.argv[1:]
    git("rev-parse", "--git-dir")                                     # bricht ausserhalb eines Repos ab
    if not git("remote", "get-url", REMOTE, check=False):
        raise SystemExit(f"Kein Remote '{REMOTE}' vorhanden.")
    vorhanden = git("config", "--get-all", f"remote.{REMOTE}.push", check=False).splitlines()
    fehlt = [r for r in PUSH_REFS if r not in vorhanden]
    fremd = [r for r in vorhanden if r not in PUSH_REFS]
    alias_ist = git("config", "--get", f"alias.{ALIAS_NAME}", check=False)
    print("Push-Regeln:", "ok" if not fehlt else "fehlen: " + ", ".join(fehlt))
    if fremd:
        print("Hinweis: weitere Push-Regeln bleiben unveraendert:", ", ".join(fremd))
    print(f"Alias git {ALIAS_NAME}:", "ok" if alias_ist == ALIAS else "fehlt oder abweichend")
    if nur_pruefen:
        raise SystemExit(0 if not fehlt and alias_ist == ALIAS else 1)
    for ref in fehlt:
        git("config", "--add", f"remote.{REMOTE}.push", ref)
    if alias_ist != ALIAS:
        git("config", f"alias.{ALIAS_NAME}", ALIAS)
    print("Eingerichtet. `git push` zieht spec mit; `git nachziehen` zeigt zusaetzlich die Staende.")


if __name__ == "__main__":
    main()
