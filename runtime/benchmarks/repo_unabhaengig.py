r"""A1 bekommt ein eigenes Git-Repository (Umzug nach A1, U2-13): heute ist A1 ein verknüpfter Worktree des Hub-Repos (die Datei `.git` zeigt in den Hub-Ordner). Danach liegt das Repository in A1
selbst, und der Hub-Ordner wird nicht mehr gebraucht.

    python benchmarks/repo_unabhaengig.py                         Trockenlauf: prüft und zeigt, was geschähe, ändert nichts
    python benchmarks/repo_unabhaengig.py --go                    umbauen (Captain-Gate)
    python benchmarks/repo_unabhaengig.py --rollback              die alte `.git`-Datei wiederherstellen (sie liegt als `.git\hub-link` im neuen Repository)
    optionen: --repo <A1-Ordner>  --bundle <Datei>  (Vorgabe: Archiv\Entwickler_Archiv\A1_alle_refs_<datum>.bundle)

Ablauf von --go (jeder Schritt vor dem Umbenennen ändert A1 nicht):
  1. Prüfungen: `.git` ist eine Datei (verknüpfter Worktree), `git status` sauber, kein Python/llama-Prozess aus dem Ordner, ein überprüftes Bundle aller Refs existiert (sonst wird es angelegt).
  2. Neues Repository als `.git.neu` (bare) im Ordner anlegen und ALLE Refs aus dem gemeinsamen Git-Verzeichnis des Hubs holen (Branches, Tags, Remote-Branches, Stash), dazu die Konfiguration
     des Hubs übernehmen (remote.*, branch.*, core.*, user.*, Zeilenende-Einstellungen), keine Worktree-Verwaltungsdaten.
  3. Umbenennen: `.git` (Datei) wird gelesen und weggelegt, `.git.neu` -> `.git`, die alte Datei liegt danach als `.git\hub-link` im neuen Repository (nicht im Arbeitsordner: Git zählte sie sonst als unversioniert); `core.bare` false; HEAD auf den bisherigen Branch; Index aus HEAD neu aufbauen (`git reset`, Dateien bleiben unberührt).
  4. Prüfung: gleicher HEAD, `git status` sauber, dieselben Branches und Tags mit denselben Commits, `git fsck --connectivity-only`, `git worktree list` zeigt nur A1. Bei einem Fehler wird zurückgestellt.
Der Hub-Ordner wird nicht angefasst und nicht gelöscht; das ist der Schritt des Captains, nachdem `--go` gemeldet hat, dass alles stimmt."""
from __future__ import annotations

import argparse
import datetime
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO = r"E:\Sedra Umgebung\A1 Sedra Main Branch Entwicklungs umgebung"
DEFAULT_BUNDLE_DIR = r"E:\Sedra Umgebung\Archiv\Entwickler_Archiv"
KEEP_CONFIG = ("remote.", "branch.", "core.", "user.", "i18n.", "pull.", "fetch.", "push.", "init.", "gc.", "advice.")
SKIP_CONFIG = ("core.bare", "core.worktree", "core.repositoryformatversion", "core.filemode", "core.symlinks", "core.ignorecase", "core.logallrefupdates")


def git(repo, *args, check=True, git_dir=None):
    cmd = ["git"]
    if git_dir:
        cmd += ["--git-dir", str(git_dir)]
    elif repo is not None:
        cmd += ["-C", str(repo)]
    done = subprocess.run(cmd + list(args), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {(done.stderr or done.stdout).strip()[:300]}")
    return done.stdout.strip()


def refs(repo=None, git_dir=None):
    out = git(repo, "for-each-ref", "--format=%(refname) %(objectname)", git_dir=git_dir)
    return dict(line.split(" ", 1) for line in out.splitlines() if line.strip() and not line.startswith("refs/worktree"))


def common_dir(repo):
    p = Path(git(repo, "rev-parse", "--git-common-dir"))
    return p if p.is_absolute() else (Path(repo) / p).resolve()


def processes_in(repo):
    if os.name != "nt":
        return 0
    cmd = (f"@(Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like '*{Path(repo).name}*' -and $_.Name -match 'python|llama' }}).Count")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True).stdout.strip()
    return int(out) if out.isdigit() else 0


