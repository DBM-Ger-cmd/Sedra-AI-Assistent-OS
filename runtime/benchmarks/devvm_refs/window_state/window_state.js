var WINDOW_STATE_KEY = "guppi.windows.v1";
var WINDOW_MIN = {width: 320, height: 200};
var WINDOW_KEEP = {width: 80, height: 70};
var CASCADE_STEP = 28;
var CASCADE_START = 24;
var CASCADE_COUNT = 8;

function num(v, fallback) {
    return typeof v === "number" && isFinite(v) ? v : fallback;
}

function clampBox(box, desk, min) {
    var b = box && typeof box === "object" ? box : {};
    var m = min && typeof min === "object" ? min : WINDOW_MIN;
    var minW = num(m.width, WINDOW_MIN.width);
    var minH = num(m.height, WINDOW_MIN.height);
    var deskW = num(desk && desk.width, 0);
    var deskH = num(desk && desk.height, 0);
    var width = Math.round(Math.max(minW, Math.min(num(b.width, minW), Math.max(minW, deskW))));
    var height = Math.round(Math.max(minH, Math.min(num(b.height, minH), Math.max(minH, deskH))));
    var left = Math.round(Math.max(0, Math.min(num(b.left, 0), deskW - WINDOW_KEEP.width)));
    var top = Math.round(Math.max(0, Math.min(num(b.top, 0), deskH - WINDOW_KEEP.height)));
    return {left: left, top: top, width: width, height: height};
}

function cascadeBox(index, desk, size) {
    var i = Math.max(0, Math.floor(num(index, 0))) % CASCADE_COUNT;
    var s = size && typeof size === "object" ? size : {};
    var offset = CASCADE_START + i * CASCADE_STEP;
    return clampBox({left: offset, top: offset, width: num(s.width, WINDOW_MIN.width), height: num(s.height, WINDOW_MIN.height)}, desk, WINDOW_MIN);
}

function cleanWindow(w) {
    if (!w || typeof w !== "object" || typeof w.id !== "string" || !w.id) {
        return null;
    }
    var b = w.box && typeof w.box === "object" ? w.box : {};
    return {
        id: w.id,
        open: !!w.open,
        minimized: !!w.minimized,
        maximized: !!w.maximized,
        box: {left: Math.round(num(b.left, 0)), top: Math.round(num(b.top, 0)), width: Math.round(num(b.width, 0)), height: Math.round(num(b.height, 0))},
        z: Math.round(num(w.z, 0))
    };
}

function packWindows(list, now) {
    var items = [];
    if (Array.isArray(list)) {
        for (var i = 0; i < list.length; i++) {
            var c = cleanWindow(list[i]);
            if (c) {
                c.order = i;
                items.push(c);
            }
        }
    }
    items.sort(function(a, b) { return a.z - b.z || a.order - b.order; });
    for (var k = 0; k < items.length; k++) {
        delete items[k].order;
    }
    return {v: 1, saved: typeof now === "number" ? now : 0, windows: items};
}

function unpackWindows(raw, knownIds, desk) {
    if (typeof raw !== "string" || !Array.isArray(knownIds)) {
        return null;
    }
    var data;
    try {
        data = JSON.parse(raw);
    } catch (e) {
        return null;
    }
    if (!data || typeof data !== "object" || data.v !== 1 || !Array.isArray(data.windows)) {
        return null;
    }
    var out = [];
    var seen = {};
    for (var i = 0; i < data.windows.length; i++) {
        var c = cleanWindow(data.windows[i]);
        if (!c || knownIds.indexOf(c.id) < 0 || seen[c.id]) {
            continue;
        }
        seen[c.id] = true;
        out.push({id: c.id, open: c.open, minimized: c.minimized, maximized: c.maximized, box: clampBox(c.box, desk, WINDOW_MIN)});
    }
    return out;
}
