"""Coin hole for the Guppy meter (Captain 2026-10-12: "eine kleine Animation mit einem Loch im Boden, in dem immer wieder Muenzen verschwinden, in Anlehnung an den
Tokenverbrauch; verschiedene Muenzgroessen je nach Groesse des Tokenpakets"). A test task of another kind (drawing and timing instead of pure logic).
Stage 1: `usage_meter.py` sums the tokens of the build runs per range (python, judged in the microVM). Stages 2 and 3: `coin_hole.js`, a classic browser script: coins of three
sizes (gold 10,000, silver 1,000, copper 100 tokens), falling, drifting to the hole and shrinking in it, drawn on a canvas (judged on the host with node and a fake canvas).
Claude wires it into /api/meter and the meter window after acceptance. Claude wrote this file, the hidden tests and the reference (benchmarks/devvm_refs/coin_hole)."""

NOTES = '''# Notes for the coin hole
Python part: standard library only. JavaScript part: a CLASSIC script (no modules, no import/export, no DOM access at the top level); functions and `var` names become
globals of the page. Drawing goes through a canvas 2D context only (clearRect, beginPath, ellipse, arc, fill, fillStyle). No comments and no docstrings, small helpers instead of copied code.
'''

PY = r'''
from usage_meter import token_view
R = [{"date": "2026-10-12", "spec": "e06", "model": "qwen36", "tokens": 1000},
     {"date": "2026-10-12", "spec": "e10", "model": "coder", "tokens": 500},
     {"date": "2026-10-06", "spec": "am", "model": "x", "tokens": 200},
     {"date": "2026-10-05", "spec": "b", "model": "y", "tokens": 300},
     {"date": "2026-09-13", "spec": "c", "model": "z", "tokens": 50},
     {"date": "2026-09-12", "spec": "d", "model": "z", "tokens": 7},
     {"date": "x", "tokens": 5}, {"date": "2026-10-12", "tokens": -1}, {"date": "2026-10-12", "tokens": True}, {"date": "2026-10-12", "tokens": "9"}, "junk", {"tokens": 3}]
v = token_view(R, "2026-10-12")
assert v["ranges"] == {"today": {"tokens": 1500, "runs": 2}, "7": {"tokens": 1700, "runs": 3}, "30": {"tokens": 2050, "runs": 5}, "all": {"tokens": 2057, "runs": 6}}
assert v["last"] == {"date": "2026-10-12", "spec": "e10", "model": "coder", "tokens": 500}
s = v["series"]
assert len(s) == 14 and s[0] == {"date": "2026-09-29", "tokens": 0} and s[-1] == {"date": "2026-10-12", "tokens": 1500}
assert s[6] == {"date": "2026-10-05", "tokens": 300} and s[7] == {"date": "2026-10-06", "tokens": 200} and sum(x["tokens"] for x in s) == 2000
e = token_view([], "2026-10-12")
assert e["last"] is None and e["ranges"]["all"] == {"tokens": 0, "runs": 0} and len(e["series"]) == 14 and all(x["tokens"] == 0 for x in e["series"])
assert token_view([{"date": "2026-10-12", "tokens": 4}], "2026-10-12")["last"] == {"date": "2026-10-12", "spec": None, "model": None, "tokens": 4}
before = [dict(r) if isinstance(r, dict) else r for r in R]; token_view(R, "2026-10-12"); assert R == before
print("ok")
'''

