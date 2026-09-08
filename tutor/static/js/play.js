/* ==========================================================================
   The quest player.

   Design decisions that matter for a seven-year-old:
   * One question on screen at a time, with the progress dots always visible so
     the finish line is never a mystery.
   * A correct answer advances itself after a beat. A wrong answer waits, so
     there is time to read why.
   * Wrong answers are soft: gentle sound, gentle colour, an explanation, and
     no score to lose.
   * A "wiggle break" is offered on a timer rather than enforced.
   ========================================================================== */

(function (global) {
  "use strict";

  var App = global.App;
  var Visuals = global.Visuals;
  var data = global.QUEST_DATA;
  if (!data) return;

  var opts = data.options || {};
  App.Sound.set(!!opts.sound);

  var el = {
    dots: document.getElementById("dots"),
    stage: document.getElementById("stage"),
    timer: document.getElementById("timer"),
    counter: document.getElementById("counter")
  };

  var state = {
    index: 0,
    questionStartedAt: Date.now(),
    quizStartedAt: Date.now(),
    hintShown: false,
    locked: false,
    finished: false,
    breakOffered: false,
    outOfTime: false,
    lastPassage: null
  };

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------
  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function current() { return data.questions[state.index]; }

  function returnPath() { return data.return_to || "/home"; }

  function firstUnanswered() {
    for (var i = 0; i < data.questions.length; i++) {
      if (!data.questions[i].answered) return i;
    }
    return data.questions.length;
  }

  function paintDots() {
    if (!el.dots) return;
    el.dots.innerHTML = data.questions
      .map(function (question, i) {
        var cls = "";
        if (question.result === true) cls = "on";
        else if (question.result === false) cls = "off";
        else if (question.pending) cls = "pending";
        else if (i === state.index) cls = "now";
        return '<i class="' + cls + '"></i>';
      })
      .join("");
    if (el.counter) {
      el.counter.textContent =
        Math.min(state.index + 1, data.questions.length) + " of " + data.questions.length;
    }
  }

  /** Draw a piece of artwork from the sprite already on the page.
   *
   * The wrapper needs the same viewBox as the symbol, which is read straight
   * off the sprite rather than hard-coded, so JS and templates cannot drift.
   */
  function art(name, classes) {
    var symbol = document.getElementById(name);
    var box = (symbol && symbol.getAttribute("viewBox")) || "0 0 120 120";
    return (
      '<svg class="art ' + (classes || "") + '" viewBox="' + box + '"' +
      ' aria-hidden="true" focusable="false"><use href="#' + name + '"/></svg>'
    );
  }

  function keypadFor(kind) {
    var extras = { money: [".", "£"], fraction: ["/"], time: [":"], number: [] };
    var rows = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"];
    var keys = rows.concat(extras[kind] || []);
    var buttons = keys
      .map(function (key) {
        return '<button type="button" class="kp" data-key="' + esc(key) + '">' + esc(key) + "</button>";
      })
      .join("");
    buttons += '<button type="button" class="kp del" data-key="del" aria-label="Delete">⌫</button>';
    return '<div class="keypad">' + buttons + "</div>";
  }

  var richState = {
    strokes: [],
    activeStroke: null,
    recorder: null,
    stream: null,
    audioChunks: [],
    audioData: null,
    audioMime: "",
    audioStartedAt: 0,
    audioDurationMs: 0,
    audioTimer: null
  };

  var interactiveState = { points: [] };

  function resetInteractiveState() {
    interactiveState = { points: [] };
  }

  function isInteractiveKind(kind) {
    return kind === "coordinate_points" || kind === "transformation_polygon";
  }

  function resetRichState() {
    if (richState.recorder && richState.recorder.state !== "inactive") richState.recorder.stop();
    if (richState.stream) richState.stream.getTracks().forEach(function (track) { track.stop(); });
    if (richState.audioTimer) clearInterval(richState.audioTimer);
    richState = {
      strokes: [], activeStroke: null, recorder: null, stream: null,
      audioChunks: [], audioData: null, audioMime: "", audioStartedAt: 0,
      audioDurationMs: 0, audioTimer: null
    };
  }

  function richTextMarkup(question) {
    var spec = question.response_spec || {};
    return (
      '<div class="rich-response rich-text-response">' +
      '<label class="rich-label" for="response-text">' + esc(spec.label || "Your response") + '</label>' +
      (spec.helper ? '<p class="rich-helper">' + esc(spec.helper) + '</p>' : '') +
      '<textarea id="response-text" class="rich-textarea" rows="' + esc(spec.rows || 6) + '" ' +
      'maxlength="' + esc(spec.max_chars || 2400) + '" spellcheck="' + (spec.spellcheck === false ? "false" : "true") + '" ' +
      'aria-describedby="response-helper" placeholder="Write in your own words"></textarea>' +
      '<p class="rich-count" id="response-helper" aria-live="polite">0 / ' + esc(spec.max_chars || 2400) + ' characters</p>' +
      '<button type="button" class="btn leaf rich-submit" id="check">Submit writing</button>' +
      '</div>'
    );
  }

  function evidenceMarkup(question) {
    var spec = question.response_spec || {};
    var fields = (spec.fields || []).map(function (field) {
      return (
        '<div class="rich-field">' +
        '<label for="evidence-' + esc(field.id) + '"><b>' + esc(field.label) + '</b>' +
        '<span>' + esc(field.prompt) + '</span></label>' +
        '<textarea id="evidence-' + esc(field.id) + '" data-evidence-field="' + esc(field.id) + '" rows="3" maxlength="' +
        esc(field.max_chars || 800) + '" ' + (field.required ? 'aria-required="true"' : '') + '></textarea>' +
        '</div>'
      );
    }).join("");
    return (
      '<div class="rich-response evidence-response">' +
      '<p class="rich-helper">' + esc(spec.helper || "Record what you did and what the evidence shows.") + '</p>' +
      fields +
      '<button type="button" class="btn leaf rich-submit" id="check">Submit investigation</button>' +
      '</div>'
    );
  }

  function handwritingMarkup(question) {
    var spec = question.response_spec || {};
    return (
      '<div class="rich-response handwriting-response">' +
      '<p class="rich-helper">' + esc(spec.canvas_label || "Draw your handwriting here") + '</p>' +
      '<div class="copy-target" aria-label="Sentence to copy">' + esc(spec.copy_text || "") + '</div>' +
      '<canvas id="handwriting-canvas" width="900" height="360" aria-label="Handwriting drawing pad"></canvas>' +
      '<div class="rich-actions">' +
      '<button type="button" class="tool" id="clear-drawing">Clear drawing</button>' +
      '<label class="rich-fallback" for="handwriting-text">' + esc(spec.fallback_label || "Or type your answer") +
      '<textarea id="handwriting-text" rows="2" maxlength="' + esc(spec.fallback_max_chars || 500) + '"></textarea></label>' +
      '</div>' +
      '<button type="button" class="btn leaf rich-submit" id="check">Submit handwriting</button>' +
      '</div>'
    );
  }

  function audioMarkup(question) {
    var spec = question.response_spec || {};
    return (
      '<div class="rich-response audio-response">' +
      '<p class="rich-helper">' + esc(spec.helper || "Record a short answer, or type what you would say.") + '</p>' +
      '<div class="record-controls">' +
      '<button type="button" class="btn grape" id="record-audio">Start recording</button>' +
      '<button type="button" class="tool hidden" id="stop-audio">Stop recording</button>' +
      '<span class="record-status" id="record-status" role="status" aria-live="polite">No recording yet</span>' +
      '</div>' +
      '<label class="rich-label" for="audio-transcript">Typed fallback (optional)</label>' +
      '<textarea id="audio-transcript" rows="3" maxlength="' + esc(spec.transcript_max_chars || 1200) + '" placeholder="Type what you would say if recording is not available"></textarea>' +
      '<button type="button" class="btn leaf rich-submit" id="check">Submit speaking answer</button>' +
      '</div>'
    );
  }

  function interactiveStatus(message, error) {
    var node = document.getElementById("interactive-status");
    if (!node) return;
    node.textContent = message;
    node.classList.toggle("error", !!error);
  }

  function interactiveSvg() {
    return el.stage && el.stage.querySelector("[data-interactive-grid]");
  }

  function interactiveMetrics(question, svg) {
    var visual = question.visual || {};
    return {
      xmin: Number(visual.x_min), xmax: Number(visual.x_max),
      ymin: Number(visual.y_min), ymax: Number(visual.y_max),
      left: Number(svg.getAttribute("data-plot-left") || 48),
      right: Number(svg.getAttribute("data-plot-right") || 356),
      top: Number(svg.getAttribute("data-plot-top") || 22),
      bottom: Number(svg.getAttribute("data-plot-bottom") || 218)
    };
  }

  function gridToSvgPoint(question, svg, point) {
    var metrics = interactiveMetrics(question, svg);
    return [
      metrics.left + ((point[0] - metrics.xmin) / (metrics.xmax - metrics.xmin)) * (metrics.right - metrics.left),
      metrics.bottom - ((point[1] - metrics.ymin) / (metrics.ymax - metrics.ymin)) * (metrics.bottom - metrics.top)
    ];
  }

  function eventToGridPoint(question, svg, event) {
    var rect = svg.getBoundingClientRect();
    if (!rect.width || !rect.height) return null;
    var viewBox = (svg.getAttribute("viewBox") || "0 0 380 270").split(/\s+/).map(Number);
    var svgX = viewBox[0] + ((event.clientX - rect.left) / rect.width) * viewBox[2];
    var svgY = viewBox[1] + ((event.clientY - rect.top) / rect.height) * viewBox[3];
    var metrics = interactiveMetrics(question, svg);
    var x = metrics.xmin + ((svgX - metrics.left) / (metrics.right - metrics.left)) * (metrics.xmax - metrics.xmin);
    var y = metrics.ymin + ((metrics.bottom - svgY) / (metrics.bottom - metrics.top)) * (metrics.ymax - metrics.ymin);
    var snap = Number((question.response_spec || {}).snap || (question.visual || {}).grid_step || 1);
    x = Math.round(x / snap) * snap;
    y = Math.round(y / snap) * snap;
    x = Math.abs(x) < 0.00005 ? 0 : Number(x.toFixed(4));
    y = Math.abs(y) < 0.00005 ? 0 : Number(y.toFixed(4));
    if (!isFinite(x) || !isFinite(y) || x < metrics.xmin || x > metrics.xmax || y < metrics.ymin || y > metrics.ymax) return null;
    return [x, y];
  }

  function renderInteractiveSelection(question) {
    var svg = interactiveSvg();
    if (!svg) return;
    var old = svg.querySelector("[data-user-overlay]");
    if (old) old.parentNode.removeChild(old);
    var ns = "http://www.w3.org/2000/svg";
    var group = document.createElementNS(ns, "g");
    group.setAttribute("data-user-overlay", "true");
    group.setAttribute("aria-label", "Your plotted response");
    var points = interactiveState.points;
    var mapped = points.map(function (point) { return gridToSvgPoint(question, svg, point); });
    if (question.kind === "transformation_polygon" && mapped.length >= 2) {
      var line = document.createElementNS(ns, mapped.length >= 3 ? "polygon" : "polyline");
      line.setAttribute("points", mapped.map(function (point) { return point[0].toFixed(1) + "," + point[1].toFixed(1); }).join(" "));
      line.setAttribute("fill", mapped.length >= 3 ? "#e7f8ec" : "none");
      line.setAttribute("fill-opacity", "0.82");
      line.setAttribute("stroke", "#3aa657");
      line.setAttribute("stroke-width", "4");
      line.setAttribute("stroke-linejoin", "round");
      group.appendChild(line);
    }
    mapped.forEach(function (point, index) {
      var circle = document.createElementNS(ns, "circle");
      circle.setAttribute("cx", point[0].toFixed(1));
      circle.setAttribute("cy", point[1].toFixed(1));
      circle.setAttribute("r", "8");
      circle.setAttribute("fill", "#45b35a");
      circle.setAttribute("stroke", "#ffffff");
      circle.setAttribute("stroke-width", "3");
      group.appendChild(circle);
      var label = document.createElementNS(ns, "text");
      label.setAttribute("x", (point[0] + 12).toFixed(1));
      label.setAttribute("y", (point[1] - 10).toFixed(1));
      label.setAttribute("font-size", "13");
      label.setAttribute("font-weight", "800");
      label.setAttribute("fill", "#3b2c4f");
      label.textContent = question.kind === "coordinate_points" ? "P" : String.fromCharCode(65 + index) + "′";
      group.appendChild(label);
    });
    svg.appendChild(group);
  }

  function setInteractivePoints(question, points) {
    interactiveState.points = points.map(function (point) { return [Number(point[0]), Number(point[1])]; });
    var pointFields = document.getElementById("interactive-x");
    var yField = document.getElementById("interactive-y");
    var vertices = document.getElementById("interactive-vertices");
    if (question.kind === "coordinate_points" && pointFields && yField) {
      pointFields.value = interactiveState.points[0] ? interactiveState.points[0][0] : "";
      yField.value = interactiveState.points[0] ? interactiveState.points[0][1] : "";
    }
    if (question.kind === "transformation_polygon" && vertices) {
      vertices.value = interactiveState.points.map(function (point) { return point[0] + ", " + point[1]; }).join("; ");
    }
    renderInteractiveSelection(question);
  }

  function parseInteractivePoint(text) {
    var parts = String(text || "").trim().split(/\s*,\s*|\s+/);
    if (parts.length !== 2 || parts.some(function (part) { return part === "" || !isFinite(Number(part)); })) return null;
    return [Number(parts[0]), Number(parts[1])];
  }

  function applyInteractiveFields(question) {
    var points = [];
    if (question.kind === "coordinate_points") {
      var x = document.getElementById("interactive-x");
      var y = document.getElementById("interactive-y");
      var point = parseInteractivePoint((x ? x.value : "") + "," + (y ? y.value : ""));
      if (point) points = [point];
    } else {
      var vertices = document.getElementById("interactive-vertices");
      String(vertices ? vertices.value : "").split(/[;\n]+/).forEach(function (item) {
        if (item.trim()) {
          var point = parseInteractivePoint(item);
          if (point) points.push(point);
        }
      });
    }
    var spec = question.response_spec || {};
    if (points.length < Number(spec.min_points || 1) || points.length > Number(spec.max_points || 12)) {
      interactiveStatus(question.kind === "coordinate_points" ? "Enter one x and y coordinate." : "Enter three different vertices.", true);
      return false;
    }
    var visual = question.visual || {};
    var valid = points.every(function (point) {
      return point[0] >= Number(visual.x_min) && point[0] <= Number(visual.x_max) &&
        point[1] >= Number(visual.y_min) && point[1] <= Number(visual.y_max) &&
        Math.abs(point[0] / Number(spec.snap) - Math.round(point[0] / Number(spec.snap))) < 0.00001 &&
        Math.abs(point[1] / Number(spec.snap) - Math.round(point[1] / Number(spec.snap))) < 0.00001;
    });
    var duplicate = points.some(function (point, index) {
      return points.slice(0, index).some(function (other) {
        return point[0] === other[0] && point[1] === other[1];
      });
    });
    if (!valid || (question.kind === "transformation_polygon" && duplicate)) {
      interactiveStatus("Use different grid intersections inside the grid.", true);
      return false;
    }
    setInteractivePoints(question, points);
    interactiveStatus("Coordinates added. Check your answer when ready.", false);
    return true;
  }

  function interactiveResponse(question) {
    var spec = question.response_spec || {};
    if (interactiveState.points.length < Number(spec.min_points || 1) || interactiveState.points.length > Number(spec.max_points || 12)) return null;
    return { type: question.kind, points: interactiveState.points.map(function (point) { return [point[0], point[1]]; }) };
  }

  function placeInteractiveFromEvent(question, event) {
    var svg = event.target.closest("[data-interactive-grid]");
    if (!svg || state.locked) return;
    var point = eventToGridPoint(question, svg, event);
    if (!point) {
      interactiveStatus("Choose a grid intersection inside the axes.", true);
      return;
    }
    if (question.kind === "coordinate_points") {
      setInteractivePoints(question, [point]);
    } else {
      var max = Number((question.response_spec || {}).max_points || 3);
      if (interactiveState.points.length >= max) {
        interactiveStatus("All vertices are placed. Clear them to start again.", true);
        return;
      }
      setInteractivePoints(question, interactiveState.points.concat([point]));
    }
    interactiveStatus("Point placed. You can also enter coordinates below.", false);
  }

  function interactiveMarkup(question) {
    var spec = question.response_spec || {};
    var isPoint = question.kind === "coordinate_points";
    var fields = isPoint
      ? '<div class="interactive-fields"><label for="interactive-x">x coordinate<input id="interactive-x" inputmode="decimal" autocomplete="off" aria-label="x coordinate"></label>' +
        '<label for="interactive-y">y coordinate<input id="interactive-y" inputmode="decimal" autocomplete="off" aria-label="y coordinate"></label>' +
        '<button type="button" class="tool" id="apply-interactive">Place coordinates</button></div>'
      : '<label class="interactive-vertices-label" for="interactive-vertices">Vertex coordinates</label>' +
        '<textarea id="interactive-vertices" rows="2" inputmode="text" placeholder="1, 1; 3, 1; 2, 3" aria-label="Vertex coordinates"></textarea>' +
        '<button type="button" class="tool" id="apply-interactive">Use these vertices</button>';
    return '<div class="interactive-response" id="interactive-response">' +
      '<p class="rich-helper" id="interactive-instructions">' + esc(spec.helper || "Tap a grid intersection to plot your answer.") + '</p>' +
      '<p class="interactive-status" id="interactive-status" role="status" aria-live="polite">' + esc(spec.label || "Your plotted answer") + '</p>' +
      fields +
      '<div class="interactive-actions"><button type="button" class="tool" id="clear-interactive">Clear plotted answer</button></div>' +
      '<button type="button" class="btn leaf rich-submit" id="check">Check diagram</button>' +
      '</div>';
  }

  function setInteractiveLocked(locked) {
    var grid = interactiveSvg();
    if (grid) grid.classList.toggle("locked", !!locked);
    Array.prototype.forEach.call(el.stage.querySelectorAll("#interactive-response button, #interactive-response input, #interactive-response textarea"), function (control) {
      control.disabled = !!locked;
      if (locked && (control.tagName === "INPUT" || control.tagName === "TEXTAREA")) control.readOnly = true;
    });
  }

  function richMarkup(question) {
    if (question.kind === "free_text") return richTextMarkup(question);
    if (question.kind === "handwriting") return handwritingMarkup(question);
    if (question.kind === "audio") return audioMarkup(question);
    if (question.kind === "evidence") return evidenceMarkup(question);
    return "";
  }

  function richResponse(question) {
    if (question.kind === "free_text") {
      var text = document.getElementById("response-text");
      return text && text.value.trim() ? { text: text.value } : null;
    }
    if (question.kind === "handwriting") {
      var handwriting = document.getElementById("handwriting-text");
      if (!richState.strokes.length && (!handwriting || !handwriting.value.trim())) return null;
      return { strokes: richState.strokes, text: handwriting ? handwriting.value : "" };
    }
    if (question.kind === "audio") {
      var transcript = document.getElementById("audio-transcript");
      if (!richState.audioData && (!transcript || !transcript.value.trim())) return null;
      return {
        audio: richState.audioData,
        transcript: transcript ? transcript.value : "",
        duration_ms: richState.audioDurationMs
      };
    }
    if (question.kind === "evidence") {
      var fields = {};
      Array.prototype.forEach.call(document.querySelectorAll("[data-evidence-field]"), function (field) {
        fields[field.dataset.evidenceField] = field.value;
      });
      return { fields: fields };
    }
    return null;
  }

  function richStatus(message, error) {
    var node = document.getElementById("record-status") || document.getElementById("response-helper");
    if (!node) return;
    node.textContent = message;
    if (error) node.classList.add("error");
  }

  function canvasPoint(canvas, event) {
    var rect = canvas.getBoundingClientRect();
    return [
      Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
      Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height))
    ];
  }

  function drawCanvasSegment(canvas, from, to) {
    var context = canvas.getContext("2d");
    if (!context) return;
    context.strokeStyle = "#3b2c4f";
    context.lineWidth = 5;
    context.lineCap = "round";
    context.beginPath();
    context.moveTo(from[0] * canvas.width, from[1] * canvas.height);
    context.lineTo(to[0] * canvas.width, to[1] * canvas.height);
    context.stroke();
  }

  function clearDrawing() {
    var canvas = document.getElementById("handwriting-canvas");
    if (!canvas) return;
    var context = canvas.getContext("2d");
    if (context) context.clearRect(0, 0, canvas.width, canvas.height);
    richState.strokes = [];
    richState.activeStroke = null;
  }

  function startAudio() {
    var question = current();
    var spec = question && question.response_spec || {};
    if (!global.navigator.mediaDevices || !global.navigator.mediaDevices.getUserMedia || !global.MediaRecorder) {
      richStatus("Recording is not available here. Use the typed fallback instead.", true);
      var fallback = document.getElementById("audio-transcript");
      if (fallback) fallback.focus();
      return;
    }
    global.navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      var mime = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg"].filter(function (candidate) {
        return !global.MediaRecorder.isTypeSupported || global.MediaRecorder.isTypeSupported(candidate);
      })[0] || "";
      var recorder = mime ? new global.MediaRecorder(stream, { mimeType: mime }) : new global.MediaRecorder(stream);
      richState.recorder = recorder;
      richState.stream = stream;
      richState.audioChunks = [];
      richState.audioStartedAt = Date.now();
      recorder.ondataavailable = function (event) { if (event.data && event.data.size) richState.audioChunks.push(event.data); };
      recorder.onstop = function () {
        var blob = new Blob(richState.audioChunks, { type: recorder.mimeType || "audio/webm" });
        var reader = new FileReader();
        reader.onloadend = function () {
          richState.audioData = reader.result;
          richState.audioMime = blob.type;
          richState.audioDurationMs = Math.max(1, Date.now() - richState.audioStartedAt);
          richStatus("Recording ready. Listen or submit it when you are happy.", false);
          var record = document.getElementById("record-audio");
          var stop = document.getElementById("stop-audio");
          if (record) { record.classList.remove("hidden"); record.textContent = "Record again"; }
          if (stop) stop.classList.add("hidden");
        };
        reader.readAsDataURL(blob);
      };
      recorder.start();
      var record = document.getElementById("record-audio");
      var stop = document.getElementById("stop-audio");
      if (record) record.classList.add("hidden");
      if (stop) stop.classList.remove("hidden");
      richStatus("Recording… speak clearly, then stop when you finish.", false);
      richState.audioTimer = setInterval(function () {
        var seconds = Math.round((Date.now() - richState.audioStartedAt) / 1000);
        richStatus("Recording… " + seconds + " seconds", false);
        if (seconds >= (spec.max_seconds || 60)) stopAudio();
      }, 500);
    }).catch(function () {
      richStatus("Microphone access was not given. Use the typed fallback instead.", true);
      var fallback = document.getElementById("audio-transcript");
      if (fallback) fallback.focus();
    });
  }

  function stopAudio() {
    if (richState.audioTimer) clearInterval(richState.audioTimer);
    richState.audioTimer = null;
    if (richState.recorder && richState.recorder.state !== "inactive") richState.recorder.stop();
    if (richState.stream) richState.stream.getTracks().forEach(function (track) { track.stop(); });
  }

  // -----------------------------------------------------------------------
  // Rendering a question
  // -----------------------------------------------------------------------
  function phonicsMarkup(question) {
    var type = question.phonics_type || "";
    var body = "";
    if (type === "gpc") {
      body = '<div class="phonics-sound" aria-label="Target sound">' +
        '<span class="phonics-symbol">' + esc(question.phoneme || "") + '</span>' +
        '<span class="phonics-helper">Find the letter or letters that make this sound.</span></div>';
    } else if (type === "blend") {
      var blendTiles = (question.graphemes || []).map(function (grapheme) {
        return '<span class="phonics-tile">' + esc(grapheme) + '</span>';
      }).join('<span class="phonics-dot" aria-hidden="true">·</span>');
      body = '<div class="phonics-strip" aria-label="Sounds to blend">' + blendTiles + '</div>' +
        '<span class="phonics-helper">Say each sound, then push them together.</span>';
    } else if (type === "segment") {
      body = '<div class="phonics-word" aria-label="Word to segment">' + esc(question.phonics_word || "") + '</div>' +
        '<span class="phonics-helper">Type the graphemes in order, with a dash between each sound.</span>';
    } else if (type === "decodable") {
      body = '<div class="decodable-text"><span class="phonics-helper">Read this sentence:</span><p>' +
        esc(question.decodable_text || "") + '</p></div>';
    } else if (type === "tricky") {
      body = '<div class="phonics-word" aria-label="Common exception word">Look carefully</div>' +
        '<span class="phonics-helper">Some words have a part that does not follow the usual sound pattern.</span>';
    }
    if (!body) return "";
    var spoken = question.speak_text || question.sound_text || "";
    var hear = spoken
      ? '<button type="button" class="tool phonics-hear" id="phonics-sound">' +
        '🔊 Hear it</button>'
      : "";
    return '<div class="phonics-panel phonics-' + esc(type) + '">' + body + hear + '</div>';
  }

  function renderQuestion() {
    var question = current();
    if (!question) { finish(); return; }

    state.questionStartedAt = Date.now();
    state.hintShown = false;
    state.locked = false;
    resetRichState();
    resetInteractiveState();
    paintDots();

    var label = question.year_label || (question.year ? "Year " + question.year : "");
    var pillClass = question.pathway ? "gcse" : (question.year ? "y" + question.year : "");
    var yearPill = label ? '<span class="pill ' + pillClass + '">' + esc(label) + "</span>" : "";
    var parts = [];

    parts.push('<div class="qcard enter">');
    parts.push(
      '<div class="qtag">' +
      (question.subject ? art("icon-" + question.subject) : "") +
      yearPill +
      "<span>" + esc(question.skill_name || "") + "</span></div>"
    );

    if (question.passage_text) {
      var paragraphs = String(question.passage_text)
        .split(/\n\s*\n/)
        .map(function (block) { return "<p>" + esc(block).replace(/\n/g, "<br>") + "</p>"; })
        .join("");
      parts.push(
        '<div class="passage" id="passage"><h4>' + art("icon-english") +
        "<span>" + esc(question.passage_title || "Read this") + "</span></h4>" +
        paragraphs + "</div>"
      );
    }

    parts.push('<h1 class="qprompt" id="prompt">' + esc(question.prompt) + "</h1>");
    if (question.prompt_sub) {
      parts.push('<div class="qsub">' + esc(question.prompt_sub) + "</div>");
    }
    if (question.phonics_type) parts.push(phonicsMarkup(question));

    if (question.visual) {
      var markup = isInteractiveKind(question.kind) && Visuals.renderInteractive
        ? Visuals.renderInteractive(question.visual, question.response_spec || {})
        : Visuals.render(question.visual);
      if (markup) parts.push('<div class="visual' + (isInteractiveKind(question.kind) ? " interactive-visual" : "") + '">' + markup + "</div>");
      if (isInteractiveKind(question.kind)) parts.push(interactiveMarkup(question));
    }

    if (question.kind === "choice") {
      var letters = ["A", "B", "C", "D", "E", "F"];
      var long = (question.choices || []).some(function (choice) { return String(choice).length > 22; });
      parts.push('<div class="choices' + (long ? "" : " pairs") + '" id="choices">');
      (question.choices || []).forEach(function (choice, i) {
        parts.push(
          '<button type="button" class="choice" data-value="' + esc(choice) + '">' +
          '<span class="key">' + letters[i] + "</span>" +
          "<span>" + esc(choice) + "</span>" +
          '<span class="mark">' + art("scene-tick") + "</span></button>"
        );
      });
      parts.push("</div>");
    } else if (["free_text", "handwriting", "audio", "evidence"].indexOf(question.kind) >= 0) {
      parts.push(richMarkup(question));
    } else if (isInteractiveKind(question.kind)) {
      // The diagram response controls were rendered beside the visual above.
    } else {
      var keypad = question.keypad || "number";
      parts.push('<div class="answer-row">');
      parts.push(
        '<input class="answer-input" id="typed" type="text" inputmode="' +
        (keypad === "text" ? "text" : "text") +
        '" autocomplete="off" autocapitalize="off" spellcheck="false" ' +
        'aria-label="Your answer" placeholder="?">'
      );
      parts.push('<button type="button" class="btn leaf" id="check">Check</button>');
      parts.push("</div>");
      if (keypad !== "text") parts.push(keypadFor(keypad));
    }

    parts.push('<div class="tools">');
    if (opts.read_aloud) {
      parts.push(
        '<button type="button" class="tool" id="say">' + art("scene-speaker") +
        "Read it to me</button>"
      );
    }
    if (opts.allow_hints && question.hint) {
      parts.push(
        '<button type="button" class="tool" id="hint">' + art("scene-bulb") +
        "Give me a clue</button>"
      );
    }
    parts.push("</div>");
    parts.push('<div id="slot"></div>');
    parts.push("</div>");

    el.stage.innerHTML = parts.join("");

    if (opts.read_aloud && opts.read_aloud_auto) readAloud(question);
    var typed = document.getElementById("typed");
    if (typed && global.matchMedia("(min-width: 760px)").matches) typed.focus();
    var responseText = document.getElementById("response-text");
    if (responseText) {
      responseText.addEventListener("input", function () {
        var count = document.getElementById("response-helper");
        if (count) count.textContent = responseText.value.length + " / " + (question.response_spec.max_chars || 2400) + " characters";
      });
      if (global.matchMedia("(min-width: 760px)").matches) responseText.focus();
    }
  }

  function readAloud(question) {
    var text = question.prompt;
    if (question.phonics_type === "decodable" && question.decodable_text) {
      text = question.decodable_text + ". " + text;
    } else if (question.sound_text) {
      text = "The sound is " + question.sound_text + ". " + text;
    }
    if (question.kind === "choice" && question.choices) {
      text += ". Your choices are: " + question.choices.join(", ");
    }
    App.Speech.speak(text);
  }

  // The stage element persists for the whole quest and only its contents are
  // replaced, so these listeners are attached exactly once. Attaching them per
  // question would stack duplicates and make one tap on Next advance several
  // questions at a time.
  function wireStage() {
    var stage = el.stage;

    stage.addEventListener("pointerdown", function (event) {
      var canvas = event.target.closest("#handwriting-canvas");
      if (!canvas || state.locked) return;
      var point = canvasPoint(canvas, event);
      richState.activeStroke = [point];
      canvas.setPointerCapture(event.pointerId);
      event.preventDefault();
    });
    stage.addEventListener("pointermove", function (event) {
      var canvas = event.target.closest("#handwriting-canvas");
      if (!canvas || !richState.activeStroke) return;
      var point = canvasPoint(canvas, event);
      var stroke = richState.activeStroke;
      drawCanvasSegment(canvas, stroke[stroke.length - 1], point);
      stroke.push(point);
      event.preventDefault();
    });
    ["pointerup", "pointercancel", "pointerleave"].forEach(function (name) {
      stage.addEventListener(name, function (event) {
        if (!richState.activeStroke) return;
        if (richState.activeStroke.length > 1) richState.strokes.push(richState.activeStroke);
        richState.activeStroke = null;
        if (event.preventDefault) event.preventDefault();
      });
    });

    stage.addEventListener("click", function (event) {
      var question = current();

      if (question && isInteractiveKind(question.kind) && event.target.closest("[data-interactive-grid]")) {
        placeInteractiveFromEvent(question, event);
        return;
      }

      var choice = event.target.closest(".choice");
      if (choice && !state.locked && !choice.disabled) {
        submit(choice.dataset.value, choice);
        return;
      }
      var key = event.target.closest(".kp");
      if (key) {
        var input = document.getElementById("typed");
        if (!input || input.readOnly) return;
        App.Sound.play("tap");
        if (key.dataset.key === "del") input.value = input.value.slice(0, -1);
        else input.value += key.dataset.key;
        input.focus();
        return;
      }
      var check = event.target.closest("#check");
      if (check && !state.locked) {
        var activeQuestion = current();
        if (activeQuestion && isInteractiveKind(activeQuestion.kind)) {
          var interactive = interactiveResponse(activeQuestion);
          if (!interactive) {
            interactiveStatus(activeQuestion.kind === "coordinate_points" ? "Plot one point before submitting." : "Plot all three vertices before submitting.", true);
          } else {
            submit(interactive, null);
          }
        } else if (activeQuestion && ["free_text", "handwriting", "audio", "evidence"].indexOf(activeQuestion.kind) >= 0) {
          var rich = richResponse(activeQuestion);
          if (!rich) {
            richStatus("Complete the response before submitting it.", true);
            var firstRich = el.stage.querySelector("textarea");
            if (firstRich) firstRich.focus();
          } else {
            submit(rich, null);
          }
        } else {
          var typed = document.getElementById("typed");
          if (typed && typed.value.trim() !== "") submit(typed.value, null);
          else if (typed) typed.focus();
        }
        return;
      }
      var clearInteractiveButton = event.target.closest("#clear-interactive");
      if (clearInteractiveButton && !state.locked) {
        setInteractivePoints(question, []);
        interactiveStatus("Plotted answer cleared.", false);
        return;
      }
      var applyInteractiveButton = event.target.closest("#apply-interactive");
      if (applyInteractiveButton && !state.locked && question && isInteractiveKind(question.kind)) {
        applyInteractiveFields(question);
        return;
      }
      var clearDrawingButton = event.target.closest("#clear-drawing");
      if (clearDrawingButton) { clearDrawing(); return; }
      var recordAudioButton = event.target.closest("#record-audio");
      if (recordAudioButton) { startAudio(); return; }
      var stopAudioButton = event.target.closest("#stop-audio");
      if (stopAudioButton) { stopAudio(); return; }
      var phonicsSound = event.target.closest("#phonics-sound");
      if (phonicsSound) {
        if (question) App.Speech.speak(question.speak_text || question.sound_text || question.prompt);
        return;
      }
      var say = event.target.closest("#say");
      if (say) { if (question) readAloud(question); return; }
      var replay = event.target.closest("#replay");
      if (replay) {
        // Hearing it again should never be interrupted by the quest moving on.
        if (state.autoAdvance) { clearTimeout(state.autoAdvance); state.autoAdvance = null; }
        App.Speech.speak(state.lastSpoken);
        return;
      }
      var hint = event.target.closest("#hint");
      if (hint) { if (question) showHint(question, hint); return; }
      var greatScore = event.target.closest(".great-score");
      if (greatScore && !greatScore.disabled) {
        var greatRow = greatScore.closest(".great-row");
        if (greatRow) {
          Array.prototype.forEach.call(greatRow.querySelectorAll(".great-score"), function (item) {
            item.classList.remove("selected");
          });
          greatScore.classList.add("selected");
          var saveGreat = document.getElementById("save-great");
          if (saveGreat) saveGreat.disabled = !greatScores();
        }
        return;
      }
      var saveGreatDiagnosticButton = event.target.closest("#save-great-diagnostic");
      if (saveGreatDiagnosticButton && !saveGreatDiagnosticButton.disabled) {
        if (question) saveGreatDiagnostic(question);
        return;
      }
      var saveGreatButton = event.target.closest("#save-great");
      if (saveGreatButton && !saveGreatButton.disabled) {
        if (question) saveGreatReflection(question, saveGreatButton);
        return;
      }
      var next = event.target.closest("#next");
      if (next && !next.disabled) {
        advance();
      }
    });

    stage.addEventListener("input", function (event) {
      if (!event.target.closest("#great-diagnostic")) return;
      var save = document.getElementById("save-great-diagnostic");
      if (save) save.disabled = !greatDiagnosticResponses();
    });

    stage.addEventListener("keydown", function (event) {
      if (event.key !== "Enter") return;
      event.preventDefault();
      var nextBtn = document.getElementById("next");
      if (nextBtn && !nextBtn.disabled) { advance(); return; }
      var activeQuestion = current();
      if (activeQuestion && isInteractiveKind(activeQuestion.kind) && !state.locked) {
        var interactive = interactiveResponse(activeQuestion);
        if (interactive) submit(interactive, null);
        else interactiveStatus("Plot the required points before submitting.", true);
        return;
      }
      var typed = document.getElementById("typed");
      if (typed && !typed.readOnly && typed.value.trim() !== "" && !state.locked) {
        submit(typed.value, null);
      }
    });
  }

  document.addEventListener("keydown", function (event) {
    if (state.finished) return;
    var question = current();
    if (!question || question.kind !== "choice" || state.locked) {
      if (event.key === "Enter") {
        var next = document.getElementById("next");
        if (next && !next.disabled) advance();
      }
      return;
    }
    var index = ["1", "2", "3", "4", "5", "6"].indexOf(event.key);
    if (index >= 0) {
      var buttons = el.stage.querySelectorAll(".choice");
      if (buttons[index]) { buttons[index].click(); }
    }
  });

  function showHint(question, button) {
    if (state.hintShown) return;
    state.hintShown = true;
    if (button) button.classList.add("hidden");
    App.api.post("/api/quest/" + data.id + "/hint", { question_id: question.id }).then(function (res) {
      var text = res.hint || question.hint || "Have a careful look at the picture.";
      var slot = document.getElementById("slot");
      slot.insertAdjacentHTML(
        "afterbegin",
        '<div class="hintbox">' + art("scene-bulb") + "<div>" + esc(text) + "</div></div>"
      );
      if (opts.read_aloud) App.Speech.speak(text);
    });
  }

  var GREAT_STAGES = [
    { key: "G", label: "Given", statement: "I found the important information.", prompt: "What important information did you notice or use?" },
    { key: "R", label: "Required", statement: "I knew what I was trying to find.", prompt: "What exactly were you trying to find?" },
    { key: "E", label: "Equation / Explanation / Link", statement: "I knew what connected the information.", prompt: "What idea, rule, or relationship connected the information?" },
    { key: "A", label: "Act", statement: "I carried out the steps.", prompt: "Show or tell the step you used to work it out." },
    { key: "T", label: "Test", statement: "I checked that my answer made sense.", prompt: "How could you check that your answer makes sense?" }
  ];

  function greatReflectionMarkup() {
    var rows = GREAT_STAGES.map(function (stage) {
      return (
        '<div class="great-row" data-great-stage="' + stage.key + '">' +
        '<div class="great-statement"><b><span class="great-letter">' + stage.key +
        "</span> " + esc(stage.label) + '</b><span>' + esc(stage.statement) + "</span></div>" +
        '<div class="great-options" role="group" aria-label="' + esc(stage.label) + '">' +
        '<button type="button" class="great-score" data-great-score="0">Not yet</button>' +
        '<button type="button" class="great-score" data-great-score="1">With a clue</button>' +
        '<button type="button" class="great-score" data-great-score="2">By myself</button>' +
        "</div></div>"
      );
    }).join("");

    return (
      '<section class="great-check" id="great-check" aria-labelledby="great-title">' +
      '<div class="great-check-head"><h2 id="great-title">Quick GREAT check-in</h2>' +
      '<p>How did you solve this one? Pick one for each thinking step.</p></div>' +
      rows +
      '<div class="great-actions">' +
      '<button type="button" class="btn leaf" id="save-great" disabled>Save check-in</button>' +
      "</div>" +
      '<p class="great-status" id="great-status" aria-live="polite"></p>' +
      "</section>"
    );
  }

  function greatDiagnosticMarkup() {
    var fields = GREAT_STAGES.map(function (stage) {
      return (
        '<div class="great-diagnostic-field">' +
        '<label class="great-diagnostic-label" for="great-diagnostic-' + stage.key + '">' +
        '<span class="great-diagnostic-heading"><span class="great-letter">' + stage.key +
        "</span> " + esc(stage.label) + "</span>" +
        '<span class="great-diagnostic-prompt">' + esc(stage.prompt) + "</span>" +
        "</label>" +
        '<textarea id="great-diagnostic-' + stage.key + '" data-great-diagnostic-stage="' +
        stage.key + '" maxlength="500" rows="2" aria-required="true" ' +
        'placeholder="Write or tell it in your own words"></textarea>' +
        "</div>"
      );
    }).join("");

    return (
      '<section class="great-check great-diagnostic" id="great-diagnostic" ' +
      'aria-labelledby="great-diagnostic-title">' +
      '<div class="great-check-head"><h2 id="great-diagnostic-title">Show your GREAT thinking</h2>' +
      '<p>Tell us what you noticed and did. A grown-up will review your thinking later.</p></div>' +
      '<div class="great-diagnostic-fields">' + fields + "</div>" +
      '<div class="great-actions">' +
      '<button type="button" class="btn leaf" id="save-great-diagnostic" disabled>Save my thinking</button>' +
      "</div>" +
      '<p class="great-status great-diagnostic-status" id="great-diagnostic-status" ' +
      'aria-live="polite" role="status"></p>' +
      "</section>"
    );
  }

  function greatDiagnosticResponses() {
    var card = document.getElementById("great-diagnostic");
    if (!card) return null;
    var responses = {};
    for (var i = 0; i < GREAT_STAGES.length; i++) {
      var stage = GREAT_STAGES[i];
      var input = card.querySelector('[data-great-diagnostic-stage="' + stage.key + '"]');
      if (!input) return null;
      var response = input.value.trim();
      if (!response) return null;
      responses[stage.key] = response;
    }
    return responses;
  }

  function greatDiagnosticStatus(message, error) {
    var status = document.getElementById("great-diagnostic-status");
    if (!status) return;
    status.textContent = message;
    status.className = "great-status great-diagnostic-status" + (error ? " error" : "");
  }

  function setGreatDiagnosticControls(card, disabled) {
    if (!card) return;
    Array.prototype.forEach.call(card.querySelectorAll("textarea, button"), function (item) {
      item.disabled = disabled;
    });
  }

  function saveGreatDiagnostic(question) {
    var responses = greatDiagnosticResponses();
    if (!responses) {
      greatDiagnosticStatus("Answer every thinking prompt first.", true);
      return;
    }

    var card = document.getElementById("great-diagnostic");
    setGreatDiagnosticControls(card, true);
    App.api.post("/api/quest/" + data.id + "/great-diagnostic", {
      question_id: question.id,
      responses: responses
    }).then(function (res) {
      if (res.error) {
        setGreatDiagnosticControls(card, false);
        var save = document.getElementById("save-great-diagnostic");
        if (save) save.disabled = !greatDiagnosticResponses();
        greatDiagnosticStatus(res.error, true);
        return;
      }
      question.great_diagnostic_submitted = true;
      if (card) card.classList.add("saved");
      greatDiagnosticStatus("Saved — your thinking is ready for a grown-up to review.", false);
      unlockNextAfterGreat();
    }).catch(function () {
      setGreatDiagnosticControls(card, false);
      var save = document.getElementById("save-great-diagnostic");
      if (save) save.disabled = !greatDiagnosticResponses();
      greatDiagnosticStatus("That thinking did not save. Please try again.", true);
    });
  }

  function greatScores() {
    var card = document.getElementById("great-check");
    if (!card) return null;
    var scores = {};
    for (var i = 0; i < GREAT_STAGES.length; i++) {
      var stage = GREAT_STAGES[i];
      var selected = card.querySelector(
        '[data-great-stage="' + stage.key + '"] .great-score.selected'
      );
      if (!selected) return null;
      scores[stage.key] = Number(selected.dataset.greatScore);
    }
    return scores;
  }

  function greatStatus(message, error) {
    var status = document.getElementById("great-status");
    if (!status) return;
    status.textContent = message;
    status.className = "great-status" + (error ? " error" : "");
  }

  function unlockNextAfterGreat() {
    var next = document.getElementById("next");
    if (next) next.disabled = false;
  }

  function saveGreatReflection(question, button) {
    var scores = greatScores();
    if (!scores) {
      greatStatus("Choose one answer for each step first.", true);
      return;
    }

    button.disabled = true;
    App.api.post("/api/quest/" + data.id + "/great", {
      question_id: question.id,
      scores: scores
    }).then(function (res) {
      if (res.error) {
        button.disabled = false;
        greatStatus(res.error, true);
        return;
      }
      question.great_assessed = true;
      var card = document.getElementById("great-check");
      if (card) {
        card.classList.add("saved");
        Array.prototype.forEach.call(card.querySelectorAll("button"), function (item) {
          item.disabled = true;
        });
      }
      greatStatus("Saved — you noticed how you thought!", false);
      unlockNextAfterGreat();
    }).catch(function () {
      button.disabled = false;
      greatStatus("That check-in did not save. Please try again.", true);
    });
  }

  // -----------------------------------------------------------------------
  // Submitting
  // -----------------------------------------------------------------------
  function submit(value, button) {
    var question = current();
    state.locked = true;
    var seconds = Math.round((Date.now() - state.questionStartedAt) / 1000);
    var body = {
      question_id: question.id,
      seconds: seconds,
      used_hint: state.hintShown
    };
    if (typeof value === "string") body.answer = value;
    else body.response = value;

    App.api
      .post("/api/quest/" + data.id + "/answer", body)
      .then(function (res) {
        if (res.error) {
          state.locked = false;
          if (res.reload) { global.location.reload(); return; }
          showTrouble(res.error);
          return;
        }
        if (res.status === "retry") {
          handleRetry(res, button, value);
          return;
        }
        if (res.status === "submitted") {
          handleSubmitted(res, question);
          return;
        }
        handleResult(res, button, value, question);
      })
      .catch(function () {
        state.locked = false;
        showTrouble("The app could not be reached just now.");
      });
  }

  // Something went wrong that is not the child's fault. Say so kindly, and give
  // them a button rather than leaving a tap that appears to do nothing.
  function showTrouble(detail) {
    var slot = document.getElementById("slot");
    if (!slot) return;
    slot.innerHTML =
      '<div class="feedback try">' + art("pip-oops", "pip") +
      '<div class="say"><div class="headline">Hmm, that did not save</div>' +
      '<div class="detail">' + esc(detail) + " Your earlier answers are safe. " +
      "Tap to try again, or ask a grown-up to restart the app.</div>" +
      "</div></div>" +
      '<button type="button" class="btn block ghost" style="margin-top:12px" ' +
      'onclick="window.location.reload()">Try again</button>';
  }

  function handleRetry(res, button, value) {
    App.Sound.play("retry");
    var retryQuestion = current();
    if (retryQuestion && isInteractiveKind(retryQuestion.kind)) {
      setInteractivePoints(retryQuestion, []);
      interactiveStatus("Try the diagram again. Check each coordinate carefully.", true);
    } else if (button) {
      button.classList.add("wrong");
      button.disabled = true;
    } else {
      var input = document.getElementById("typed");
      if (input) {
        input.classList.add("wrong");
        // Clear rather than select. The on-screen keypad appends, so leaving
        // the old answer in place turns "12" plus a tap on 7 into "127".
        input.value = "";
        input.focus();
        setTimeout(function () { input.classList.remove("wrong"); }, 900);
      }
    }
    var slot = document.getElementById("slot");
    slot.innerHTML =
      '<div class="feedback try">' + art("pip-think", "pip") +
      '<div class="say"><div class="headline">' + esc(res.message) + "</div>" +
      (res.hint ? '<div class="detail">' + esc(res.hint) + "</div>" : "") +
      "</div></div>";
    // Nothing auto-advances on a retry, so the clue can be read in full.
    if (opts.read_aloud) {
      App.Speech.speak(res.message + (res.hint ? ". " + res.hint : ""));
    }
    state.locked = false;
    state.questionStartedAt = Date.now();
  }

  function handleSubmitted(res, question) {
    question.answered = true;
    question.pending = true;
    question.status = "submitted";
    question.result = null;
    paintDots();
    var isLast = state.index >= data.questions.length - 1;
    var lines = [];
    lines.push('<div class="feedback try">');
    lines.push(art("pip-happy", "pip"));
    lines.push('<div class="say"><div class="headline">' + esc(res.message || "Saved for a grown-up to review") + "</div>");
    lines.push('<div class="detail">Your response is safely stored on this device. You can move to the next question.</div></div></div>');
    lines.push('<button type="button" class="btn block leaf" id="next" style="margin-top:14px">' +
      (isLast ? "Finish 🎉" : "Next question →") + "</button>");
    var slot = document.getElementById("slot");
    slot.innerHTML = lines.join("");
    updateHeader(res.child);
    state.lastSpoken = res.message || "Your response was saved for a grown-up to review.";
    state.lastCorrect = null;
    if (opts.read_aloud) App.Speech.speak(state.lastSpoken);
  }

  function handleResult(res, button, value, question) {
    question.answered = true;
    question.result = !!res.correct;
    paintDots();

    if (res.correct) {
      App.Sound.play("correct");
      if (res.coins) setTimeout(function () { App.Sound.play("coin"); }, 220);
    } else {
      App.Sound.play("wrong");
    }

    var buttons = el.stage.querySelectorAll(".choice");
    Array.prototype.forEach.call(buttons, function (candidate) {
      candidate.disabled = true;
      var candidateValue = candidate.dataset.value;
      if (candidateValue === String(res.answer)) candidate.classList.add("right");
      else if (candidateValue === String(value)) candidate.classList.add("wrong");
      else candidate.classList.add("dim");
    });

    var input = document.getElementById("typed");
    if (input) {
      input.classList.add(res.correct ? "right" : "wrong");
      input.readOnly = true;
      var pad = el.stage.querySelector(".keypad");
      if (pad) pad.classList.add("hidden");
      var check = document.getElementById("check");
      if (check) check.classList.add("hidden");
    }
    if (isInteractiveKind(question.kind)) setInteractiveLocked(true);

    var isLast = state.index >= data.questions.length - 1;
    var lines = [];
    // Pip reacts, which turns a verdict into a reaction from a friend.
    lines.push('<div class="feedback ' + (res.correct ? "good" : "bad") + '">');
    lines.push(art(res.correct ? "pip-happy" : "pip-oops", "pip"));
    lines.push('<div class="say">');
    lines.push('<div class="headline">' + esc(res.message) + "</div>");
    if (!res.correct) {
      lines.push('<div class="detail">The answer is <b>' + esc(res.answer) + "</b>.</div>");
    }
    if (res.explain) {
      lines.push('<div class="detail">' + esc(res.explain) + "</div>");
    }
    if (res.correct && res.xp) {
      lines.push(
        '<div class="reward"><b>+' + res.xp + " XP</b>" +
        (res.coins ? art("scene-coin") + "<b>+" + res.coins + "</b>" : "") +
        "</div>"
      );
    }
    lines.push("</div></div>");
    if (opts.read_aloud) {
      lines.push(
        '<button type="button" class="tool" id="replay" style="margin-top:12px">' +
        art("scene-speaker") + "Say that again</button>"
      );
    }
    lines.push(opts.great_diagnostic ? greatDiagnosticMarkup() : greatReflectionMarkup());
    lines.push(
      '<button type="button" class="btn block ' + (res.correct ? "leaf" : "grape") +
      '" id="next" disabled style="margin-top:14px">' +
      (isLast ? "Finish 🎉" : "Next question →") + "</button>"
    );

    var slot = document.getElementById("slot");
    slot.innerHTML = lines.join("");
    updateHeader(res.child);

    var spoken = res.message + (res.correct ? "" : ". The answer is " + res.answer) +
      (res.explain ? ". " + res.explain : "");
    state.lastSpoken = spoken;
    state.lastCorrect = !!res.correct;

    if (opts.read_aloud) App.Speech.speak(spoken);
  }

  function advance() {
    // Keep the visual lock authoritative too: keyboard events and other callers
    // must not move past an unsaved GREAT reflection or diagnostic interview.
    var next = document.getElementById("next");
    if (next && next.disabled) return;
    if (next) next.disabled = true;

    // Belt and braces: a tap, the Enter key and the auto-advance timer can all
    // race, and skipping a question would silently shorten the quest.
    if (state.advancing) return;
    state.advancing = true;
    setTimeout(function () { state.advancing = false; }, 250);

    if (state.autoAdvance) { clearTimeout(state.autoAdvance); state.autoAdvance = null; }
    App.Speech.stop();
    state.index += 1;
    if (state.index >= data.questions.length) { finish(); return; }
    if (state.outOfTime) { showOutOfTime(); return; }
    maybeOfferBreak();
    renderQuestion();
    global.scrollTo({ top: 0, behavior: "smooth" });
  }

  function updateHeader(child) {
    if (!child) return;
    var xp = document.getElementById("hdr-xp");
    var coins = document.getElementById("hdr-coins");
    var level = document.getElementById("hdr-level");
    var bar = document.getElementById("hdr-bar");
    if (xp) xp.textContent = child.xp;
    if (coins) coins.textContent = child.coins;
    if (level) level.textContent = child.level;
    if (bar) bar.style.width = child.level_pct + "%";
  }

  // -----------------------------------------------------------------------
  // Finishing
  // -----------------------------------------------------------------------
  function finish() {
    if (state.finished) return;
    state.finished = true;
    App.Speech.stop();
    App.api.post("/api/quest/" + data.id + "/finish", {}).then(function (summary) {
      if (summary.error) { global.location.href = "/home"; return; }
      showSummary(summary);
    });
  }

  function showSummary(summary) {
    App.Sound.play("finish");
    if (summary.stars >= 2) App.confetti(summary.stars >= 3 ? 60 : 38);
    updateHeader(summary.child);

    var stars = "";
    for (var i = 0; i < 3; i++) {
      stars +=
        '<span class="slot ' + (i < summary.stars ? "lit" : "") + '">' +
        art(i < summary.stars ? "scene-star" : "scene-star-empty") +
        "</span>";
    }

    var badges = (summary.badges || [])
      .map(function (badge) {
        return (
          '<div class="badge-pop">' + art(badge.rosette || "rosette-fun", "rosette") +
          "<div><b>New badge: " + esc(badge.name) + "</b><br><small>" +
          esc(badge.description) + "</small></div></div>"
        );
      })
      .join("");

    var pose = summary.stars >= 3 ? "cheer" : summary.stars >= 2 ? "happy" : "idle";

    var html =
      '<div class="overlay" id="summary"><div class="sheet">' +
      '<div class="pip-big art-holder pop">' + art("pip-" + pose) + "</div>" +
      '<div class="stars">' + stars + "</div>" +
      "<h1>" + esc(summary.message) + "</h1>" +
      '<p class="muted">' + esc(summary.title) + "</p>" +
      '<div class="score-grid">' +
      '<div><b class="nums">' + summary.correct + "/" + summary.answered + "</b><span>right</span></div>" +
      '<div><b class="nums">+' + summary.xp + "</b><span>bonus XP</span></div>" +
      '<div><b class="nums">+' + summary.coins + "</b><span>coins</span></div>" +
      "</div>" +
      badges +
      '<div class="stack" style="margin-top:18px">' +
      '<button type="button" class="btn big block leaf" data-start-quest data-subject="' +
      esc(data.subject === "mixed" ? "" : data.subject) + '" data-pathway="' +
      esc(data.pathway || "") + '" data-mode="' + esc(data.mode) +
      '">Another quest</button>' +
      '<a class="btn block ghost" href="/done/' + data.id + '">See my answers</a>' +
      '<a class="btn block ghost" href="/home">Back home</a>' +
      "</div></div></div>";

    document.body.insertAdjacentHTML("beforeend", html);
    if (summary.badges && summary.badges.length) {
      setTimeout(function () { App.Sound.play("levelup"); }, 700);
    }
    if (opts.read_aloud) {
      App.Speech.speak(summary.message + " You got " + summary.correct + " out of " + summary.answered + ".");
    }
  }

  // -----------------------------------------------------------------------
  // Breaks, time limits and quitting
  // -----------------------------------------------------------------------
  function maybeOfferBreak() {
    var after = opts.break_after_minutes || 0;
    if (!after || state.breakOffered) return;
    var minutes = (Date.now() - state.quizStartedAt) / 60000;
    if (minutes < after) return;
    state.breakOffered = true;

    var html =
      '<div class="overlay" id="breaker"><div class="sheet">' +
      '<div class="pip-big art-holder bob">' + art("pip-idle") + "</div>" +
      "<h1>Wiggle break!</h1>" +
      "<p>You have been working hard for " + Math.round(minutes) + " minutes. " +
      "Stand up, stretch tall, and have a drink of water.</p>" +
      '<div class="stack" style="margin-top:16px">' +
      '<button type="button" class="btn block leaf" id="break-back">I am ready — keep going</button>' +
      '<a class="btn block ghost" href="' + esc(returnPath()) + '">' +
      (data.return_to ? "Back to lesson" : "Stop for now") + "</a>" +
      "</div></div></div>";
    document.body.insertAdjacentHTML("beforeend", html);
    App.Sound.play("star");
    document.getElementById("break-back").addEventListener("click", function () {
      var overlay = document.getElementById("breaker");
      if (overlay) overlay.remove();
      state.quizStartedAt = Date.now();
      state.breakOffered = false;
    });
  }

  function showOutOfTime() {
    if (document.getElementById("timeup")) return;
    var html =
      '<div class="overlay" id="timeup"><div class="sheet">' +
      '<div class="pip-big art-holder bob-slow">' + art("pip-sleep") + "</div>" +
      "<h1>That is your time for today</h1>" +
      "<p>Brilliant effort. Your practice is all saved — come back tomorrow!</p>" +
      '<a class="btn big block leaf" href="' + esc(returnPath()) + '" style="margin-top:16px">' +
      (data.return_to ? "Back to lesson" : "Back home") + "</a>" +
      "</div></div>";
    document.body.insertAdjacentHTML("beforeend", html);
  }

  var quit = document.getElementById("quit");
  if (quit) {
    quit.addEventListener("click", function () {
      var answered = data.questions.filter(function (q) { return q.answered; }).length;
      var message = answered
        ? "Stop this quest? Your " + answered + " answered question" + (answered === 1 ? "" : "s") + " will be saved."
        : "Leave this quest?";
      if (!global.confirm(message)) return;
      App.Speech.stop();
      App.api.post("/api/quest/" + data.id + "/abandon", {}).then(function () {
        global.location.href = returnPath();
      });
    });
  }

  // -----------------------------------------------------------------------
  // Heartbeat: real minutes on task, for the parent's daily limit
  // -----------------------------------------------------------------------
  var TICK = 15;
  var visible = true;
  document.addEventListener("visibilitychange", function () {
    visible = document.visibilityState === "visible";
  });

  setInterval(function () {
    if (!visible || state.finished) return;
    App.api.post("/api/heartbeat", { seconds: TICK }).then(function (res) {
      if (!res || res.error) return;
      if (el.timer && opts.show_timer) {
        el.timer.textContent =
          res.minutes_left == null ? res.minutes_used + " min" : res.minutes_left + " min left";
      }
      if (res.out_of_time || !res.within_hours) {
        state.outOfTime = true;
        if (!state.locked && !document.getElementById("next")) showOutOfTime();
      }
    });
  }, TICK * 1000);

  // -----------------------------------------------------------------------
  // Go
  // -----------------------------------------------------------------------
  // Carry forward the outcome of anything answered before a reload, so the
  // dots show real progress rather than starting blank.
  data.questions.forEach(function (question) {
    question.pending = question.status === "submitted" || !!question.pending;
    question.result = question.correct === true ? true : (question.correct === false ? false : null);
  });
  wireStage();
  state.index = firstUnanswered();
  if (state.index >= data.questions.length) finish();
  else renderQuestion();
})(window);
