import argparse
import datetime
import json
import os
import re
import subprocess
import sys

OUT_NAMES = ("dashboard_data.json", "INDEX.md", "PROJEKT_DASHBOARD.html")
EXCLUDE = {"__pycache__", "node_modules", ".venv"}
SYSTEM = {".git", ".claude"}
CODE = {".py", ".js", ".ts", ".html", ".css", ".bat", ".ps1", ".sh"}
DOCS = {".md", ".txt", ".rst"}
CONFIG = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"}
FIELDS = ("files_direct", "files_recursive", "dirs_direct", "dirs_recursive")
COUNT_MODE = "direkt zaehlt nur den Ordner selbst (files_direct, dirs_direct), rekursiv alle Unterordner mit (files_recursive, dirs_recursive)"


def file_category(name):
    ext = os.path.splitext(name)[1].lower()
    if ext in CODE:
        return "code"
    if ext in DOCS:
        return "docs"
    if ext in CONFIG:
        return "config"
    return "other"


def count_system(path):
    files = dirs = 0
    direct = None
    for _, dirnames, filenames in os.walk(path):
        if direct is None:
            direct = (len(filenames), len(dirnames))
        dirs += len(dirnames)
        files += len(filenames)
    return direct, (files, dirs)


def scan_dir(path, rel, root_level):
    name = "." if rel == "." else os.path.basename(path)
    node = {"name": name, "path": rel, "type": "dir", "children": []}
    tally = {}
    files_direct = dirs_direct = files_rec = dirs_rec = size = 0
    entries = sorted(os.listdir(path), key=lambda n: (not os.path.isdir(os.path.join(path, n)), n.lower()))
    for entry in entries:
        full = os.path.join(path, entry)
        child_rel = entry if rel == "." else rel + "/" + entry
        if os.path.isdir(full):
            if entry in EXCLUDE:
                continue
            dirs_direct += 1
            if entry in SYSTEM:
                direct, total = count_system(full)
                child = {"name": entry, "path": child_rel, "type": "dir", "category": "system", "files_direct": direct[0], "files_recursive": total[0],
                         "dirs_direct": direct[1], "dirs_recursive": total[1], "size_bytes": 0, "children": []}
                child_tally = {}
            else:
                child, child_tally = scan_dir(full, child_rel, False)
            node["children"].append(child)
            dirs_rec += 1 + child["dirs_recursive"]
            files_rec += child["files_recursive"]
            size += child["size_bytes"]
            if child["category"] != "system":
                for cat, n in child_tally.items():
                    tally[cat] = tally.get(cat, 0) + n
        else:
            if root_level and entry in OUT_NAMES:
                continue
            cat = file_category(entry)
            file_size = os.path.getsize(full)
            node["children"].append({"name": entry, "path": child_rel, "type": "file", "category": cat, "size_bytes": file_size})
            files_direct += 1
            files_rec += 1
            size += file_size
            tally[cat] = tally.get(cat, 0) + 1
    if tally:
        category = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    else:
        category = "other"
    node.update({"category": category, "files_direct": files_direct, "files_recursive": files_rec, "dirs_direct": dirs_direct,
                 "dirs_recursive": dirs_rec, "size_bytes": size})
    return node, tally


