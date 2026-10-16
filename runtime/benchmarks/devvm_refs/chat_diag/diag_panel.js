var DIAG_COMMANDS = ["status", "fehler", "rebind", "modelle", "log", "hilfe"];
var DIAG_SYMBOLS = {ok: "✔", warn: "⚠", bad: "✖"};

function slashCommand(text) {
    if (typeof text !== "string" || text.trim().charAt(0) !== "/") return null;
    var words = text.trim().slice(1).split(/\s+/).filter(function (w) { return w !== ""; });
    var name = words.length ? words[0].toLowerCase() : "";
    var args = words.slice(1);
    if (name === "plan") return null;
    if (DIAG_COMMANDS.indexOf(name) < 0) return {cmd: "unknown", name: name, args: [], confirm: false};
    var confirm = name === "rebind" && args.length > 0 && ["ja", "yes"].indexOf(args[0].toLowerCase()) >= 0;
    return {cmd: name, args: args, confirm: confirm};
}

function rowsText(rows) {
    if (!Array.isArray(rows)) return [];
    return rows.map(function (r) { return (DIAG_SYMBOLS[r.state] || "?") + " " + r.label + ": " + r.detail; });
}

function worstState(rows) {
    var rank = {ok: 0, warn: 1, bad: 2}, worst = "ok";
    if (!Array.isArray(rows)) return worst;
    rows.forEach(function (r) { if (rank[r.state] > rank[worst]) worst = r.state; });
    return worst;
}
