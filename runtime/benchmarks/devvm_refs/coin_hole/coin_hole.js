var COIN_KINDS = { gold: { value: 10000, r: 14, color: "#f2c94c" }, silver: { value: 1000, r: 10, color: "#c0c7d0" }, copper: { value: 100, r: 6, color: "#c27c4e" } };
var COIN_GRAVITY = 600, COIN_DRIFT = 80, COIN_SHRINK = 2, COIN_CAP = 30, COIN_SCREEN = 60;

function coinsFor(prevTokens, nowTokens) {
  if (typeof prevTokens !== "number" || typeof nowTokens !== "number" || nowTokens <= prevTokens) return [];
  var h = Math.floor(nowTokens / 100) - Math.floor(prevTokens / 100), out = [], i;
  var counts = [["gold", Math.floor(h / 100)], ["silver", Math.floor((h % 100) / 10)], ["copper", h % 10]];
  counts.forEach(function (pair) { for (i = 0; i < pair[1]; i++) out.push(pair[0]); });
  return out.slice(0, COIN_CAP);
}

function newCoin(kind, i, scene) {
  var r = COIN_KINDS[kind].r;
  return { kind: kind, x: scene.width * (0.2 + 0.6 * ((i * 37) % 100) / 100), y: -r, vy: 0, r: r, scale: 1 };
}

function stepCoins(coins, dt, scene) {
  var out = [], swallowed = 0, tokens = 0;
  coins.forEach(function (c) {
    var n = { kind: c.kind, x: c.x, y: c.y, vy: c.vy, r: c.r, scale: c.scale };
    var dx = scene.holeX - n.x;
    n.x += Math.sign(dx) * Math.min(Math.abs(dx), COIN_DRIFT * dt);
    if (c.y >= scene.holeY) {
      n.scale = c.scale - COIN_SHRINK * dt;
      if (n.scale <= 0) { swallowed += 1; tokens += COIN_KINDS[c.kind].value; return; }
    } else {
      n.vy = c.vy + COIN_GRAVITY * dt;
      n.y = Math.min(scene.holeY, c.y + n.vy * dt);
    }
    out.push(n);
  });
  return { coins: out, swallowed: swallowed, tokens: tokens };
}

function drawScene(ctx, scene, coins) {
  ctx.clearRect(0, 0, scene.width, scene.height);
  ctx.fillStyle = "#111";
  ctx.beginPath();
  ctx.ellipse(scene.holeX, scene.holeY, scene.holeR, scene.holeR * 0.35, 0, 0, 2 * Math.PI);
  ctx.fill();
  coins.forEach(function (c) {
    if (c.scale <= 0) return;
    ctx.fillStyle = COIN_KINDS[c.kind].color;
    ctx.beginPath();
    ctx.arc(c.x, c.y, c.r * c.scale, 0, 2 * Math.PI);
    ctx.fill();
  });
}

function createCoinHole(canvas) {
  var ctx = canvas.getContext("2d");
  var scene = { width: canvas.width, height: canvas.height, holeX: canvas.width / 2, holeY: canvas.height - 20, holeR: 40 };
  var coins = [], prev = null, swallowed = 0, swallowedTokens = 0, made = 0;
  return {
    update: function (tokens) {
      var kinds = prev === null ? [] : coinsFor(prev, tokens), added = 0;
      if (typeof tokens === "number") prev = tokens;
      kinds.forEach(function (kind) { if (coins.length < COIN_SCREEN) { coins.push(newCoin(kind, made, scene)); made += 1; added += 1; } });
      return added;
    },
    tick: function (dt) {
      var res = stepCoins(coins, dt, scene);
      coins = res.coins; swallowed += res.swallowed; swallowedTokens += res.tokens;
      drawScene(ctx, scene, coins);
    },
    stats: function () { return { falling: coins.length, swallowed: swallowed, swallowedTokens: swallowedTokens, tokens: prev }; },
    scene: scene
  };
}