def git_info(root):
    info = {"branch": None, "commit": None, "date": None, "total_commits": 0}
    try:
        def run(*args):
            return subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True, timeout=20)
        top = run("rev-parse", "--show-toplevel")
        if top.returncode != 0 or os.path.normcase(os.path.realpath(top.stdout.strip())) != os.path.normcase(os.path.realpath(root)):
            return info
        info["branch"] = run("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or None
        info["commit"] = run("rev-parse", "--short", "HEAD").stdout.strip() or None
        info["date"] = run("log", "-1", "--format=%cI").stdout.strip() or None
        count = run("rev-list", "--count", "HEAD").stdout.strip()
        info["total_commits"] = int(count) if count.isdigit() else 0
    except (OSError, subprocess.SubprocessError):
        pass
    return info


def build_data(root):
    node, _ = scan_dir(root, ".", True)
    node["generated_at"] = datetime.datetime.now().replace(microsecond=0).isoformat()
    node["git_info"] = git_info(root)
    node["count_mode"] = COUNT_MODE
    return node


def index_text(data):
    git = data["git_info"]
    git_line = f"{git['branch']}@{git['commit']} ({git['total_commits']} Commits)" if git["commit"] else "kein Repository"
    lines = ["# Projekt-Index", "", f"Erzeugt: {data['generated_at']}", f"Git: {git_line}", f"Zaehlweise: {data['count_mode']}", "",
             "| Verzeichnis | Kategorie | Dateien direkt | Dateien rekursiv | Unterordner direkt | Unterordner rekursiv |",
             "|---|---|---|---|---|---|"]
    rows = [data] + [c for c in data["children"] if c["type"] == "dir"]
    for r in rows:
        lines.append(f"| {r['path']} | {r['category']} | {r['files_direct']} | {r['files_recursive']} | {r['dirs_direct']} | {r['dirs_recursive']} |")
    return "\n".join(lines) + "\n"


def check(out):
    json_path = os.path.join(out, "dashboard_data.json")
    index_path = os.path.join(out, "INDEX.md")
    for p in (json_path, index_path):
        if not os.path.exists(p):
            print("fehlt: " + os.path.basename(p))
            return 1
    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)
    by_path = {data["path"]: data}
    for child in data["children"]:
        if child["type"] == "dir":
            by_path[child["path"]] = child
    problems = []
    seen = set()
    with open(index_path, encoding="utf-8") as fh:
        for line in fh:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != 6 or cells[0] not in by_path:
                continue
            seen.add(cells[0])
            for field, value in zip(FIELDS, cells[2:]):
                if str(by_path[cells[0]][field]) != value:
                    problems.append(f"abweichung: {cells[0]} {field} index={value} json={by_path[cells[0]][field]}")
    for path in by_path:
        if path not in seen:
            problems.append(f"abweichung: {path} fehlt im Index")
    if problems:
        print("\n".join(problems))
        return 1
    print("konsistent")
    return 0


