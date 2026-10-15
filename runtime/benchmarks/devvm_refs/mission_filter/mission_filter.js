var MISSION_PHASES = ["READY", "PAUSED", "CAPTAIN_REVIEW", "CANDIDATE_REVIEW", "REWORK", "COMPLETE", "FAILED"];
var MISSION_GROUPS = ["Heute", "Gestern", "Diese Woche", "Älter"];

function text(v) {
    return typeof v === "string" ? v : "";
}

function missionText(m) {
    return (text(m.mission_id) + " " + text(m.intent) + " " + text(m.objective)).toLowerCase();
}

function filterMissions(list, query, phases, onlyGates) {
    if (!Array.isArray(list)) {
        return [];
    }
    var words = text(query).toLowerCase().split(/\s+/).filter(function(w) { return w !== ""; });
    var wanted = Array.isArray(phases) && phases.length ? phases : null;
    var out = [];
    for (var i = 0; i < list.length; i++) {
        var m = list[i];
        if (!m || typeof m !== "object") {
            continue;
        }
        var hay = missionText(m);
        var hit = true;
        for (var w = 0; w < words.length; w++) {
            if (hay.indexOf(words[w]) < 0) {
                hit = false;
                break;
            }
        }
        if (!hit) {
            continue;
        }
        if (wanted && wanted.indexOf(m.phase) < 0) {
            continue;
        }
        if (onlyGates && !(typeof m.pending_gates === "number" && m.pending_gates > 0)) {
            continue;
        }
        out.push({m: m, i: i});
    }
    out.sort(function(a, b) {
        var ca = text(a.m.created_at), cb = text(b.m.created_at);
        if (ca < cb) { return 1; }
        if (ca > cb) { return -1; }
        return a.i - b.i;
    });
    return out.map(function(e) { return e.m; });
}

function dayNumber(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(text(iso));
    if (!m) {
        return null;
    }
    var d = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
    return isNaN(d) ? null : Math.floor(d / 864e5);
}

function missionGroupLabel(createdAt, today) {
    var day = dayNumber(createdAt), ref = dayNumber(today);
    if (day === null || ref === null) {
        return MISSION_GROUPS[3];
    }
    var diff = ref - day;
    if (diff < 0) {
        return MISSION_GROUPS[0];
    }
    if (diff === 0) {
        return MISSION_GROUPS[0];
    }
    if (diff === 1) {
        return MISSION_GROUPS[1];
    }
    if (diff <= 6) {
        return MISSION_GROUPS[2];
    }
    return MISSION_GROUPS[3];
}

function missionGroups(list, today) {
    var buckets = {};
    var k;
    for (k = 0; k < MISSION_GROUPS.length; k++) {
        buckets[MISSION_GROUPS[k]] = [];
    }
    if (Array.isArray(list)) {
        for (var i = 0; i < list.length; i++) {
            var m = list[i];
            if (m && typeof m === "object") {
                buckets[missionGroupLabel(m.created_at, today)].push(m);
            }
        }
    }
    var out = [];
    for (k = 0; k < MISSION_GROUPS.length; k++) {
        if (buckets[MISSION_GROUPS[k]].length) {
            out.push({label: MISSION_GROUPS[k], items: buckets[MISSION_GROUPS[k]]});
        }
    }
    return out;
}

function missionLine(m) {
    var o = m && typeof m === "object" ? m : {};
    var intent = text(o.intent) || text(o.objective);
    if (intent.length > 60) {
        intent = intent.slice(0, 60) + "…";
    }
    var line = text(o.mission_id) + " · " + (text(o.phase) || "?") + " · " + intent;
    var gates = typeof o.pending_gates === "number" ? o.pending_gates : 0;
    if (gates === 1) {
        line += " · 1 Freigabe offen";
    } else if (gates > 1) {
        line += " · " + gates + " Freigaben offen";
    }
    return line;
}
