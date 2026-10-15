var DIAG_COMMANDS = ["status", "fehler", "rebind", "modelle", "log", "hilfe"];

function slashCommand(text) {
    if (typeof text !== "string") {
        return null;
    }
    var trimmed = text.trim();
    if (trimmed.charAt(0) !== "/") {
        return null;
    }
    var withoutSlash = trimmed.substring(1);
    var words = withoutSlash.split(/\s+/).filter(function(w) { return w !== ""; });
    var name = words.length > 0 ? words[0].toLowerCase() : "";
    var args = words.length > 1 ? words.slice(1) : [];
    if (name === "plan") {
        return null;
    }
    var known = {};
    for (var i = 0; i < DIAG_COMMANDS.length; i++) {
        known[DIAG_COMMANDS[i]] = true;
    }
    if (!known[name]) {
        return {cmd: "unknown", name: name, args: [], confirm: false};
    }
    var confirm = false;
    if (name === "rebind" && args.length > 0) {
        if (args[0].toLowerCase() === "ja" || args[0].toLowerCase() === "yes") {
            confirm = true;
        }
    }
    return {cmd: name, args: args, confirm: confirm};
}

function rowsText(rows) {
    if (!Array.isArray(rows)) {
        return [];
    }
    return rows.map(function(row) {
        var symbol;
        if (row.state === "ok") {
            symbol = "\u2714";
        } else if (row.state === "warn") {
            symbol = "\u26A0";
        } else if (row.state === "bad") {
            symbol = "\u2716";
        } else {
            symbol = "?";
        }
        return symbol + " " + row.label + ": " + row.detail;
    });
}

function worstState(rows) {
    if (!Array.isArray(rows)) {
        return "ok";
    }
    for (var i = 0; i < rows.length; i++) {
        if (rows[i].state === "bad") {
            return "bad";
        }
    }
    for (var j = 0; j < rows.length; j++) {
        if (rows[j].state === "warn") {
            return "warn";
        }
    }
    return "ok";
}
