/* ==========================================================================
   Shared behaviour: sound, read-aloud, confetti and the API helper.

   All the audio is synthesised with the Web Audio API and all the speech uses
   the browser's own voice, so the app ships with no media files and works with
   no network connection.
   ========================================================================== */

(function (global) {
  "use strict";

  var CSRF =
    (document.querySelector('meta[name="csrf-token"]') || {}).content || "";

  // -----------------------------------------------------------------------
  // API
  // -----------------------------------------------------------------------
  function request(method, url, body) {
    return fetch(url, {
      method: method,
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": CSRF,
        "X-Requested-With": "fetch"
      },
      credentials: "same-origin",
      body: body ? JSON.stringify(body) : undefined
    }).then(function (response) {
      return response
        .json()
        .catch(function () {
          return { error: "The server sent something unexpected." };
        })
        .then(function (data) {
          data._status = response.status;
          data._ok = response.ok;
          return data;
        });
    });
  }

  var api = {
    get: function (url) { return request("GET", url); },
    post: function (url, body) { return request("POST", url, body); }
  };

  // -----------------------------------------------------------------------
  // Sound
  // -----------------------------------------------------------------------
  var Sound = (function () {
    var ctx = null;
    var enabled = true;

    function context() {
      if (ctx) return ctx;
      var Ctor = global.AudioContext || global.webkitAudioContext;
      if (!Ctor) return null;
      try { ctx = new Ctor(); } catch (err) { ctx = null; }
      return ctx;
    }

    function tone(freq, start, duration, type, peak) {
      var ac = context();
      if (!ac) return;
      var osc = ac.createOscillator();
      var gain = ac.createGain();
      osc.type = type || "sine";
      osc.frequency.setValueAtTime(freq, ac.currentTime + start);
      gain.gain.setValueAtTime(0, ac.currentTime + start);
      gain.gain.linearRampToValueAtTime(peak == null ? 0.16 : peak, ac.currentTime + start + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0008, ac.currentTime + start + duration);
      osc.connect(gain);
      gain.connect(ac.destination);
      osc.start(ac.currentTime + start);
      osc.stop(ac.currentTime + start + duration + 0.02);
    }

    function play(name) {
      if (!enabled) return;
      var ac = context();
      if (!ac) return;
      if (ac.state === "suspended") ac.resume();

      switch (name) {
        case "correct":
          tone(660, 0, 0.13, "triangle");
          tone(880, 0.09, 0.16, "triangle");
          tone(1174, 0.18, 0.22, "triangle", 0.13);
          break;
        case "retry":
          tone(440, 0, 0.12, "sine", 0.11);
          tone(392, 0.1, 0.16, "sine", 0.1);
          break;
        case "wrong":
          // Deliberately soft and low. A harsh buzzer makes children freeze.
          tone(300, 0, 0.16, "sine", 0.1);
          tone(240, 0.13, 0.22, "sine", 0.09);
          break;
        case "tap":
          tone(520, 0, 0.05, "sine", 0.07);
          break;
        case "coin":
          tone(1046, 0, 0.06, "square", 0.07);
          tone(1568, 0.06, 0.11, "square", 0.06);
          break;
        case "star":
          tone(784, 0, 0.1, "triangle");
          tone(1046, 0.1, 0.12, "triangle");
          break;
        case "finish":
          [523, 659, 784, 1046].forEach(function (freq, i) {
            tone(freq, i * 0.11, 0.3, "triangle", 0.14);
          });
          break;
        case "levelup":
          [659, 784, 988, 1318].forEach(function (freq, i) {
            tone(freq, i * 0.09, 0.34, "triangle", 0.13);
          });
          break;
        default:
          break;
      }
    }

    return {
      play: play,
      set: function (value) { enabled = !!value; },
      get enabled() { return enabled; },
      unlock: function () {
        var ac = context();
        if (ac && ac.state === "suspended") ac.resume();
      }
    };
  })();

  // -----------------------------------------------------------------------
  // Read aloud
  // -----------------------------------------------------------------------
  var Speech = (function () {
    var available = "speechSynthesis" in global;
    var voice = null;
    var picked = false;

    function pick() {
      if (!available || picked) return;
      var voices = global.speechSynthesis.getVoices() || [];
      if (!voices.length) return;
      voice =
        voices.filter(function (v) { return /en[-_]GB/i.test(v.lang); })[0] ||
        voices.filter(function (v) { return /^en/i.test(v.lang); })[0] ||
        voices[0];
      picked = true;
    }

    if (available) {
      pick();
      global.speechSynthesis.onvoiceschanged = function () { picked = false; pick(); };
    }

    function speak(text) {
      if (!available || !text) return;
      pick();
      try {
        global.speechSynthesis.cancel();
        var utter = new global.SpeechSynthesisUtterance(String(text));
        if (voice) utter.voice = voice;
        utter.lang = (voice && voice.lang) || "en-GB";
        utter.rate = 0.92;
        utter.pitch = 1.05;
        global.speechSynthesis.speak(utter);
      } catch (err) { /* speech is a bonus, never a blocker */ }
    }

    function stop() {
      if (available) {
        try { global.speechSynthesis.cancel(); } catch (err) { /* ignore */ }
      }
    }

    return { speak: speak, stop: stop, available: available };
  })();

  // -----------------------------------------------------------------------
  // Confetti
  // -----------------------------------------------------------------------
  function confetti(count) {
    if (document.body.classList.contains("motion-off")) return;
    var colours = ["#e0447a", "#2481cc", "#3d9c48", "#ef9a1e", "#7c4dd8", "#f2647a"];
    var layer = document.createElement("div");
    layer.className = "confetti";
    var total = count || 44;
    for (var i = 0; i < total; i++) {
      var piece = document.createElement("i");
      piece.style.left = Math.random() * 100 + "vw";
      piece.style.background = colours[i % colours.length];
      piece.style.animationDuration = 1.7 + Math.random() * 1.5 + "s";
      piece.style.animationDelay = Math.random() * 0.5 + "s";
      piece.style.transform = "rotate(" + Math.random() * 360 + "deg)";
      layer.appendChild(piece);
    }
    document.body.appendChild(layer);
    setTimeout(function () { layer.remove(); }, 4200);
  }

  // -----------------------------------------------------------------------
  // Small helpers
  // -----------------------------------------------------------------------
  function on(selector, event, handler, root) {
    (root || document).addEventListener(event, function (e) {
      var target = e.target.closest(selector);
      if (target) handler(e, target);
    });
  }

  function busy(button, isBusy) {
    if (!button) return;
    if (isBusy) {
      button.dataset.label = button.innerHTML;
      button.disabled = true;
      button.classList.add("is-disabled");
    } else {
      button.disabled = false;
      button.classList.remove("is-disabled");
      if (button.dataset.label) button.innerHTML = button.dataset.label;
    }
  }

  // A first tap anywhere unlocks audio on iOS.
  ["pointerdown", "keydown"].forEach(function (evt) {
    global.addEventListener(evt, function unlock() {
      Sound.unlock();
      global.removeEventListener(evt, unlock);
    }, { once: true });
  });

  // Any element with data-start-quest fires off a quest and navigates to it.
  document.addEventListener("click", function (event) {
    var trigger = event.target.closest("[data-start-quest]");
    if (!trigger) return;
    event.preventDefault();
    if (trigger.dataset.locked === "1") return;
    Sound.play("tap");
    busy(trigger, true);
    trigger.innerHTML = "Getting ready…";
    api
      .post("/api/quest/start", {
        subject: trigger.dataset.subject || null,
        mode: trigger.dataset.mode || "mixed",
        skill_id: trigger.dataset.skill || null,
        count: trigger.dataset.count ? parseInt(trigger.dataset.count, 10) : null
      })
      .then(function (data) {
        if (data.url) {
          global.location.href = data.url;
          return;
        }
        busy(trigger, false);
        alert(data.error || "Could not start that quest. Please try again.");
        if (data.blocked) global.location.href = "/blocked";
      })
      .catch(function () {
        busy(trigger, false);
        alert("Could not reach the app. Is it still running?");
      });
  });

  global.App = {
    api: api,
    Sound: Sound,
    Speech: Speech,
    confetti: confetti,
    on: on,
    busy: busy,
    csrf: CSRF
  };
})(window);
