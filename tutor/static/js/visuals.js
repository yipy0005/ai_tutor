/* ==========================================================================
   Visuals: turns the `visual` object on a question into a picture.

   A seven-year-old reasons far better about a clock face than about the words
   "quarter to four", so most maths questions carry one of these. Everything is
   inline SVG or plain HTML: no images, no libraries, works offline.
   ========================================================================== */

(function (global) {
  "use strict";

  var C = {
    ink: "#2b2340",
    soft: "#8d85a3",
    line: "#d9d1e6",
    berry: "#e0447a",
    ocean: "#2481cc",
    leaf: "#3d9c48",
    sun: "#ef9a1e",
    grape: "#7c4dd8",
    paper: "#ffffff",
    shade: "#f6f1fb"
  };

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function svg(width, height, body, extra) {
    return (
      '<svg viewBox="0 0 ' + width + " " + height + '" width="' + width + '" height="' + height +
      '" role="img" aria-label="' + esc((extra && extra.label) || "diagram") +
      '" xmlns="http://www.w3.org/2000/svg">' + body + "</svg>"
    );
  }

  function txt(x, y, value, opts) {
    opts = opts || {};
    return (
      '<text x="' + x + '" y="' + y + '" text-anchor="' + (opts.anchor || "middle") +
      '" font-size="' + (opts.size || 14) + '" font-weight="' + (opts.weight || 700) +
      '" fill="' + (opts.fill || C.ink) + '" font-family="inherit"' +
      (opts.transform ? ' transform="' + opts.transform + '"' : "") + ">" + esc(value) + "</text>"
    );
  }

  function polarX(cx, r, deg) { return cx + r * Math.sin((deg * Math.PI) / 180); }
  function polarY(cy, r, deg) { return cy - r * Math.cos((deg * Math.PI) / 180); }

  // -----------------------------------------------------------------------
  // Counting dots
  // -----------------------------------------------------------------------
  function dots(v) {
    var filled = Math.max(0, v.filled || 0);
    var empty = Math.max(0, v.empty || 0);
    var total = filled + empty;
    if (!total) return "";
    var perRow = v.per_row || 10;
    var rows = Math.ceil(total / perRow);
    var step = 34;
    var pad = 18;
    var w = pad * 2 + Math.min(total, perRow) * step;
    var h = pad * 2 + rows * step;
    var body = "";
    for (var i = 0; i < total; i++) {
      var col = i % perRow;
      var row = Math.floor(i / perRow);
      var cx = pad + col * step + step / 2;
      var cy = pad + row * step + step / 2;
      var isFilled = i < filled;
      body +=
        '<circle cx="' + cx + '" cy="' + cy + '" r="12" fill="' +
        (isFilled ? C.ocean : C.paper) + '" stroke="' + (isFilled ? C.ocean : C.line) +
        '" stroke-width="3"' + (isFilled ? "" : ' stroke-dasharray="4 3"') + " />";
    }
    return svg(w, h, body, { label: filled + " counters and " + empty + " empty spaces" });
  }

  // -----------------------------------------------------------------------
  // Place value blocks
  // -----------------------------------------------------------------------
  function blocks(v) {
    var hundreds = v.hundreds || 0;
    var tens = v.tens || 0;
    var ones = v.ones || 0;
    var unit = 7;
    var gap = 10;
    var body = "";
    var x = 12;
    var baseY = 12;
    var height = unit * 10;

    for (var h = 0; h < hundreds; h++) {
      body += '<rect x="' + x + '" y="' + baseY + '" width="' + unit * 10 + '" height="' + height +
        '" fill="#dff0ff" stroke="' + C.ocean + '" stroke-width="2" rx="2"/>';
      for (var g = 1; g < 10; g++) {
        body += '<line x1="' + (x + g * unit) + '" y1="' + baseY + '" x2="' + (x + g * unit) +
          '" y2="' + (baseY + height) + '" stroke="' + C.ocean + '" stroke-width="0.6" opacity="0.5"/>';
        body += '<line x1="' + x + '" y1="' + (baseY + g * unit) + '" x2="' + (x + unit * 10) +
          '" y2="' + (baseY + g * unit) + '" stroke="' + C.ocean + '" stroke-width="0.6" opacity="0.5"/>';
      }
      x += unit * 10 + gap;
    }
    if (hundreds) x += 6;

    for (var t = 0; t < tens; t++) {
      body += '<rect x="' + x + '" y="' + baseY + '" width="' + unit + '" height="' + height +
        '" fill="#e6f6ea" stroke="' + C.leaf + '" stroke-width="2" rx="2"/>';
      for (var k = 1; k < 10; k++) {
        body += '<line x1="' + x + '" y1="' + (baseY + k * unit) + '" x2="' + (x + unit) +
          '" y2="' + (baseY + k * unit) + '" stroke="' + C.leaf + '" stroke-width="0.6" opacity="0.6"/>';
      }
      x += unit + 5;
    }
    if (tens) x += 8;

    for (var o = 0; o < ones; o++) {
      var oc = o % 5;
      var orow = Math.floor(o / 5);
      body += '<rect x="' + (x + oc * (unit + 4)) + '" y="' + (baseY + orow * (unit + 4)) +
        '" width="' + unit + '" height="' + unit + '" fill="#fff2cf" stroke="' + C.sun +
        '" stroke-width="2" rx="1.5"/>';
    }
    x += Math.min(ones, 5) * (unit + 4);

    var width = Math.max(x + 14, 140);
    return svg(width, height + 30, body, {
      label: hundreds + " hundreds, " + tens + " tens and " + ones + " ones"
    });
  }

  // -----------------------------------------------------------------------
  // Analogue clock
  // -----------------------------------------------------------------------
  function clock(v, roman) {
    var hour = v.hour == null ? 12 : v.hour;
    var minute = v.minute || 0;
    var size = 210;
    var c = size / 2;
    var r = c - 12;
    var romans = ["XII", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI"];
    var body =
      '<circle cx="' + c + '" cy="' + c + '" r="' + r + '" fill="#fffdf7" stroke="' + C.ink +
      '" stroke-width="4"/>';

    for (var m = 0; m < 60; m++) {
      var deg = m * 6;
      var isHour = m % 5 === 0;
      var outer = r - 4;
      var inner = r - (isHour ? 13 : 8);
      body +=
        '<line x1="' + polarX(c, inner, deg).toFixed(1) + '" y1="' + polarY(c, inner, deg).toFixed(1) +
        '" x2="' + polarX(c, outer, deg).toFixed(1) + '" y2="' + polarY(c, outer, deg).toFixed(1) +
        '" stroke="' + (isHour ? C.ink : C.soft) + '" stroke-width="' + (isHour ? 3 : 1.4) + '"/>';
    }
    for (var n = 1; n <= 12; n++) {
      var a = n * 30;
      var lx = polarX(c, r - 30, a);
      var ly = polarY(c, r - 30, a) + 6;
      body += txt(lx.toFixed(1), ly.toFixed(1), roman ? romans[n % 12] : n, {
        size: roman ? 15 : 18, weight: 800
      });
    }

    var minuteDeg = minute * 6;
    var hourDeg = ((hour % 12) * 30) + minute * 0.5;
    body +=
      '<line x1="' + c + '" y1="' + c + '" x2="' + polarX(c, r - 58, hourDeg).toFixed(1) +
      '" y2="' + polarY(c, r - 58, hourDeg).toFixed(1) + '" stroke="' + C.berry +
      '" stroke-width="8" stroke-linecap="round"/>';
    body +=
      '<line x1="' + c + '" y1="' + c + '" x2="' + polarX(c, r - 26, minuteDeg).toFixed(1) +
      '" y2="' + polarY(c, r - 26, minuteDeg).toFixed(1) + '" stroke="' + C.ocean +
      '" stroke-width="5" stroke-linecap="round"/>';
    body += '<circle cx="' + c + '" cy="' + c + '" r="6" fill="' + C.ink + '"/>';

    return svg(size, size, body, { label: "a clock face" });
  }

  function romanClock() {
    return clock({ hour: 3, minute: 0 }, true);
  }

  // -----------------------------------------------------------------------
  // 2-D shapes
  // -----------------------------------------------------------------------
  var SIDES = {
    triangle: 3, square: 4, rectangle: 4, pentagon: 5, hexagon: 6,
    heptagon: 7, octagon: 8, rhombus: 4, trapezium: 4, parallelogram: 4
  };

  function shape2d(v) {
    var name = (v.name || "circle").toLowerCase();
    var size = 180;
    var c = size / 2;
    var r = 66;
    var rotate = v.rotate || 0;
    var fill = "#e9f2ff";
    var body = "";

    if (name === "circle") {
      body = '<circle cx="' + c + '" cy="' + c + '" r="' + r + '" fill="' + fill +
        '" stroke="' + C.ocean + '" stroke-width="4"/>';
    } else if (name === "rectangle") {
      body = '<rect x="' + (c - 78) + '" y="' + (c - 46) + '" width="156" height="92" rx="4" fill="' +
        fill + '" stroke="' + C.ocean + '" stroke-width="4"/>';
    } else if (name === "square") {
      body = '<rect x="' + (c - 58) + '" y="' + (c - 58) + '" width="116" height="116" rx="4" fill="' +
        fill + '" stroke="' + C.ocean + '" stroke-width="4"/>';
    } else if (name === "rhombus") {
      body = '<polygon points="' + c + "," + (c - 62) + " " + (c + 52) + "," + c + " " + c + "," +
        (c + 62) + " " + (c - 52) + "," + c + '" fill="' + fill + '" stroke="' + C.ocean +
        '" stroke-width="4"/>';
    } else if (name === "trapezium") {
      body = '<polygon points="' + (c - 36) + "," + (c - 46) + " " + (c + 36) + "," + (c - 46) +
        " " + (c + 74) + "," + (c + 46) + " " + (c - 74) + "," + (c + 46) + '" fill="' + fill +
        '" stroke="' + C.ocean + '" stroke-width="4"/>';
    } else if (name === "parallelogram") {
      body = '<polygon points="' + (c - 40) + "," + (c - 44) + " " + (c + 78) + "," + (c - 44) +
        " " + (c + 40) + "," + (c + 44) + " " + (c - 78) + "," + (c + 44) + '" fill="' + fill +
        '" stroke="' + C.ocean + '" stroke-width="4"/>';
    } else {
      var n = SIDES[name] || 5;
      var pts = [];
      for (var i = 0; i < n; i++) {
        var deg = (360 / n) * i + rotate;
        pts.push(polarX(c, r, deg).toFixed(1) + "," + polarY(c, r, deg).toFixed(1));
      }
      body = '<polygon points="' + pts.join(" ") + '" fill="' + fill + '" stroke="' + C.ocean +
        '" stroke-width="4"/>';
    }
    if (rotate && name !== "circle" && SIDES[name] === undefined) {
      body = '<g transform="rotate(' + rotate + " " + c + " " + c + ')">' + body + "</g>";
    }
    return svg(size, size, body, { label: "a " + name });
  }

  // -----------------------------------------------------------------------
  // Coins
  // -----------------------------------------------------------------------
  var COIN_LABEL = { 1: "1p", 2: "2p", 5: "5p", 10: "10p", 20: "20p", 50: "50p", 100: "£1", 200: "£2" };
  var COIN_STYLE = {
    1: ["#d8956b", "#a9673f"], 2: ["#d8956b", "#a9673f"], 5: ["#dcdfe4", "#9aa1ab"],
    10: ["#dcdfe4", "#9aa1ab"], 20: ["#dcdfe4", "#9aa1ab"], 50: ["#dcdfe4", "#9aa1ab"],
    100: ["#f0cf72", "#b58e26"], 200: ["#f0cf72", "#8b9099"]
  };

  function coins(v) {
    var values = v.values || [];
    if (!values.length) return "";
    var perRow = 5;
    var step = 74;
    var rows = Math.ceil(values.length / perRow);
    var w = 18 + Math.min(values.length, perRow) * step;
    var h = 18 + rows * step;
    var body = "";
    values.forEach(function (value, i) {
      var col = i % perRow;
      var row = Math.floor(i / perRow);
      var cx = 18 + col * step + 28;
      var cy = 18 + row * step + 28;
      var style = COIN_STYLE[value] || ["#dcdfe4", "#9aa1ab"];
      body += '<circle cx="' + cx + '" cy="' + cy + '" r="30" fill="' + style[0] + '" stroke="' +
        style[1] + '" stroke-width="3"/>';
      body += '<circle cx="' + cx + '" cy="' + cy + '" r="24" fill="none" stroke="' + style[1] +
        '" stroke-width="1" opacity="0.5"/>';
      body += txt(cx, cy + 6, COIN_LABEL[value] || value + "p", { size: 16, weight: 800, fill: "#3a2d16" });
    });
    return svg(w, h, body, { label: values.length + " coins" });
  }

  // -----------------------------------------------------------------------
  // Fractions
  // -----------------------------------------------------------------------
  function fraction(v) {
    var num = v.num || 0;
    var den = Math.max(1, v.den || 1);
    if ((v.shape || "circle") === "bar" || den > 8) return fractionBar(num, den, 320);
    var size = 170;
    var c = size / 2;
    var r = c - 12;
    var body = "";
    for (var i = 0; i < den; i++) {
      var a0 = (360 / den) * i - 90;
      var a1 = (360 / den) * (i + 1) - 90;
      var x0 = c + r * Math.cos((a0 * Math.PI) / 180);
      var y0 = c + r * Math.sin((a0 * Math.PI) / 180);
      var x1 = c + r * Math.cos((a1 * Math.PI) / 180);
      var y1 = c + r * Math.sin((a1 * Math.PI) / 180);
      var large = 360 / den > 180 ? 1 : 0;
      var d = den === 1
        ? "M " + (c - r) + " " + c + " a " + r + " " + r + " 0 1 0 " + 2 * r + " 0 a " + r + " " + r + " 0 1 0 " + -2 * r + " 0"
        : "M " + c + " " + c + " L " + x0.toFixed(1) + " " + y0.toFixed(1) +
          " A " + r + " " + r + " 0 " + large + " 1 " + x1.toFixed(1) + " " + y1.toFixed(1) + " Z";
      body += '<path d="' + d + '" fill="' + (i < num ? C.berry : "#fff") + '" stroke="' + C.ink +
        '" stroke-width="2.5"/>';
    }
    return svg(size, size, body, { label: num + " out of " + den + " parts shaded" });
  }

  function fractionBar(num, den, width) {
    var w = width || 300;
    var h = 62;
    var cell = (w - 8) / den;
    var body = "";
    for (var i = 0; i < den; i++) {
      body += '<rect x="' + (4 + i * cell).toFixed(1) + '" y="8" width="' + cell.toFixed(1) +
        '" height="' + (h - 16) + '" fill="' + (i < num ? C.berry : "#fff") + '" stroke="' + C.ink +
        '" stroke-width="2.5"/>';
    }
    return svg(w, h, body, { label: num + " out of " + den + " parts shaded" });
  }

  function fractionPair(v) {
    var a = v.a || [1, 2];
    var b = v.b || [1, 2];
    var w = 340;
    var body = "";
    [a, b].forEach(function (pair, row) {
      var num = pair[0];
      var den = Math.max(1, pair[1]);
      var y = 12 + row * 62;
      var barW = 240;
      var cell = barW / den;
      for (var i = 0; i < den; i++) {
        body += '<rect x="' + (78 + i * cell).toFixed(1) + '" y="' + y + '" width="' + cell.toFixed(1) +
          '" height="40" fill="' + (i < num ? (row ? C.ocean : C.berry) : "#fff") + '" stroke="' +
          C.ink + '" stroke-width="2"/>';
      }
      body += txt(38, y + 27, num + "/" + den, { size: 19, weight: 800 });
    });
    return svg(w, 136, body, { label: "two fractions compared" });
  }

  // -----------------------------------------------------------------------
  // Charts
  // -----------------------------------------------------------------------
  function barChart(v) {
    var labels = v.labels || [];
    var values = v.values || [];
    if (!labels.length) return "";
    var step = Math.max(1, v.step || 1);
    var peak = Math.max.apply(null, values.concat([step]));
    var ticks = Math.ceil(peak / step);
    var top = v.title ? 34 : 14;
    var plotH = 170;
    var axisX = 44;
    var barW = 44;
    var gap = 24;
    var w = axisX + labels.length * (barW + gap) + 18;
    var h = top + plotH + 44;
    var baseY = top + plotH;
    var body = "";

    if (v.title) body += txt(w / 2, 20, v.title, { size: 15, weight: 800 });

    for (var t = 0; t <= ticks; t++) {
      var value = t * step;
      var y = baseY - (value / (ticks * step || 1)) * plotH;
      body += '<line x1="' + axisX + '" y1="' + y.toFixed(1) + '" x2="' + (w - 10) + '" y2="' +
        y.toFixed(1) + '" stroke="' + C.line + '" stroke-width="1"/>';
      body += txt(axisX - 8, y + 5, value, { size: 12, weight: 700, anchor: "end", fill: C.soft });
    }
    body += '<line x1="' + axisX + '" y1="' + top + '" x2="' + axisX + '" y2="' + baseY +
      '" stroke="' + C.ink + '" stroke-width="2.5"/>';
    body += '<line x1="' + axisX + '" y1="' + baseY + '" x2="' + (w - 10) + '" y2="' + baseY +
      '" stroke="' + C.ink + '" stroke-width="2.5"/>';

    var palette = [C.ocean, C.berry, C.leaf, C.sun, C.grape];
    labels.forEach(function (label, i) {
      var value = values[i] || 0;
      var barH = (value / (ticks * step || 1)) * plotH;
      var x = axisX + 14 + i * (barW + gap);
      body += '<rect x="' + x + '" y="' + (baseY - barH).toFixed(1) + '" width="' + barW +
        '" height="' + barH.toFixed(1) + '" rx="4" fill="' + palette[i % palette.length] + '"/>';
      body += txt(x + barW / 2, baseY + 20, label, { size: 13, weight: 800 });
    });
    return svg(w, h, body, { label: "a bar chart" });
  }

  function pictogram(v) {
    var labels = v.labels || [];
    var values = v.values || [];
    var symbol = v.symbol || "⭐";
    var rows = labels.map(function (label, i) {
      return (
        '<tr><th scope="row">' + esc(label) + "</th><td>" +
        new Array((values[i] || 0) + 1).join(symbol + " ") +
        ' <span class="count">(' + (values[i] || 0) + ")</span></td></tr>"
      );
    }).join("");
    return (
      '<table class="pictogram">' +
      (v.title ? "<caption>" + esc(v.title) + "</caption>" : "") +
      "<tbody>" + rows + "</tbody></table>"
    );
  }

  function tally(v) {
    var labels = v.labels || [];
    var values = v.values || [];
    var rowH = 42;
    var w = 360;
    var h = (v.title ? 30 : 8) + labels.length * rowH + 10;
    var top = v.title ? 30 : 8;
    var body = v.title ? txt(w / 2, 20, v.title, { size: 15, weight: 800 }) : "";

    labels.forEach(function (label, i) {
      var y = top + i * rowH;
      body += txt(10, y + 26, label, { size: 14, weight: 800, anchor: "start" });
      var count = values[i] || 0;
      var x = 118;
      for (var n = 0; n < count; n++) {
        var groupIndex = Math.floor(n / 5);
        var inGroup = n % 5;
        var gx = x + groupIndex * 42;
        if (inGroup < 4) {
          var lx = gx + inGroup * 8;
          body += '<line x1="' + lx + '" y1="' + (y + 8) + '" x2="' + lx + '" y2="' + (y + 32) +
            '" stroke="' + C.ink + '" stroke-width="2.6"/>';
        } else {
          body += '<line x1="' + (gx - 4) + '" y1="' + (y + 32) + '" x2="' + (gx + 28) + '" y2="' +
            (y + 8) + '" stroke="' + C.berry + '" stroke-width="2.6"/>';
        }
      }
      body += '<line x1="10" y1="' + (y + 38) + '" x2="' + (w - 10) + '" y2="' + (y + 38) +
        '" stroke="' + C.line + '" stroke-width="1"/>';
    });
    return svg(w, h, body, { label: "a tally chart" });
  }

  // -----------------------------------------------------------------------
  // Arrays, number lines, rectangles
  // -----------------------------------------------------------------------
  function array(v) {
    var rows = v.rows || 2;
    var cols = v.cols || 2;
    var step = 34;
    var pad = 16;
    var w = pad * 2 + cols * step;
    var h = pad * 2 + rows * step;
    var body = "";
    for (var r = 0; r < rows; r++) {
      for (var c = 0; c < cols; c++) {
        body += '<circle cx="' + (pad + c * step + step / 2) + '" cy="' + (pad + r * step + step / 2) +
          '" r="12" fill="' + C.grape + '"/>';
      }
    }
    return svg(w, h, body, { label: rows + " rows of " + cols });
  }

  function numberLine(v) {
    var start = v.start || 0;
    var end = v.end == null ? 10 : v.end;
    var step = v.step || 1;
    var count = Math.max(1, Math.round((end - start) / step));
    var w = Math.min(620, Math.max(280, 60 + count * 62));
    var h = 76;
    var y = 42;
    var left = 26;
    var right = w - 26;
    var body = '<line x1="' + left + '" y1="' + y + '" x2="' + right + '" y2="' + y +
      '" stroke="' + C.ink + '" stroke-width="3"/>';
    for (var i = 0; i <= count; i++) {
      var value = start + i * step;
      var x = left + ((right - left) * i) / count;
      var isMark = v.mark != null && value === v.mark;
      body += '<line x1="' + x.toFixed(1) + '" y1="' + (y - 10) + '" x2="' + x.toFixed(1) + '" y2="' +
        (y + 10) + '" stroke="' + (isMark ? C.berry : C.ink) + '" stroke-width="' + (isMark ? 4 : 2) + '"/>';
      body += txt(x.toFixed(1), y + 30, value, { size: 13, weight: 800, fill: isMark ? C.berry : C.ink });
    }
    return svg(w, h, body, { label: "a number line" });
  }

  function rect(v) {
    var unit = v.unit || "cm";
    var scale = Math.min(22, Math.max(11, 160 / Math.max(v.w || 1, v.h || 1)));
    var rw = (v.w || 1) * scale;
    var rh = (v.h || 1) * scale;
    var w = rw + 110;
    var h = rh + 84;
    var x = 54;
    var y = 34;
    var body =
      '<rect x="' + x + '" y="' + y + '" width="' + rw + '" height="' + rh + '" fill="#e9f2ff" stroke="' +
      C.ocean + '" stroke-width="4" rx="3"/>';
    body += txt(x + rw / 2, y - 12, v.w + " " + unit, { size: 16, weight: 800 });
    body += txt(x + rw / 2, y + rh + 26, v.w + " " + unit, { size: 16, weight: 800, fill: C.soft });
    body += txt(x - 12, y + rh / 2 + 5, v.h + " " + unit, { size: 16, weight: 800, anchor: "end" });
    body += txt(x + rw + 12, y + rh / 2 + 5, v.h + " " + unit, {
      size: 16, weight: 800, anchor: "start", fill: C.soft
    });
    return svg(w, h, body, { label: "a rectangle " + v.w + " by " + v.h + " " + unit });
  }

  // -----------------------------------------------------------------------
  // Angles and lines
  // -----------------------------------------------------------------------
  function angle(v) {
    var deg = v.degrees == null ? 90 : v.degrees;
    var size = 190;
    var ox = 40;
    var oy = size - 40;
    var len = 122;
    var x2 = ox + len * Math.cos((deg * Math.PI) / 180);
    var y2 = oy - len * Math.sin((deg * Math.PI) / 180);
    var body =
      '<line x1="' + ox + '" y1="' + oy + '" x2="' + (ox + len) + '" y2="' + oy + '" stroke="' +
      C.ink + '" stroke-width="4" stroke-linecap="round"/>';
    body += '<line x1="' + ox + '" y1="' + oy + '" x2="' + x2.toFixed(1) + '" y2="' + y2.toFixed(1) +
      '" stroke="' + C.ink + '" stroke-width="4" stroke-linecap="round"/>';

    if (deg === 90) {
      body += '<rect x="' + ox + '" y="' + (oy - 24) + '" width="24" height="24" fill="none" stroke="' +
        C.berry + '" stroke-width="3"/>';
    } else {
      var ar = 40;
      var ax = ox + ar;
      var ay = oy;
      var bx = ox + ar * Math.cos((deg * Math.PI) / 180);
      var by = oy - ar * Math.sin((deg * Math.PI) / 180);
      var large = deg > 180 ? 1 : 0;
      body += '<path d="M ' + ax + " " + ay + " A " + ar + " " + ar + " 0 " + large + " 0 " +
        bx.toFixed(1) + " " + by.toFixed(1) + '" fill="none" stroke="' + C.berry + '" stroke-width="3"/>';
    }
    body += '<circle cx="' + ox + '" cy="' + oy + '" r="5" fill="' + C.ink + '"/>';
    return svg(size, size, body, { label: "an angle" });
  }

  function lines(v) {
    var kind = v.kind || "parallel";
    var w = 220;
    var h = 150;
    var body = "";
    var stroke = ' stroke="' + C.ocean + '" stroke-width="5" stroke-linecap="round"';
    if (kind === "horizontal") {
      body = '<line x1="24" y1="52"' + ' x2="196" y2="52"' + stroke + "/>" +
        '<line x1="24" y1="104" x2="196" y2="104"' + stroke + "/>";
    } else if (kind === "vertical") {
      body = '<line x1="78" y1="20" x2="78" y2="130"' + stroke + "/>" +
        '<line x1="142" y1="20" x2="142" y2="130"' + stroke + "/>";
    } else if (kind === "perpendicular") {
      body = '<line x1="30" y1="104" x2="190" y2="104"' + stroke + "/>" +
        '<line x1="106" y1="24" x2="106" y2="132"' + stroke + "/>" +
        '<rect x="106" y="82" width="22" height="22" fill="none" stroke="' + C.berry + '" stroke-width="3"/>';
    } else {
      body = '<line x1="26" y1="42" x2="194" y2="62"' + stroke + "/>" +
        '<line x1="26" y1="96" x2="194" y2="116"' + stroke + "/>" +
        '<polyline points="150,52 158,52" stroke="' + C.berry + '" stroke-width="3"/>' +
        '<polyline points="150,106 158,106" stroke="' + C.berry + '" stroke-width="3"/>';
    }
    return svg(w, h, body, { label: kind + " lines" });
  }

  // -----------------------------------------------------------------------
  // Column arithmetic, sharing, partitioning (HTML, not SVG)
  // -----------------------------------------------------------------------
  function column(v) {
    var a = String(v.a == null ? "" : v.a);
    var b = String(v.b == null ? "" : v.b);
    var width = Math.max(a.length, b.length) + 1;
    function cells(value) {
      var padded = new Array(width - value.length + 1).join(" ") + value;
      return padded.split("").map(function (ch) {
        return '<span class="' + (ch === " " ? "blank" : "digit") + '">' + esc(ch) + "</span>";
      }).join("");
    }
    return (
      '<div class="column-sum" aria-hidden="false">' +
      '<div class="row">' + cells(a) + "</div>" +
      '<div class="row"><span class="op">' + esc(v.op || "+") + "</span>" + cells(b) + "</div>" +
      '<div class="rule"></div>' +
      '<div class="row answer">' + cells("?") + "</div>" +
      "</div>"
    );
  }

  function share(v) {
    var total = v.total || 0;
    var groups = Math.max(1, v.groups || 1);
    var take = v.take || 0;
    var per = Math.floor(total / groups);
    var out = '<div class="share">';
    for (var g = 0; g < groups; g++) {
      out += '<div class="share-group' + (take && g < take ? " taken" : "") + '">';
      for (var i = 0; i < per; i++) out += "<i></i>";
      out += "</div>";
    }
    out += "</div>";
    return out;
  }

  function partition(v) {
    var value = v.value || 0;
    var times = v.times || 1;
    var tens = Math.floor(value / 10) * 10;
    var ones = value % 10;
    return (
      '<div class="partition">' +
      '<div class="pnode top">' + value + " × " + times + "</div>" +
      '<div class="pbranch"><span></span><span></span></div>' +
      '<div class="prow">' +
      '<div class="pnode">' + tens + " × " + times + "</div>" +
      '<div class="pnode">' + ones + " × " + times + "</div>" +
      "</div></div>"
    );
  }

  // -----------------------------------------------------------------------
  // GCSE geometry and statistics diagrams
  // -----------------------------------------------------------------------
  function paletteColor(name, fallback) {
    var colors = {
      ocean: C.ocean,
      berry: C.berry,
      leaf: C.leaf,
      sun: C.sun,
      grape: C.grape,
      ink: C.ink
    };
    return colors[name] || fallback || C.ocean;
  }

  function numberText(value) {
    var rounded = Math.round(value);
    return Math.abs(value - rounded) < 0.000001
      ? String(rounded)
      : String(Number(value.toFixed(2)));
  }

  function triangle(v) {
    var mode = v.mode || "right";
    var general = mode === "general";
    var w = 340;
    var h = 220;
    var points = general
      ? [[52, 176], [286, 176], [154, 48]]
      : [[54, 176], [276, 176], [276, 56]];
    var pointText = points.map(function (point) { return point.join(","); }).join(" ");
    var body = '<polygon points="' + pointText + '" fill="#e9f2ff" stroke="' + C.ocean +
      '" stroke-width="4" stroke-linejoin="round"/>';
    var labels = v.labels || {};

    if (!general) {
      body += '<path d="M 252 176 L 252 152 L 276 152" fill="none" stroke="' +
        C.berry + '" stroke-width="3"/>';
      if (labels.base) body += txt(165, 204, labels.base, { size: 16, weight: 800 });
      if (labels.height) {
        body += txt(304, 118, labels.height, {
          size: 16, weight: 800, transform: "rotate(-90 304 118)"
        });
      }
      if (labels.hypotenuse) body += txt(150, 105, labels.hypotenuse, { size: 16, weight: 800 });
      if (labels.angle) body += txt(84, 164, labels.angle, { size: 16, weight: 800, fill: C.berry });
    } else {
      if (labels.base) body += txt(169, 204, labels.base, { size: 16, weight: 800 });
      if (labels.left) body += txt(74, 158, labels.left, { size: 16, weight: 800, fill: C.berry });
      if (labels.right) body += txt(260, 158, labels.right, { size: 16, weight: 800, fill: C.berry });
      if (labels.top) body += txt(154, 76, labels.top, { size: 16, weight: 800, fill: C.berry });
    }
    return svg(w, h, body, {
      label: v.aria_label || (general ? "a labelled triangle" : "a labelled right-angled triangle")
    });
  }

  function coordinateGrid(v) {
    var xmin = v.x_min == null ? -5 : Number(v.x_min);
    var xmax = v.x_max == null ? 5 : Number(v.x_max);
    var ymin = v.y_min == null ? -5 : Number(v.y_min);
    var ymax = v.y_max == null ? 5 : Number(v.y_max);
    var step = v.grid_step == null ? 1 : Number(v.grid_step);
    var w = 380;
    var h = 270;
    var left = 48;
    var right = 356;
    var top = 22;
    var bottom = 218;
    var xSpan = xmax - xmin || 1;
    var ySpan = ymax - ymin || 1;
    var px = function (x) { return left + ((x - xmin) / xSpan) * (right - left); };
    var py = function (y) { return bottom - ((y - ymin) / ySpan) * (bottom - top); };
    var body = '<rect x="' + left + '" y="' + top + '" width="' + (right - left) +
      '" height="' + (bottom - top) + '" fill="#fff" stroke="' + C.line + '" stroke-width="1"/>';
    var firstX = Math.ceil(xmin / step - 0.000001);
    var lastX = Math.floor(xmax / step + 0.000001);
    var firstY = Math.ceil(ymin / step - 0.000001);
    var lastY = Math.floor(ymax / step + 0.000001);
    var i;

    for (i = firstX; i <= lastX; i++) {
      var xValue = i * step;
      var x = px(xValue);
      body += '<line x1="' + x.toFixed(1) + '" y1="' + top + '" x2="' + x.toFixed(1) +
        '" y2="' + bottom + '" stroke="' + C.line + '" stroke-width="1"/>';
      body += txt(x.toFixed(1), bottom + 18, numberText(xValue), {
        size: 11, weight: 700, fill: C.soft
      });
    }
    for (i = firstY; i <= lastY; i++) {
      var yValue = i * step;
      var y = py(yValue);
      body += '<line x1="' + left + '" y1="' + y.toFixed(1) + '" x2="' + right +
        '" y2="' + y.toFixed(1) + '" stroke="' + C.line + '" stroke-width="1"/>';
      if (Math.abs(yValue) > 0.000001) {
        body += txt(left - 8, (y + 4).toFixed(1), numberText(yValue), {
          size: 11, weight: 700, anchor: "end", fill: C.soft
        });
      }
    }
    if (xmin <= 0 && xmax >= 0) {
      var axisX = px(0);
      body += '<line x1="' + axisX.toFixed(1) + '" y1="' + top + '" x2="' + axisX.toFixed(1) +
        '" y2="' + bottom + '" stroke="' + C.ink + '" stroke-width="2.5"/>';
    }
    if (ymin <= 0 && ymax >= 0) {
      var axisY = py(0);
      body += '<line x1="' + left + '" y1="' + axisY.toFixed(1) + '" x2="' + right +
        '" y2="' + axisY.toFixed(1) + '" stroke="' + C.ink + '" stroke-width="2.5"/>';
    }
    if (v.x_label) body += txt(right, bottom + 38, v.x_label, { size: 13, weight: 800, anchor: "end" });
    if (v.y_label) body += txt(left - 28, top + 4, v.y_label, { size: 13, weight: 800, anchor: "end" });

    (v.lines || []).forEach(function (line) {
      var coords = [];
      if (typeof line.gradient === "number" && typeof line.intercept === "number") {
        coords = [[xmin, line.gradient * xmin + line.intercept], [xmax, line.gradient * xmax + line.intercept]];
      } else if (Array.isArray(line.points)) {
        coords = line.points;
      }
      if (coords.length >= 2) {
        var linePoints = coords.map(function (point) {
          return px(Number(point[0])).toFixed(1) + "," + py(Number(point[1])).toFixed(1);
        }).join(" ");
        body += '<polyline points="' + linePoints + '" fill="none" stroke="' +
          paletteColor(line.color, C.berry) + '" stroke-width="4" stroke-linecap="round"/>';
      }
    });

    (v.polygons || []).forEach(function (polygon) {
      if (!Array.isArray(polygon.points) || polygon.points.length < 3) return;
      var polygonPoints = polygon.points.map(function (point) {
        return px(Number(point[0])).toFixed(1) + "," + py(Number(point[1])).toFixed(1);
      }).join(" ");
      var dashed = polygon.style === "dashed" ? ' stroke-dasharray="7 5"' : "";
      var fill = polygon.style === "dashed" ? "#fff4fa" : "#e9f2ff";
      body += '<polygon points="' + polygonPoints + '" fill="' + fill + '" fill-opacity="0.72" stroke="' +
        paletteColor(polygon.color, C.ocean) + '" stroke-width="3"' + dashed + '/>';
      if (polygon.label) {
        var centre = polygon.points.reduce(function (sum, point) {
          return [sum[0] + Number(point[0]), sum[1] + Number(point[1])];
        }, [0, 0]);
        centre[0] /= polygon.points.length;
        centre[1] /= polygon.points.length;
        body += txt(px(centre[0]), py(centre[1]), polygon.label, { size: 13, weight: 800 });
      }
    });

    (v.points || []).forEach(function (point) {
      var cx = px(Number(point.x));
      var cy = py(Number(point.y));
      body += '<circle cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1) + '" r="6" fill="' +
        paletteColor(point.color, C.berry) + '" stroke="#fff" stroke-width="2"/>';
      if (point.label) body += txt(cx + 10, cy - 8, point.label, { size: 13, weight: 800, anchor: "start" });
    });
    return svg(w, h, body, { label: v.aria_label || "a coordinate grid" });
  }

  function scatterPlot(v) {
    var xmin = Number(v.x_min);
    var xmax = Number(v.x_max);
    var ymin = Number(v.y_min);
    var ymax = Number(v.y_max);
    var w = 390;
    var h = 270;
    var left = 52;
    var right = 362;
    var top = v.title ? 36 : 22;
    var bottom = 216;
    var xSpan = xmax - xmin || 1;
    var ySpan = ymax - ymin || 1;
    var px = function (x) { return left + ((x - xmin) / xSpan) * (right - left); };
    var py = function (y) { return bottom - ((y - ymin) / ySpan) * (bottom - top); };
    var body = v.title ? txt(w / 2, 20, v.title, { size: 15, weight: 800 }) : "";
    var t;
    for (t = 0; t <= 5; t++) {
      var xv = xmin + (xSpan * t) / 5;
      var x = px(xv);
      var yv = ymin + (ySpan * t) / 5;
      var y = py(yv);
      body += '<line x1="' + x.toFixed(1) + '" y1="' + top + '" x2="' + x.toFixed(1) +
        '" y2="' + bottom + '" stroke="' + C.line + '" stroke-width="1"/>';
      body += '<line x1="' + left + '" y1="' + y.toFixed(1) + '" x2="' + right +
        '" y2="' + y.toFixed(1) + '" stroke="' + C.line + '" stroke-width="1"/>';
      body += txt(x.toFixed(1), bottom + 18, numberText(xv), { size: 11, weight: 700, fill: C.soft });
      if (t > 0) body += txt(left - 8, (y + 4).toFixed(1), numberText(yv), {
        size: 11, weight: 700, anchor: "end", fill: C.soft
      });
    }
    body += '<line x1="' + left + '" y1="' + top + '" x2="' + left + '" y2="' + bottom +
      '" stroke="' + C.ink + '" stroke-width="2.5"/><line x1="' + left + '" y1="' + bottom +
      '" x2="' + right + '" y2="' + bottom + '" stroke="' + C.ink + '" stroke-width="2.5"/>';
    (v.points || []).forEach(function (point) {
      body += '<circle cx="' + px(Number(point[0])).toFixed(1) + '" cy="' +
        py(Number(point[1])).toFixed(1) + '" r="5.5" fill="' + C.berry + '" stroke="#fff" stroke-width="2"/>';
    });
    if (v.x_label) body += txt(right, bottom + 40, v.x_label, { size: 13, weight: 800, anchor: "end" });
    if (v.y_label) body += txt(left - 28, top + 4, v.y_label, { size: 13, weight: 800, anchor: "end" });
    return svg(w, h, body, { label: v.aria_label || "a scatter plot" });
  }

  function histogram(v) {
    var bins = v.bins || [];
    if (!bins.length) return "";
    var min = Number(bins[0].start);
    var max = Number(bins[bins.length - 1].end);
    var peak = Math.max.apply(null, bins.map(function (bin) { return Number(bin.density); }).concat([1]));
    var w = 390;
    var h = 270;
    var left = 52;
    var right = 362;
    var top = v.title ? 36 : 22;
    var bottom = 216;
    var xSpan = max - min || 1;
    var px = function (x) { return left + ((x - min) / xSpan) * (right - left); };
    var body = v.title ? txt(w / 2, 20, v.title, { size: 15, weight: 800 }) : "";
    var t;
    for (t = 0; t <= 5; t++) {
      var value = (peak * t) / 5;
      var y = bottom - (value / peak) * (bottom - top);
      body += '<line x1="' + left + '" y1="' + y.toFixed(1) + '" x2="' + right +
        '" y2="' + y.toFixed(1) + '" stroke="' + C.line + '" stroke-width="1"/>';
      if (t > 0) body += txt(left - 8, (y + 4).toFixed(1), numberText(value), {
        size: 11, weight: 700, anchor: "end", fill: C.soft
      });
    }
    body += '<line x1="' + left + '" y1="' + top + '" x2="' + left + '" y2="' + bottom +
      '" stroke="' + C.ink + '" stroke-width="2.5"/><line x1="' + left + '" y1="' + bottom +
      '" x2="' + right + '" y2="' + bottom + '" stroke="' + C.ink + '" stroke-width="2.5"/>';
    bins.forEach(function (bin) {
      var x1 = px(Number(bin.start));
      var x2 = px(Number(bin.end));
      var height = (Number(bin.density) / peak) * (bottom - top);
      body += '<rect x="' + x1.toFixed(1) + '" y="' + (bottom - height).toFixed(1) +
        '" width="' + Math.max(1, x2 - x1).toFixed(1) + '" height="' + height.toFixed(1) +
        '" fill="#e9f2ff" stroke="' + C.ocean + '" stroke-width="2"/>';
      body += txt((x1 + x2) / 2, bottom + 18,
        numberText(Number(bin.start)) + "–" + numberText(Number(bin.end)), {
          size: 11, weight: 700, fill: C.soft
        });
    });
    if (v.x_label) body += txt(right, bottom + 40, v.x_label, { size: 13, weight: 800, anchor: "end" });
    if (v.y_label) body += txt(left - 28, top + 4, v.y_label, { size: 13, weight: 800, anchor: "end" });
    return svg(w, h, body, { label: v.aria_label || "a histogram" });
  }

  function boxPlot(v) {
    var min = Number(v.min);
    var q1 = Number(v.q1);
    var median = Number(v.median);
    var q3 = Number(v.q3);
    var max = Number(v.max);
    var axisMin = v.axis_min == null ? min : Number(v.axis_min);
    var axisMax = v.axis_max == null ? max : Number(v.axis_max);
    var w = 390;
    var h = v.title ? 180 : 155;
    var left = 42;
    var right = 358;
    var axisY = v.title ? 105 : 82;
    var xSpan = axisMax - axisMin || 1;
    var px = function (value) { return left + ((value - axisMin) / xSpan) * (right - left); };
    var body = v.title ? txt(w / 2, 20, v.title, { size: 15, weight: 800 }) : "";
    var t;
    for (t = 0; t <= 5; t++) {
      var value = axisMin + (xSpan * t) / 5;
      var x = px(value);
      body += '<line x1="' + x.toFixed(1) + '" y1="' + (axisY - 18) + '" x2="' +
        x.toFixed(1) + '" y2="' + (axisY + 18) + '" stroke="' + C.line + '" stroke-width="1"/>';
      body += txt(x.toFixed(1), axisY + 42, numberText(value), { size: 11, weight: 700, fill: C.soft });
    }
    body += '<line x1="' + left + '" y1="' + axisY + '" x2="' + right + '" y2="' + axisY +
      '" stroke="' + C.ink + '" stroke-width="2.5"/>';
    body += '<line x1="' + px(min).toFixed(1) + '" y1="' + axisY + '" x2="' + px(max).toFixed(1) +
      '" y2="' + axisY + '" stroke="' + C.berry + '" stroke-width="4"/>';
    body += '<line x1="' + px(min).toFixed(1) + '" y1="' + (axisY - 15) + '" x2="' + px(min).toFixed(1) +
      '" y2="' + (axisY + 15) + '" stroke="' + C.berry + '" stroke-width="3"/>';
    body += '<line x1="' + px(max).toFixed(1) + '" y1="' + (axisY - 15) + '" x2="' + px(max).toFixed(1) +
      '" y2="' + (axisY + 15) + '" stroke="' + C.berry + '" stroke-width="3"/>';
    body += '<rect x="' + px(q1).toFixed(1) + '" y="' + (axisY - 25) + '" width="' +
      Math.max(1, px(q3) - px(q1)).toFixed(1) + '" height="50" fill="#e9f2ff" stroke="' +
      C.ocean + '" stroke-width="3"/>';
    body += '<line x1="' + px(median).toFixed(1) + '" y1="' + (axisY - 25) + '" x2="' +
      px(median).toFixed(1) + '" y2="' + (axisY + 25) + '" stroke="' + C.grape + '" stroke-width="4"/>';
    if (v.label) body += txt(w / 2, axisY - 38, v.label, { size: 13, weight: 800 });
    return svg(w, h, body, { label: v.aria_label || "a box plot" });
  }

  function renderInteractive(visual) {
    if (!visual || visual.type !== "coordinate_grid") return "";
    var markup = coordinateGrid(visual);
    var attrs =
      'class="interactive-grid" data-interactive-grid="true" tabindex="0" ' +
      'aria-describedby="interactive-instructions" ' +
      'data-x-min="' + esc(visual.x_min) + '" data-x-max="' + esc(visual.x_max) +
      '" data-y-min="' + esc(visual.y_min) + '" data-y-max="' + esc(visual.y_max) +
      '" data-plot-left="48" data-plot-right="356" data-plot-top="22" data-plot-bottom="218"';
    return markup.replace("<svg ", "<svg " + attrs + " ");
  }

  // -----------------------------------------------------------------------
  // Dispatch
  // -----------------------------------------------------------------------
  var RENDERERS = {
    dots: dots,
    blocks: blocks,
    clock: function (v) { return clock(v, false); },
    roman_clock: romanClock,
    shape2d: shape2d,
    coins: coins,
    fraction: fraction,
    fraction_pair: fractionPair,
    bar_chart: barChart,
    pictogram: pictogram,
    tally: tally,
    array: array,
    number_line: numberLine,
    rect: rect,
    angle: angle,
    lines: lines,
    triangle: triangle,
    coordinate_grid: coordinateGrid,
    scatter_plot: scatterPlot,
    histogram: histogram,
    box_plot: boxPlot,
    column: column,
    share: share,
    partition: partition
  };

  function render(visual) {
    if (!visual || !visual.type) return "";
    var fn = RENDERERS[visual.type];
    if (!fn) return "";
    try {
      return fn(visual) || "";
    } catch (err) {
      if (global.console) console.warn("visual failed", visual.type, err);
      return "";
    }
  }

  global.Visuals = { render: render, renderInteractive: renderInteractive };
})(window);