def preconditions(repo):
    problems = []
    dotgit = Path(repo) / ".git"
    if not dotgit.exists():
        problems.append("kein .git")
    elif dotgit.is_dir():
        problems.append(".git ist schon ein Ordner: A1 hat bereits ein eigenes Repository")
    if (Path(repo) / ".git.neu").exists() or (Path(repo) / ".git.alt").exists():
        problems.append(".git.neu oder .git.alt liegt schon im Ordner (frühere Umbauversuche aufräumen)")
    if not problems:
        status = git(repo, "status", "--short")
        if status:
            problems.append(f"git status nicht sauber ({len(status.splitlines())} Einträge)")
    n = processes_in(repo)
    if n:
        problems.append(f"{n} Python/llama-Prozess(e) aus dem Ordner laufen")
    return problems


def make_bundle(repo, bundle):
    bundle = Path(bundle)
    bundle.parent.mkdir(parents=True, exist_ok=True)
    if not bundle.exists():
        git(repo, "bundle", "create", str(bundle), "--all")
    git(repo, "bundle", "verify", str(bundle))
    return bundle


def convert(repo, say=print):
    repo = Path(repo)
    hub = common_dir(repo)
    head_branch = git(repo, "symbolic-ref", "-q", "--short", "HEAD", check=False)
    head_commit = git(repo, "rev-parse", "HEAD")
    before = refs(git_dir=hub)
    say(f"Hub-Repository: {hub} ({len(before)} Refs); A1 steht auf {head_branch or 'losem HEAD'} {head_commit[:9]}")
    neu = repo / ".git.neu"
    git(None, "init", "--bare", "-q", str(neu))
    for line in git(None, "config", "--file", str(hub / "config"), "--list", check=False).splitlines():
        key, _, value = line.partition("=")
        if key.startswith(KEEP_CONFIG) and key not in SKIP_CONFIG:
            git(None, "config", "--add", key, value, git_dir=neu)
    # alle Refs aus dem gemeinsamen Verzeichnis holen (ohne Worktree-eigene Refs)
    git(None, "fetch", "-q", "--no-tags", str(hub), "+refs/heads/*:refs/heads/*", "+refs/remotes/*:refs/remotes/*", "+refs/tags/*:refs/tags/*", git_dir=neu)
    if (hub / "refs" / "stash").exists() or "refs/stash" in before:
        git(None, "fetch", "-q", "--no-tags", str(hub), "+refs/stash:refs/stash", git_dir=neu, check=False)
    # Umbenennen
    old_link = (repo / ".git").read_bytes()
    os.replace(repo / ".git", repo / ".git.alt")
    os.replace(neu, repo / ".git")
    (repo / ".git" / "hub-link").write_bytes(old_link)
    os.remove(repo / ".git.alt")
    try:
        git(repo, "config", "core.bare", "false")
        git(repo, "config", "core.logallrefupdates", "true")
        if head_branch:
            git(repo, "symbolic-ref", "HEAD", f"refs/heads/{head_branch}")
        else:
            git(repo, "update-ref", "--no-deref", "HEAD", head_commit)
        git(repo, "reset", "-q")                       # Index aus HEAD; Dateien bleiben unberührt
        problems = verify(repo, before, head_commit)
    except Exception as exc:
        problems = [f"Umbau fehlgeschlagen: {exc}"]
    if problems:
        rollback(repo, say)
        raise RuntimeError("Prüfung fehlgeschlagen, zurückgestellt: " + "; ".join(problems[:5]))
    return {"refs": len(before), "head": head_commit, "hub": str(hub)}