JS_HEAD = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const box = { Math: Math, console: console };
vm.createContext(box); vm.runInContext(fs.readFileSync("coin_hole.js", "utf8"), box);
const near = (a, b) => Math.abs(a - b) < 1e-9;
function fakeCtx() {
  const log = [];
  const ctx = { log: log };
  ["clearRect", "beginPath", "ellipse", "arc", "fill"].forEach(n => { ctx[n] = (...a) => log.push([n, a]); });
  Object.defineProperty(ctx, "fillStyle", { set: v => log.push(["fillStyle", [v]]), get: () => null });
  return ctx;
}
'''

JS2 = r'''
const K = box.COIN_KINDS;
assert.deepStrictEqual([K.gold.value, K.silver.value, K.copper.value], [10000, 1000, 100]);
assert.deepStrictEqual([K.gold.r, K.silver.r, K.copper.r], [14, 10, 6]);
assert.deepStrictEqual([K.gold.color, K.silver.color, K.copper.color], ["#f2c94c", "#c0c7d0", "#c27c4e"]);
const cf = (a, b) => Array.from(box.coinsFor(a, b));
assert.deepStrictEqual(cf(null, 5000), []);
assert.deepStrictEqual(cf(0, 0), []);
assert.deepStrictEqual(cf(1000, 900), []);
assert.deepStrictEqual(cf(0, 99), []);
assert.deepStrictEqual(cf(0, 100), ["copper"]);
assert.deepStrictEqual(cf(50, 150), ["copper"]);
assert.deepStrictEqual(cf(99, 100), ["copper"]);
assert.deepStrictEqual(cf(0, 12345), ["gold", "silver", "silver", "copper", "copper", "copper"]);
assert.strictEqual(cf(0, 39900).length, 21);
const many = cf(0, 1000000);
assert.strictEqual(many.length, 30); assert.ok(many.every(k => k === "gold"));
const scene = { width: 400, height: 300, holeX: 200, holeY: 280, holeR: 40 };
const c0 = box.newCoin("silver", 0, scene);
assert.deepStrictEqual(JSON.parse(JSON.stringify(c0)), { kind: "silver", x: 80, y: -10, vy: 0, r: 10, scale: 1 });
assert.ok(near(box.newCoin("gold", 3, scene).x, 400 * (0.2 + 0.6 * 11 / 100)));
const coin = { kind: "copper", x: 80, y: -6, vy: 0, r: 6, scale: 1 };
let r = box.stepCoins([coin], 0.5, scene);
assert.strictEqual(r.swallowed, 0); assert.strictEqual(r.tokens, 0);
assert.deepStrictEqual(JSON.parse(JSON.stringify(r.coins[0])), { kind: "copper", x: 120, y: 144, vy: 300, r: 6, scale: 1 });
assert.deepStrictEqual(coin, { kind: "copper", x: 80, y: -6, vy: 0, r: 6, scale: 1 });
r = box.stepCoins(r.coins, 0.5, scene);
assert.strictEqual(r.coins[0].x, 160); assert.strictEqual(r.coins[0].y, 280); assert.strictEqual(r.coins[0].vy, 600);
r = box.stepCoins(r.coins, 0.25, scene);
assert.strictEqual(r.coins[0].scale, 0.5); assert.strictEqual(r.coins[0].x, 180); assert.strictEqual(r.coins[0].y, 280); assert.strictEqual(r.coins[0].vy, 600);
r = box.stepCoins(r.coins, 0.25, scene);
assert.strictEqual(r.coins.length, 0); assert.strictEqual(r.swallowed, 1); assert.strictEqual(r.tokens, 100);
const two = box.stepCoins([{ kind: "gold", x: 200, y: 280, vy: 0, r: 14, scale: 0.1 }, { kind: "silver", x: 210, y: 0, vy: 0, r: 10, scale: 1 }], 0.1, scene);
assert.strictEqual(two.swallowed, 1); assert.strictEqual(two.tokens, 10000); assert.strictEqual(two.coins.length, 1); assert.strictEqual(two.coins[0].x, 202);
const ctx = fakeCtx();
box.drawScene(ctx, scene, [{ kind: "gold", x: 50, y: 60, vy: 0, r: 14, scale: 0.5 }, { kind: "copper", x: 1, y: 2, vy: 0, r: 6, scale: 0 }]);
assert.deepStrictEqual(ctx.log.map(e => e[0]), ["clearRect", "fillStyle", "beginPath", "ellipse", "fill", "fillStyle", "beginPath", "arc", "fill"]);
assert.deepStrictEqual(ctx.log[0][1], [0, 0, 400, 300]);
assert.deepStrictEqual(ctx.log[1][1], ["#111"]);
assert.deepStrictEqual(ctx.log[3][1], [200, 280, 40, 14, 0, 0, 2 * Math.PI]);
assert.deepStrictEqual(ctx.log[5][1], ["#f2c94c"]);
assert.deepStrictEqual(ctx.log[7][1], [50, 60, 7, 0, 2 * Math.PI]);
console.log("ok");
'''

JS3 = r'''
const ctx3 = fakeCtx();
const canvas = { width: 400, height: 300, getContext: kind => (kind === "2d" ? ctx3 : null) };
const h = box.createCoinHole(canvas);
assert.strictEqual(h.update(5000), 0);
assert.deepStrictEqual(JSON.parse(JSON.stringify(h.stats())), { falling: 0, swallowed: 0, swallowedTokens: 0, tokens: 5000 });
assert.strictEqual(h.update(17100), 4);
assert.strictEqual(h.stats().falling, 4);
assert.strictEqual(h.update("x"), 0); assert.strictEqual(h.stats().tokens, 17100);
for (let i = 0; i < 200; i++) h.tick(0.05);
assert.deepStrictEqual(JSON.parse(JSON.stringify(h.stats())), { falling: 0, swallowed: 4, swallowedTokens: 12100, tokens: 17100 });
assert.strictEqual(ctx3.log.filter(e => e[0] === "clearRect").length, 200);
const g = box.createCoinHole({ width: 400, height: 300, getContext: () => fakeCtx() });
g.update(0);
assert.strictEqual(g.update(1000000), 30);
assert.strictEqual(g.update(2000000), 30);
assert.strictEqual(g.update(3000000), 0);
assert.strictEqual(g.stats().falling, 60);
console.log("ok");
'''

STAGES = [
    {"name": "tokens",
     "task": """Create `usage_meter.py` (Python 3 standard library only) with `token_view(records, today) -> dict`. records: a list of build runs, each a dict {"date": "YYYY-MM-DD", "spec": ..., "model": ..., "tokens": int}; today: "YYYY-MM-DD".
- A record counts only if it is a dict, its "date" parses with date.fromisoformat, and its "tokens" is an int (not a bool) >= 0; skip everything else.
- "ranges": {"today", "7", "30", "all"}, each {"tokens": sum, "runs": count}: "today" = date equal to today, "7" = dates from today-6 to today, "30" = from today-29 to today, "all" = every counted record.
- "last": the counted record with the latest date (on a tie the later one in the list) as {"date", "spec", "model", "tokens"} (missing keys give None), or None.
- "series": the 14 days up to today, oldest first, each {"date": "YYYY-MM-DD", "tokens": sum of that day}.
Never modify the arguments, no comments, no docstrings.""",
     "hidden": {"hidden_coin_1.py": PY}},
    {"name": "coins",
     "task": """Create `coin_hole.js` (a classic browser script, see NOTES.md) with:
- `var COIN_KINDS = {gold: {value: 10000, r: 14, color: "#f2c94c"}, silver: {value: 1000, r: 10, color: "#c0c7d0"}, copper: {value: 100, r: 6, color: "#c27c4e"}}`.
- `coinsFor(prevTokens, nowTokens)` -> array of kind names for the new tokens: [] unless both are numbers and nowTokens > prevTokens. h = floor(now / 100) - floor(prev / 100) (whole hundreds, so the rest carries over); then floor(h / 100) times "gold", floor((h % 100) / 10) times "silver", h % 10 times "copper", in this order, cut to at most 30 entries.
- `newCoin(kind, i, scene)` -> {kind, x: scene.width * (0.2 + 0.6 * ((i * 37) % 100) / 100), y: -r, vy: 0, r, scale: 1} with r of the kind.
- `stepCoins(coins, dt, scene)` -> {coins, swallowed, tokens}; never changes its input coins (new objects). scene = {width, height, holeX, holeY, holeR}. For each coin: x moves toward holeX by min(|holeX - x|, 80 * dt). If the coin was at the hole at the START of the step (y >= holeY): it does not fall; scale -= 2 * dt; at scale <= 0 it is swallowed (left out, swallowed + 1, tokens + value of its kind). Otherwise it falls: vy += 600 * dt, then y = min(holeY, y + vy * dt).
- `drawScene(ctx, scene, coins)`: clearRect(0, 0, width, height); fillStyle "#111", beginPath, ellipse(holeX, holeY, holeR, holeR * 0.35, 0, 0, 2 * Math.PI), fill; then for every coin with scale > 0: fillStyle = color of its kind, beginPath, arc(x, y, r * scale, 0, 2 * Math.PI), fill.""",
     "host_hidden": {"hidden_coin_2.cjs": JS_HEAD + JS2}},
    {"name": "hole",
     "task": """Add `createCoinHole(canvas)` to `coin_hole.js` (keep everything else). ctx = canvas.getContext("2d"); scene = {width: canvas.width, height: canvas.height, holeX: width / 2, holeY: height - 20, holeR: 40}. It returns an object with:
- `update(tokens)`: a non-number is ignored (returns 0). The FIRST number only sets the start value (no coins, returns 0). Later: the kinds of coinsFor(previous, tokens) become new coins (newCoin with a running counter i = 0, 1, 2, ... over the whole life of the hole), but never more than 60 coins on screen (the rest are skipped); remember tokens; return the number of coins added.
- `tick(dt)`: stepCoins over the coins, add swallowed and tokens to the totals, then drawScene.
- `stats()`: {falling: coins on screen, swallowed: total swallowed coins, swallowedTokens: total value swallowed, tokens: the last number given to update or null}.""",
     "host_hidden": {"hidden_coin_2.cjs": JS_HEAD + JS2, "hidden_coin_3.cjs": JS_HEAD + JS3}},
]
