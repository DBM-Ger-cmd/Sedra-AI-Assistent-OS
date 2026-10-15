var CHAT_STORE_KEY = "guppi.chat.v1";
var CHAT_STORE_TURNS = 40;
var CHAT_STORE_MAX_AGE_MS = 7 * 864e5;
var CHAT_STORE_CHARS = 4000;

function cleanTurns(history) {
    var out = [];
    if (!Array.isArray(history)) {
        return out;
    }
    for (var i = 0; i < history.length; i++) {
        var t = history[i];
        if (t && typeof t === "object" && (t.role === "user" || t.role === "assistant") && typeof t.content === "string") {
            out.push({role: t.role, content: t.content.slice(0, CHAT_STORE_CHARS)});
        }
    }
    return out.slice(Math.max(0, out.length - CHAT_STORE_TURNS));
}

function cleanProject(project) {
    if (project && typeof project === "object" && typeof project.id === "string" && typeof project.name === "string" && project.id) {
        return {id: project.id, name: project.name};
    }
    return null;
}

function packChat(history, mission, project, now) {
    return {
        v: 1,
        saved: typeof now === "number" ? now : 0,
        mission: typeof mission === "string" && mission ? mission : null,
        project: cleanProject(project),
        history: cleanTurns(history)
    };
}

function unpackChat(raw, now) {
    if (typeof raw !== "string" || typeof now !== "number") {
        return null;
    }
    var data;
    try {
        data = JSON.parse(raw);
    } catch (e) {
        return null;
    }
    if (!data || typeof data !== "object" || data.v !== 1 || typeof data.saved !== "number") {
        return null;
    }
    var age = now - data.saved;
    if (age < 0 || age > CHAT_STORE_MAX_AGE_MS) {
        return null;
    }
    return {
        history: cleanTurns(data.history),
        mission: typeof data.mission === "string" && data.mission ? data.mission : null,
        project: cleanProject(data.project),
        age_ms: age
    };
}

function chatSummary(history) {
    var turns = cleanTurns(history);
    if (!turns.length) {
        return "";
    }
    var last = null;
    for (var i = turns.length - 1; i >= 0; i--) {
        if (turns[i].role === "user") {
            last = turns[i].content;
            break;
        }
    }
    var head = "Verlauf mit " + (turns.length === 1 ? "1 Nachricht" : turns.length + " Nachrichten") + " wiederhergestellt";
    if (last === null) {
        return head + ".";
    }
    var text = last.length > 60 ? last.slice(0, 60) + "…" : last;
    return head + " (zuletzt: " + text + ").";
}
