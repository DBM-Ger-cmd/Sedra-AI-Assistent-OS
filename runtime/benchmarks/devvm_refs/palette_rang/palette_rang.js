function palNorm(s) {
  if (typeof s !== "string") return "";
  return s.toLowerCase().replace(/\s+/g, " ").trim();
}

function palPunkte(eingabe, text) {
  var q = palNorm(eingabe), t = palNorm(text);
  if (!q || !t) return 0;
  if (t === q) return 100;
  if (t.indexOf(q) === 0) return 80;
  var w = t.split(" ");
  for (var i = 0; i < w.length; i++) {
    if (w[i].indexOf(q) === 0) return 60;
  }
  if (t.indexOf(q) > 0) return 40;
  var qq = q.replace(/ /g, ""), k = 0;
  for (var j = 0; j < t.length && k < qq.length; j++) {
    if (t.charAt(j) === qq.charAt(k)) k++;
  }
  return qq.length > 0 && k === qq.length ? 20 : 0;
}

function palRang(eingabe, eintraege, max) {
  var m = (typeof max === "number" && isFinite(max) && max >= 1) ? Math.floor(max) : 8;
  var liste = Array.isArray(eintraege) ? eintraege.filter(function (e) {
    return e && typeof e === "object" && typeof e.id === "string" && e.id !== "" && typeof e.name === "string";
  }) : [];
  var q = palNorm(eingabe);
  if (!q) return liste.slice(0, m);
  var erg = [];
  liste.forEach(function (e, i) {
    var p = palPunkte(q, e.name);
    if (Array.isArray(e.woerter)) {
      e.woerter.forEach(function (w) { p = Math.max(p, palPunkte(q, w) - 10); });
    }
    if (p > 0) erg.push({ e: e, p: p, n: palNorm(e.name), i: i });
  });
  erg.sort(function (a, b) {
    if (b.p !== a.p) return b.p - a.p;
    if (a.n !== b.n) return a.n < b.n ? -1 : 1;
    return a.i - b.i;
  });
  return erg.slice(0, m).map(function (x) { return x.e; });
}
