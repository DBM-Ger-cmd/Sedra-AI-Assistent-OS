function newStreamState() {
    return {text: "", done: false, model: "", truncated: false, error: ""};
}

function parseSse(buffer) {
    var text = String(buffer).replace(/\r\n/g, "\n");
    var cut = text.lastIndexOf("\n\n");
    if (cut < 0) {
        return {events: [], rest: text};
    }
    var events = [];
    var blocks = text.slice(0, cut).split("\n\n");
    for (var i = 0; i < blocks.length; i++) {
        var data = blocks[i].split("\n").filter(function(l) { return l.indexOf("data: ") === 0; }).map(function(l) { return l.slice(6); }).join("\n");
        try {
            var ev = JSON.parse(data);
            if (ev !== null && typeof ev === "object" && !Array.isArray(ev)) {
                events.push(ev);
            }
        } catch (e) {
        }
    }
    return {events: events, rest: text.slice(cut + 2)};
}

function applyEvent(state, ev) {
    var next = {text: state.text, done: state.done, model: state.model, truncated: state.truncated, error: state.error};
    if (typeof ev.delta === "string") {
        next.text += ev.delta;
    }
    if (ev.done === true) {
        next.done = true;
        next.model = typeof ev.model === "string" ? ev.model : "";
        next.truncated = ev.truncated === true;
    }
    if (typeof ev.error === "string") {
        next.error = ev.error;
    }
    return next;
}
