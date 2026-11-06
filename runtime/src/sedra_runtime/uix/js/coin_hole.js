var COIN_KINDS = {gold: {value: 10000, r: 14, color: "#f2c94c"}, silver: {value: 1000, r: 10, color: "#c0c7d0"}, copper: {value: 100, r: 6, color: "#c27c4e"}};

function coinsFor(prevTokens, nowTokens) {
    if (typeof prevTokens !== 'number' || typeof nowTokens !== 'number' || nowTokens <= prevTokens) {
        return [];
    }
    var h = Math.floor(nowTokens / 100) - Math.floor(prevTokens / 100);
    var result = [];
    var goldCount = Math.floor(h / 100);
    var silverCount = Math.floor((h % 100) / 10);
    var copperCount = h % 10;
    var i = 0;
    var j = 0;
    while (i < goldCount && result.length < 30) {
        result.push("gold");
        i++;
    }
    i = 0;
    while (i < silverCount && result.length < 30) {
        result.push("silver");
        i++;
    }
    i = 0;
    while (i < copperCount && result.length < 30) {
        result.push("copper");
        i++;
    }
    return result;
}

function newCoin(kind, i, scene) {
    var info = COIN_KINDS[kind];
    var r = info.r;
    var x = scene.width * (0.2 + 0.6 * ((i * 37) % 100) / 100);
    var y = -r;
    return {kind: kind, x: x, y: y, vy: 0, r: r, scale: 1};
}

function stepCoins(coins, dt, scene) {
    var newCoins = [];
    var swallowed = [];
    var tokens = 0;
    for (var c = 0; c < coins.length; c++) {
        var coin = coins[c];
        var wasAtHole = coin.y >= scene.holeY;
        var dx = scene.holeX - coin.x;
        var nx = coin.x;
        if (Math.abs(dx) > 80 * dt) {
            nx = coin.x + Math.sign(dx) * 80 * dt;
        } else {
            nx = scene.holeX;
        }
        if (wasAtHole) {
            var ns = coin.scale - 2 * dt;
            if (ns <= 0) {
                swallowed.push(coin.kind);
                tokens += COIN_KINDS[coin.kind].value;
            } else {
                newCoins.push({kind: coin.kind, x: nx, y: coin.y, vy: coin.vy, r: coin.r, scale: ns});
            }
        } else {
            var nvy = coin.vy + 600 * dt;
            var ny = Math.min(scene.holeY, coin.y + nvy * dt);
            newCoins.push({kind: coin.kind, x: nx, y: ny, vy: nvy, r: coin.r, scale: coin.scale});
        }
    }
    return {coins: newCoins, swallowed: swallowed, tokens: tokens};
}

function drawScene(ctx, scene, coins) {
    ctx.clearRect(0, 0, scene.width, scene.height);
    ctx.fillStyle = "#111";
    ctx.beginPath();
    ctx.ellipse(scene.holeX, scene.holeY, scene.holeR, scene.holeR * 0.35, 0, 0, 2 * Math.PI);
    ctx.fill();
    for (var i = 0; i < coins.length; i++) {
        var coin = coins[i];
        if (coin.scale > 0) {
            var info = COIN_KINDS[coin.kind];
            ctx.fillStyle = info.color;
            ctx.beginPath();
            ctx.arc(coin.x, coin.y, coin.r * coin.scale, 0, 2 * Math.PI);
            ctx.fill();
        }
    }
}

function pileFor(tokens) {
    var h = Math.floor((tokens || 0) / 100);
    var n = [Math.floor(h / 100), Math.floor((h % 100) / 10), h % 10];
    var total = n[0] + n[1] + n[2];
    var out = [];
    var kinds = ["gold", "silver", "copper"];
    for (var k = 0; k < 3; k++) {
        var c = total > 150 && n[k] > 0 ? Math.max(1, Math.round(n[k] * 150 / total)) : n[k];
        for (var i = 0; i < c; i++) {
            out.push(kinds[k]);
        }
    }
    return out;
}

