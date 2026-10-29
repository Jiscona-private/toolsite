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

  // Birth-lottery-style luck reveal. A [data-luck-default] card (the draw
  // the visitor actually got) is visible from the start — self-contained,
  // not written as a contrast to anything — so the page has real content
  // at rest with no click needed. The trigger then draws a random
  // [data-luck-card] from the rest, excluding the one just shown where
  // possible so re-clicking feels like a fresh draw, and permanently hides
  // the default card the first time it's clicked.
  function initLuckReveal() {
    document.querySelectorAll("[data-luck-group]").forEach(function (group) {
      var trigger = group.querySelector("[data-luck-trigger]");
      var defaultCard = group.querySelector("[data-luck-default]");
      var cards = Array.prototype.slice.call(group.querySelectorAll("[data-luck-card]"));
      if (!trigger || !cards.length) return;
      var lastIndex = -1;

      trigger.addEventListener("click", function () {
        if (defaultCard) defaultCard.classList.remove("is-visible");
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

  // Scroll-reveal: elements render fully visible by default (no-JS, or JS
  // disabled, always shows the complete page). Only once this function runs
  // do we add "js-animate" to <html>, which is what makes [data-animate]
  // start hidden in CSS — so the hidden state only ever exists when a
  // working observer is about to reveal it again.
  function initScrollReveal() {
    var els = document.querySelectorAll("[data-animate]");
    if (!els.length) return;
    document.documentElement.classList.add("js-animate");

    if ("IntersectionObserver" in window) {
      var observer = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-visible");
              observer.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.15 }
      );
      els.forEach(function (el) { observer.observe(el); });
    } else {
      els.forEach(function (el) { el.classList.add("is-visible"); });
    }
  }

  // Chart bars: plain HTML/CSS (not SVG — SVG text scales with its viewBox
  // and goes illegibly small on a phone). Each [data-chart-bar] ships with
  // its real final width as a % in data-final (so a no-JS view shows the
  // correct, finished chart). When JS runs, we drop it to 0% and animate
  // back up to that same value the first time its chart scrolls into view.
  function initChartBars() {
    var charts = document.querySelectorAll("[data-chart]");
    if (!charts.length) return;
    var done = new WeakSet();

    function animate(chart) {
      if (done.has(chart)) return;
      done.add(chart);
      var bars = chart.querySelectorAll("[data-chart-bar]");
      bars.forEach(function (bar) {
        var final = bar.getAttribute("data-final");
        bar.style.width = "0%";
        requestAnimationFrame(function () {
          requestAnimationFrame(function () {
            bar.style.width = final + "%";
          });
        });
      });
    }

    if ("IntersectionObserver" in window) {
      var observer = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) animate(entry.target);
          });
        },
        { threshold: 0.4 }
      );
      charts.forEach(function (chart) { observer.observe(chart); });
    }
  }

  // Chart hover/focus detail: a [data-chart-tip] hit target (bigger than
  // the visible bar, for an easy hover/tap/keyboard target) swaps the
  // chart's caption text while hovered or focused, reverting on exit.
  function initChartTooltips() {
    document.querySelectorAll("[data-chart]").forEach(function (chart) {
      var card = chart.closest(".chart-card");
      var tooltip = card && card.querySelector("[data-chart-tooltip]");
      if (!tooltip) return;
      var defaultText = tooltip.textContent;
      chart.querySelectorAll("[data-chart-tip]").forEach(function (hit) {
        function show() { tooltip.textContent = hit.getAttribute("data-chart-tip"); }
        function hide() { tooltip.textContent = defaultText; }
        hit.addEventListener("mouseenter", show);
        hit.addEventListener("mouseleave", hide);
        hit.addEventListener("focus", show);
        hit.addEventListener("blur", hide);
      });
    });
  }

  // Accordion: independent expand/collapse per row, animated with the
  // grid-template-rows CSS trick (no JS height measuring needed).
  function initAccordions() {
    document.querySelectorAll("[data-accordion]").forEach(function (acc) {
      acc.querySelectorAll(".accordion__row").forEach(function (row) {
        row.addEventListener("click", function () {
          var open = row.getAttribute("aria-expanded") === "true";
          row.setAttribute("aria-expanded", open ? "false" : "true");
        });
      });
    });
  }

  // Lazy video embed: shows a thumbnail + play button until clicked, so no
  // YouTube script/iframe loads unless the visitor actually wants to watch.
  // Only wires up elements that opt in with [data-video] + [data-video-id]
  // — a plain link-out version (used where an inline embed isn't possible)
  // is untouched by this.
  function initVideoEmbeds() {
    document.querySelectorAll("[data-video]").forEach(function (wrap) {
      function play() {
        var id = wrap.getAttribute("data-video-id");
        if (!id) return;
        var iframe = document.createElement("iframe");
        iframe.src = "https://www.youtube-nocookie.com/embed/" + id + "?autoplay=1&rel=0";
        iframe.title = wrap.getAttribute("data-video-title") || "Video";
        iframe.allow = "autoplay; encrypted-media; picture-in-picture";
        iframe.allowFullscreen = true;
        wrap.innerHTML = "";
        wrap.appendChild(iframe);
      }
      wrap.addEventListener("click", play, { once: true });
      wrap.addEventListener(
        "keydown",
        function (e) {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            play();
          }
        },
        { once: true }
      );
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initNav();
    initCountUp();
    initRevealGroups();
    initLuckReveal();
    initScrollReveal();
    initChartBars();
    initChartTooltips();
    initAccordions();
    initVideoEmbeds();
  });
})();
