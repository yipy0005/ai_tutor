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
        else if (i === state.index) cls = "now";
        return '<i class="' + cls + '"></i>';
      })
      .join("");
    if (el.counter) {
      el.counter.textContent =
        Math.min(state.index + 1, data.questions.length) + " of " + data.questions.length;
    }
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

  // -----------------------------------------------------------------------
  // Rendering a question
  // -----------------------------------------------------------------------
  function renderQuestion() {
    var question = current();
    if (!question) { finish(); return; }

    state.questionStartedAt = Date.now();
    state.hintShown = false;
    state.locked = false;
    paintDots();

    var yearPill = question.year ? '<span class="pill y' + question.year + '">Year ' + question.year + "</span>" : "";
    var parts = [];

    parts.push('<div class="qcard enter">');
    parts.push('<div class="qtag">' + yearPill + " <span>" + esc(question.skill_name || "") + "</span></div>");

    if (question.passage_text) {
      var paragraphs = String(question.passage_text)
        .split(/\n\s*\n/)
        .map(function (block) { return "<p>" + esc(block).replace(/\n/g, "<br>") + "</p>"; })
        .join("");
      parts.push(
        '<div class="passage" id="passage"><h4>📖 ' + esc(question.passage_title || "Read this") +
        "</h4>" + paragraphs + "</div>"
      );
    }

    parts.push('<h1 class="qprompt" id="prompt">' + esc(question.prompt) + "</h1>");
    if (question.prompt_sub) {
      parts.push('<div class="qsub">' + esc(question.prompt_sub) + "</div>");
    }

    if (question.visual) {
      var markup = Visuals.render(question.visual);
      if (markup) parts.push('<div class="visual">' + markup + "</div>");
    }

    if (question.kind === "choice") {
      var letters = ["A", "B", "C", "D", "E", "F"];
      var long = (question.choices || []).some(function (choice) { return String(choice).length > 22; });
      parts.push('<div class="choices' + (long ? "" : " pairs") + '" id="choices">');
      (question.choices || []).forEach(function (choice, i) {
        parts.push(
          '<button type="button" class="choice" data-value="' + esc(choice) + '">' +
          '<span class="key">' + letters[i] + "</span><span>" + esc(choice) + "</span></button>"
        );
      });
      parts.push("</div>");
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
      parts.push('<button type="button" class="tool" id="say">🔊 Read it to me</button>');
    }
    if (opts.allow_hints && question.hint) {
      parts.push('<button type="button" class="tool" id="hint">💡 Give me a clue</button>');
    }
    parts.push("</div>");
    parts.push('<div id="slot"></div>');
    parts.push("</div>");

    el.stage.innerHTML = parts.join("");

    if (opts.read_aloud && opts.read_aloud_auto) readAloud(question);
    var typed = document.getElementById("typed");
    if (typed && global.matchMedia("(min-width: 760px)").matches) typed.focus();
  }

  function readAloud(question) {
    var text = question.prompt;
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

    stage.addEventListener("click", function (event) {
      var question = current();

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
        var typed = document.getElementById("typed");
        if (typed && typed.value.trim() !== "") submit(typed.value, null);
        else if (typed) typed.focus();
        return;
      }
      var say = event.target.closest("#say");
      if (say) { if (question) readAloud(question); return; }
      var replay = event.target.closest("#replay");
      if (replay) {
        // Hearing it again should never be interrupted by the quest moving on.
        if (state.autoAdvance) { clearTimeout(state.autoAdvance); state.autoAdvance = null; }
        App.Speech.speak(state.lastSpoken, function () {
          if (state.lastCorrect && !state.finished) {
            state.autoAdvance = setTimeout(function () {
              var button = document.getElementById("next");
              if (button && !button.disabled) advance();
            }, 900);
          }
        });
        return;
      }
      var hint = event.target.closest("#hint");
      if (hint) { if (question) showHint(question, hint); return; }
      var next = event.target.closest("#next");
      if (next) {
        // Guard against a double tap firing advance twice.
        next.disabled = true;
        advance();
      }
    });

    stage.addEventListener("keydown", function (event) {
      if (event.key !== "Enter") return;
      event.preventDefault();
      var nextBtn = document.getElementById("next");
      if (nextBtn && !nextBtn.disabled) { nextBtn.disabled = true; advance(); return; }
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
      if (event.key === "Enter" && document.getElementById("next")) advance();
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
        '<div class="hintbox">💡 ' + esc(text) + "</div>"
      );
      if (opts.read_aloud) App.Speech.speak(text);
    });
  }

  // -----------------------------------------------------------------------
  // Submitting
  // -----------------------------------------------------------------------
  function submit(value, button) {
    var question = current();
    state.locked = true;
    var seconds = Math.round((Date.now() - state.questionStartedAt) / 1000);

    App.api
      .post("/api/quest/" + data.id + "/answer", {
        question_id: question.id,
        answer: value,
        seconds: seconds,
        used_hint: state.hintShown
      })
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
      '<div class="feedback try"><div class="headline">🔌 Hmm, that did not save</div>' +
      '<div class="detail">' + esc(detail) + " Your earlier answers are safe. " +
      "Tap to try again, or ask a grown-up to restart the app.</div></div>" +
      '<button type="button" class="btn block ghost" style="margin-top:12px" ' +
      'onclick="window.location.reload()">Try again</button>';
  }

  function handleRetry(res, button, value) {
    App.Sound.play("retry");
    if (button) {
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
      '<div class="feedback try"><div class="headline">🤔 ' + esc(res.message) + "</div>" +
      (res.hint ? '<div class="detail">💡 ' + esc(res.hint) + "</div>" : "") +
      "</div>";
    // Nothing auto-advances on a retry, so the clue can be read in full.
    if (opts.read_aloud) {
      App.Speech.speak(res.message + (res.hint ? ". " + res.hint : ""));
    }
    state.locked = false;
    state.questionStartedAt = Date.now();
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

    var isLast = state.index >= data.questions.length - 1;
    var lines = [];
    lines.push('<div class="feedback ' + (res.correct ? "good" : "bad") + '">');
    lines.push(
      '<div class="headline">' + (res.correct ? "✅" : "💡") + " " + esc(res.message) + "</div>"
    );
    if (!res.correct) {
      lines.push('<div class="detail">The answer is <b>' + esc(res.answer) + "</b>.</div>");
    }
    if (res.explain) {
      lines.push('<div class="detail">' + esc(res.explain) + "</div>");
    }
    if (res.correct && res.xp) {
      lines.push('<div class="detail">+' + res.xp + " XP" + (res.coins ? " · +" + res.coins + " 🪙" : "") + "</div>");
    }
    lines.push("</div>");
    if (opts.read_aloud) {
      lines.push(
        '<button type="button" class="tool" id="replay" style="margin-top:12px">' +
        "🔊 Say that again</button>"
      );
    }
    lines.push(
      '<button type="button" class="btn block ' + (res.correct ? "leaf" : "grape") +
      '" id="next" style="margin-top:14px">' +
      (isLast ? "Finish 🎉" : "Next question →") + "</button>"
    );

    var slot = document.getElementById("slot");
    slot.innerHTML = lines.join("");
    updateHeader(res.child);

    var spoken = res.message + (res.correct ? "" : ". The answer is " + res.answer) +
      (res.explain ? ". " + res.explain : "");
    state.lastSpoken = spoken;
    state.lastCorrect = !!res.correct;

    function autoAdvanceNow() {
      var button = document.getElementById("next");
      if (button && !button.disabled) advance();
    }

    if (opts.read_aloud) {
      // Correct answers move on by themselves — but only once the explanation
      // has actually been read out. Cutting the reason for the answer off
      // mid-sentence is worse than a slightly slower quest.
      App.Speech.speak(spoken, function () {
        if (!res.correct || state.finished) return;
        state.autoAdvance = setTimeout(autoAdvanceNow, 900);
      });
    } else if (res.correct) {
      state.autoAdvance = setTimeout(autoAdvanceNow, 1500);
    }
  }

  function advance() {
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
      stars += '<i class="' + (i < summary.stars ? "lit" : "") + '">' + (i < summary.stars ? "⭐" : "☆") + "</i>";
    }

    var badges = (summary.badges || [])
      .map(function (badge) {
        return (
          '<div class="badge-pop"><span class="em">' + esc(badge.emoji) + "</span><div><b>New badge: " +
          esc(badge.name) + "</b><br><small>" + esc(badge.description) + "</small></div></div>"
        );
      })
      .join("");

    var html =
      '<div class="overlay" id="summary"><div class="sheet">' +
      '<div class="stars">' + stars + "</div>" +
      "<h1>" + esc(summary.message) + "</h1>" +
      '<p class="muted">' + esc(summary.title) + "</p>" +
      '<div class="score-grid">' +
      "<div><b>" + summary.correct + "/" + summary.answered + "</b><span>right</span></div>" +
      "<div><b>+" + summary.xp + "</b><span>bonus XP</span></div>" +
      "<div><b>+" + summary.coins + "</b><span>coins</span></div>" +
      "</div>" +
      badges +
      '<div class="stack" style="margin-top:18px">' +
      '<button type="button" class="btn big block leaf" data-start-quest data-subject="' +
      esc(data.subject === "mixed" ? "" : data.subject) + '" data-mode="' + esc(data.mode) +
      '">Another quest 🚀</button>' +
      '<a class="btn block ghost" href="/done/' + data.id + '">See my answers</a>' +
      '<a class="btn block ghost" href="/home">Back home 🏠</a>' +
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
      '<div style="font-size:3.4rem">🤸</div>' +
      "<h1>Wiggle break!</h1>" +
      "<p>You have been working hard for " + Math.round(minutes) + " minutes. " +
      "Stand up, stretch tall, and have a drink of water.</p>" +
      '<div class="stack" style="margin-top:16px">' +
      '<button type="button" class="btn block leaf" id="break-back">I am ready — keep going</button>' +
      '<a class="btn block ghost" href="/home">Stop for now</a>' +
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
      '<div style="font-size:3.4rem">⏰</div>' +
      "<h1>That is your time for today</h1>" +
      "<p>Brilliant effort. Your practice is all saved — come back tomorrow!</p>" +
      '<a class="btn big block leaf" href="/home" style="margin-top:16px">Back home 🏠</a>' +
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
        global.location.href = "/home";
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
    question.result = question.answered ? !!question.correct : null;
  });
  wireStage();
  state.index = firstUnanswered();
  if (state.index >= data.questions.length) finish();
  else renderQuestion();
})(window);