function drawPit(ctx, scene, pile, peek, label) {
    if (peek <= 0) {
        return;
    }
    var w = scene.width * 0.8;
    var h = scene.height * 0.8 * peek;
    var x = (scene.width - w) / 2;
    var y = scene.height - h;
    ctx.save();
    ctx.globalAlpha = Math.min(1, peek * 1.5);
    ctx.fillStyle = "#1b1712";
    ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = "#5a4d3a";
    ctx.strokeRect(x, y, w, h);
    ctx.beginPath();
    ctx.rect(x, y, w, h);
    ctx.clip();
    var rowH = 9;
    for (var i = 0; i < pile.length; i++) {
        var info = COIN_KINDS[pile[i]];
        var perRow = Math.floor((w - 20) / 20);
        var row = Math.floor(i / perRow);
        var col = i % perRow;
        var cx = x + 14 + col * 20 + (row % 2) * 8 + ((i * 7) % 5);
        var cy = scene.height - 8 - row * rowH + ((i * 3) % 3);
        ctx.fillStyle = info.color;
        ctx.beginPath();
        ctx.ellipse(cx, cy, info.r * 0.9, info.r * 0.5, 0, 0, 2 * Math.PI);
        ctx.fill();
        ctx.strokeStyle = "rgba(0,0,0,0.35)";
        ctx.stroke();
    }
    ctx.restore();
    ctx.fillStyle = "#e8e0c8";
    ctx.font = "12px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(label || (pile.length ? "Im Loch: " + pile.length + " Münzen (zuletzt)" : "Noch keine Münzen im Loch"), scene.width / 2, y + 14);
}

function createCoinHole(canvas) {
    var ctx = canvas.getContext("2d");
    var scene = {width: canvas.width, height: canvas.height, holeX: canvas.width / 2, holeY: canvas.height - 20, holeR: 40};
    var coins = [];
    var pending = [];
    var spawnTimer = 0;
    var pile = [];
    var override = null;
    var overrideLabel = "";
    var peek = 0;
    var peekOpen = false;
    var peekTime = 0;
    var totalSwallowed = 0;
    var totalTokens = 0;
    var prevTokens = null;
    var firstNumber = true;
    var coinCounter = 0;

    canvas.style.cursor = "pointer";
    canvas.addEventListener("click", function() {
        if (override) {
            override = null;
        }
        peekOpen = !peekOpen;
        peekTime = 0;
    });

    return {
        update: function(tokens) {
            if (typeof tokens !== 'number') {
                return 0;
            }
            if (firstNumber) {
                prevTokens = tokens;
                firstNumber = false;
                return 0;
            }
            var kinds = coinsFor(prevTokens, tokens);
            var added = 0;
            for (var k = 0; k < kinds.length; k++) {
                if (pending.length >= 200) {
                    break;
                }
                pending.push(kinds[k]);
                added++;
            }
            prevTokens = tokens;
            return added;
        },
        tick: function(dt) {
            if (pending.length) {
                spawnTimer -= dt;
                if (spawnTimer <= 0 && coins.length < 60) {
                    coins.push(newCoin(pending.shift(), coinCounter, scene));
                    coinCounter++;
                    spawnTimer = Math.max(0.15, Math.min(0.8, 20 / (pending.length + 1)));
                }
            }
            var result = stepCoins(coins, dt, scene);
            for (var s = 0; s < result.swallowed.length; s++) {
                pile.push(result.swallowed[s]);
            }
            if (pile.length > 120) {
                pile = pile.slice(pile.length - 120);
            }
            coins = result.coins;
            totalSwallowed += result.swallowed.length;
            totalTokens += result.tokens;
            if (peekOpen) {
                peekTime += dt;
                if (peekTime > 6 && !override) {
                    peekOpen = false;
                }
            }
            peek = Math.max(0, Math.min(1, peek + (peekOpen ? 4 : -4) * dt));
            drawScene(ctx, scene, coins);
            drawPit(ctx, scene, override || pile, peek, override ? overrideLabel : "");
        },
        showPile: function(tokens, label, open) {
            if (tokens === null) {
                override = null;
                return;
            }
            override = pileFor(tokens);
            overrideLabel = label + ": " + Number(tokens).toLocaleString("de-DE") + " Token";
            if (open) {
                peekOpen = true;
                peekTime = 0;
            }
        },
        stats: function() {
            return {
                falling: coins.length,
                waiting: pending.length,
                inHole: pile.length,
                swallowed: totalSwallowed,
                swallowedTokens: totalTokens,
                tokens: prevTokens
            };
        }
    };
}
