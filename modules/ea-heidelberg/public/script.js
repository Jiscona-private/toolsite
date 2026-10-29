(function () {
  "use strict";

  function initNav() {
    var toggle = document.querySelector("[data-nav-toggle]");
    var links = document.querySelector("[data-nav-links]");
    if (!toggle || !links) return;
    toggle.addEventListener("click", function () {
      var open = links.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  function initCountUp() {
    var els = document.querySelectorAll("[data-countup]");
    if (!els.length) return;
    var done = new WeakSet();

    function animate(el) {
      if (done.has(el)) return;
      done.add(el);
      var target = parseFloat(el.getAttribute("data-countup"));
      var suffix = el.getAttribute("data-suffix") || "";
      var duration = 1100;
      var start = null;

      function step(ts) {
        if (start === null) start = ts;
        var progress = Math.min((ts - start) / duration, 1);
        var eased = 1 - Math.pow(1 - progress, 3);
        var value = Math.round(target * eased);
        el.textContent = value.toLocaleString() + suffix;
        if (progress < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    }

    if ("IntersectionObserver" in window) {
      var observer = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) animate(entry.target);
          });
        },
        { threshold: 0.5 }
      );
      els.forEach(function (el) { observer.observe(el); });
    } else {
      els.forEach(animate);
    }
  }

  // Generic "tap a button -> reveal the matching panel" behavior, used for
  // both the cause-area mini-quiz and the everyday-spending comparison.
  // Markup contract: a [data-reveal-group] wraps buttons with
  // [data-reveal="<id>"] and panels with [data-reveal-panel="<id>"].
  function initRevealGroups() {
    document.querySelectorAll("[data-reveal-group]").forEach(function (group) {
      var buttons = group.querySelectorAll("[data-reveal]");
      var panels = group.querySelectorAll("[data-reveal-panel]");
      buttons.forEach(function (btn) {
        btn.addEventListener("click", function () {
          var target = btn.getAttribute("data-reveal");
          buttons.forEach(function (b) { b.classList.toggle("is-active", b === btn); });
          panels.forEach(function (p) {
            p.classList.toggle("is-visible", p.getAttribute("data-reveal-panel") === target);
          });
        });
      });
    });
  }

  // Birth-lottery-style luck reveal: a trigger button picks one random
  // [data-luck-card] inside the same [data-luck-group] and shows it (hiding
  // the rest). Re-clicking draws again, excluding the card just shown where
  // possible so it feels like a fresh draw.
  function initLuckReveal() {
    document.querySelectorAll("[data-luck-group]").forEach(function (group) {
      var trigger = group.querySelector("[data-luck-trigger]");
      var cards = Array.prototype.slice.call(group.querySelectorAll("[data-luck-card]"));
      if (!trigger || !cards.length) return;
      var lastIndex = -1;

      trigger.addEventListener("click", function () {
        var index = Math.floor(Math.random() * cards.length);
        if (cards.length > 1 && index === lastIndex) {
          index = (index + 1) % cards.length;
        }
        lastIndex = index;
        cards.forEach(function (card, i) {
          card.classList.toggle("is-visible", i === index);
        });
        trigger.textContent = trigger.getAttribute("data-luck-again") || trigger.textContent;
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initNav();
    initCountUp();
    initRevealGroups();
    initLuckReveal();
  });
})();