HTML = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Projekt-Dashboard</title>
<style>
body { font-family: sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
header, main, footer { max-width: 1200px; margin: 0 auto; padding: 12px 20px; }
.stats { display: flex; gap: 16px; }
.stat { background: #1e293b; padding: 12px 20px; border-radius: 8px; }
.stat b { display: block; font-size: 24px; }
.layout { display: grid; grid-template-columns: 320px 1fr; gap: 20px; }
.tree-item { cursor: pointer; padding: 3px 6px; border-radius: 4px; }
.tree-item:hover { background: #334155; }
.tree-children { margin-left: 16px; }
.file-item { display: flex; justify-content: space-between; padding: 6px 10px; border-bottom: 1px solid #334155; }
.cat-code { color: #7ec8e3; } .cat-docs { color: #f0c040; } .cat-config { color: #7ec37e; } .cat-system { color: #aaa; } .cat-other { color: #c89ef0; }
.more { background: #3b82f6; color: white; padding: 8px; text-align: center; cursor: pointer; border-radius: 6px; margin-top: 8px; }
input { width: 100%; padding: 8px; background: #1e293b; color: inherit; border: 1px solid #334155; border-radius: 6px; }
</style>
</head>
<body>
<header>
<h1>Projekt-Dashboard</h1>
<div class="stats">
<div class="stat"><span>Dateien (rekursiv)</span><b id="statFiles">-</b></div>
<div class="stat"><span>Verzeichnisse (rekursiv)</span><b id="statDirs">-</b></div>
<div class="stat"><span>Groesse</span><b id="statSize">-</b></div>
</div>
<p><button onclick="exportJSON()">Export JSON</button></p>
<input id="globalSearch" placeholder="Global suchen in Verzeichnissen und Dateien">
<div id="searchResults"></div>
</header>
<main class="layout">
<aside><div id="treeContainer"></div></aside>
<section><h2 id="currentPath">.</h2><div id="fileList"></div></section>
</main>
<footer id="dashboardFooter"></footer>
<script>
const MAX_ITEMS = 200;
let DATA = null;
function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
function fmtSize(b) {
  if (b < 1024) { return b + " B"; }
  if (b < 1048576) { return (b / 1024).toFixed(1) + " KB"; }
  return (b / 1048576).toFixed(1) + " MB";
}
function entryHtml(c) {
  const meta = c.type === "dir" ? "Verzeichnis, " + c.files_recursive + " Dateien rekursiv" : fmtSize(c.size_bytes);
  return '<div class="file-item cat-' + esc(c.category) + '"><span>' + esc(c.name) + "</span><span>" + meta + "</span></div>";
}
function showDirectory(node) {
  document.getElementById("currentPath").textContent = node.path;
  const list = document.getElementById("fileList");
  list.innerHTML = "";
  let shown = 0;
  function more() {
    const next = node.children.slice(shown, shown + MAX_ITEMS);
    list.insertAdjacentHTML("beforeend", next.map(entryHtml).join(""));
    shown += next.length;
    const old = list.querySelector(".more");
    if (old) { old.remove(); }
    if (shown < node.children.length) {
      const btn = document.createElement("div");
      btn.className = "more";
      btn.textContent = (node.children.length - shown) + " weitere laden";
      btn.onclick = more;
      list.appendChild(btn);
    }
  }
  more();
}
function renderTree(node, container) {
  const row = document.createElement("div");
  row.className = "tree-item cat-" + node.category;
  row.textContent = node.name + " (" + node.files_recursive + ")";
  const kids = document.createElement("div");
  kids.className = "tree-children";
  let open = false;
  row.onclick = function () {
    showDirectory(node);
    open = !open;
    kids.innerHTML = "";
    if (open) {
      node.children.filter(function (c) { return c.type === "dir"; }).slice(0, MAX_ITEMS).forEach(function (c) { renderTree(c, kids); });
    }
  };
  container.appendChild(row);
  container.appendChild(kids);
}
function flatten(node, acc) {
  node.children.forEach(function (c) { acc.push(c); if (c.type === "dir") { flatten(c, acc); } });
  return acc;
}
function initGlobalSearch() {
  const all = flatten(DATA, []);
  document.getElementById("globalSearch").addEventListener("input", function (ev) {
    const q = ev.target.value.toLowerCase().trim();
    const out = document.getElementById("searchResults");
    if (q.length < 2) { out.textContent = ""; return; }
    const hits = all.filter(function (c) { return c.name.toLowerCase().indexOf(q) >= 0; });
    out.textContent = hits.length + " Treffer: " + hits.slice(0, 20).map(function (c) { return c.path; }).join(", ");
  });
}
function showGitInfo() {
  const g = DATA.git_info || {};
  const git = g.commit ? g.branch + "@" + g.commit + " (" + g.total_commits + " Commits)" : "kein Repository";
  document.getElementById("dashboardFooter").textContent = "Erzeugt: " + DATA.generated_at + " | Git: " + git;
}
function exportJSON() {
  const blob = new Blob([JSON.stringify(DATA, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "dashboard_data.json";
  a.click();
}
function init(data) {
  DATA = data;
  document.getElementById("statFiles").textContent = data.files_recursive.toLocaleString("de-DE");
  document.getElementById("statDirs").textContent = data.dirs_recursive.toLocaleString("de-DE");
  document.getElementById("statSize").textContent = fmtSize(data.size_bytes);
  renderTree(data, document.getElementById("treeContainer"));
  showDirectory(data);
  initGlobalSearch();
  showGitInfo();
}
function showError(err) {
  document.body.innerHTML = "<p>dashboard_data.json konnte nicht geladen werden (" + esc(err) + "). Bitte mit python -m http.server starten und im Browser oeffnen.</p>";
}
fetch("dashboard_data.json").then(function (r) { if (!r.ok) { throw new Error(r.status); } return r.json(); }).then(init).catch(showError);
</script>
</body>
</html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)
    out = os.path.abspath(args.out or root)
    if args.check:
        return check(out)
    os.makedirs(out, exist_ok=True)
    data = build_data(root)
    with open(os.path.join(out, "dashboard_data.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(out, "INDEX.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(index_text(data))
    with open(os.path.join(out, "PROJEKT_DASHBOARD.html"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(HTML)
    return 0


if __name__ == "__main__":
    sys.exit(main())