def verify(repo, before, head_commit):
    problems = []
    if git(repo, "rev-parse", "HEAD") != head_commit:
        problems.append("HEAD weicht ab")
    status = git(repo, "status", "--short")
    if status:
        problems.append(f"git status nicht sauber ({len(status.splitlines())} Einträge)")
    after = refs(repo)
    for name, sha in before.items():
        if name.startswith("refs/remotes/") and name.endswith("/HEAD"):
            continue
        if after.get(name) != sha:
            problems.append(f"Ref {name} fehlt oder weicht ab")
    fsck = subprocess.run(["git", "-C", str(repo), "fsck", "--connectivity-only"], capture_output=True, text=True)
    if fsck.returncode != 0:
        problems.append("fsck: " + (fsck.stderr or fsck.stdout).strip()[:120])
    trees = [l for l in git(repo, "worktree", "list").splitlines() if l.strip()]
    if len(trees) != 1:
        problems.append(f"git worktree list zeigt {len(trees)} Einträge")
    return problems


def rollback(repo, say=print):
    repo = Path(repo)
    cur, alt = repo / ".git", repo / ".git.alt"
    if (cur / "hub-link").is_file():
        data = (cur / "hub-link").read_bytes()
    elif alt.is_file():
        data = alt.read_bytes()
    else:
        raise RuntimeError("keine alte Verknüpfung (.git/hub-link) gefunden: nichts zum Zurückstellen")
    if cur.is_dir():
        os.replace(cur, repo / ".git.neu")
    (repo / ".git").write_bytes(data)
    if alt.exists():
        os.remove(alt)
    git(repo, "rev-parse", "HEAD")                      # die alte Verknüpfung funktioniert wieder
    neu = repo / ".git.neu"
    if neu.is_dir():                                    # unser eigenes Duplikat; es würde sonst als unversioniert im Arbeitsordner stehen
        import stat

        def writable(func, path, _):
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(neu, onerror=writable)
    say("zurückgestellt: .git zeigt wieder in den Hub, das halbfertige neue Repository (.git.neu) ist entfernt")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--bundle", default=None)
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--no-process-check", action="store_true", help="nur für Tests")
    args = ap.parse_args(argv)
    repo = Path(args.repo)
    if args.rollback:
        rollback(repo)
        return 0
    bundle = Path(args.bundle) if args.bundle else Path(DEFAULT_BUNDLE_DIR) / f"A1_alle_refs_{datetime.date.today().isoformat()}.bundle"
    problems = preconditions(repo) if not args.no_process_check else [p for p in preconditions(repo) if "Prozess" not in p]
    hub = common_dir(repo) if (repo / ".git").exists() else None
    print(f"Repository {repo}")
    print(f"  gemeinsames Git-Verzeichnis (Hub): {hub}")
    if hub and Path(hub).exists():
        r = refs(git_dir=hub)
        print(f"  Refs: {len(r)} ({sum(1 for n in r if n.startswith('refs/heads/'))} Branches, {sum(1 for n in r if n.startswith('refs/tags/'))} Tags, {sum(1 for n in r if n.startswith('refs/remotes/'))} Remote-Refs)")
    print(f"  Bundle: {bundle} ({'vorhanden' if bundle.exists() else 'wird angelegt'})")
    for p in problems:
        print("PROBLEM:", p)
    if not args.go:
        print("Trockenlauf: nichts geändert. Mit --go nach dem Signal des Captains.")
        return 1 if problems else 0
    if problems:
        return 2
    make_bundle(repo, bundle)
    print("Bundle geprüft; baue um ...")
    result = convert(repo)
    print(f"Fertig: A1 hat ein eigenes Repository ({result['refs']} Refs übernommen, HEAD {result['head'][:9]} unverändert, git status sauber).")
    print("Die alte Verknüpfung liegt als .git/hub-link im neuen Repository (Rückweg: --rollback). Der Hub-Ordner wurde nicht angefasst; ihn zu löschen ist der Schritt des Captains.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
