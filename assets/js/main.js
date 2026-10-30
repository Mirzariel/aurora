/* AURORA — interaksi situs. JS biasa; konten tetap terbaca bila skrip ini gagal. */
(function () {
  "use strict";

  var root = document.documentElement;
  var doc = document;
  var reduceMQ = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : { matches: false };
  var conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection || {};
  var saveData = !!conn.saveData || /(^|-)2g$/.test(conn.effectiveType || "");
  var isStatic = root.classList.contains("static");
  var hasIO = "IntersectionObserver" in window;

  function $(sel, ctx) { return (ctx || doc).querySelector(sel); }
  function $$(sel, ctx) { return Array.prototype.slice.call((ctx || doc).querySelectorAll(sel)); }
  function motionOK() { return !reduceMQ.matches; }

  /* ---------- Navigasi mobile ---------- */
  var toggle = $(".nav-toggle");
  var navList = $("#nav-list");
  function setNav(open) {
    root.classList.toggle("nav-open", open);
    if (toggle) {
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? "Tutup menu" : "Buka menu");
    }
  }
  if (toggle && navList) {
    toggle.addEventListener("click", function () { setNav(!root.classList.contains("nav-open")); });
    navList.addEventListener("click", function (e) { if (e.target.closest("a")) setNav(false); });
    doc.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && root.classList.contains("nav-open")) { setNav(false); toggle.focus(); }
    });
    window.addEventListener("resize", function () { if (window.innerWidth > 960) setNav(false); });
  }

  /* ---------- Scroll: header, parallax ---------- */
  var header = $(".site-header");
  var bands = $$("[data-parallax]");
  var ticking = false;
  function onScroll() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(function () {
      ticking = false;
      if (header) header.classList.toggle("is-solid", window.scrollY > 40);
      if (!motionOK()) return;
      var vh = window.innerHeight;
      for (var i = 0; i < bands.length; i++) {
        var r = bands[i].getBoundingClientRect();
        if (r.bottom < -100 || r.top > vh + 100) continue;
        var p = (r.top + r.height / 2 - vh / 2) / (vh / 2 + r.height / 2); /* -1..1 */
        var img = bands[i].querySelector(".band-img");
        if (img) img.style.transform = "translate3d(0," + (p * -r.height * 0.1).toFixed(1) + "px,0)";
      }
    });
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);
  onScroll();

  /* ---------- Scroll-reveal ---------- */
  var reveals = $$(".reveal");
  function showAll() { reveals.forEach(function (el) { el.classList.add("is-in"); }); }
  if (isStatic || !hasIO || !motionOK()) {
    showAll();
  } else {
    var rio = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("is-in"); rio.unobserve(en.target); }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
    reveals.forEach(function (el) { rio.observe(el); });
  }

  /* ---------- Tautan aktif di navigasi ---------- */
  if (hasIO && navList) {
    var links = $$("a[href^='#']", navList);
    var map = {};
    links.forEach(function (a) { map[a.getAttribute("href").slice(1)] = a; });
    var sio = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        links.forEach(function (a) { a.removeAttribute("aria-current"); });
        var a = map[en.target.id];
        if (a) a.setAttribute("aria-current", "true");
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    Object.keys(map).forEach(function (id) { var s = doc.getElementById(id); if (s) sio.observe(s); });
  }

  /* ---------- Bintang (canvas ringan) ---------- */
  var canvas = $("#stars");
  if (canvas && canvas.getContext) {
    var ctx = canvas.getContext("2d");
    var stars = [];
    var W = 0, H = 0, dpr = 1, raf = 0, visible = true, lastT = 0;

    var build = function () {
      var r = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = Math.max(1, Math.round(r.width)); H = Math.max(1, Math.round(r.height));
      canvas.width = W * dpr; canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      var n = Math.min(110, Math.round(W * H / 12000));
      stars = [];
      for (var i = 0; i < n; i++) {
        stars.push({
          x: Math.random() * W,
          y: Math.random() * H * 0.72,
          r: Math.random() < 0.12 ? 1.5 : Math.random() * 0.8 + 0.4,
          ph: Math.random() * Math.PI * 2,
          sp: Math.random() * 1.2 + 0.4,
          mint: Math.random() < 0.4
        });
      }
    };
    var draw = function (t) {
      ctx.clearRect(0, 0, W, H);
      var live = motionOK();
      for (var i = 0; i < stars.length; i++) {
        var s = stars[i];
        var a = live ? 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(t / 1000 * s.sp + s.ph)) : 0.7;
        ctx.globalAlpha = a * 0.85;
        ctx.fillStyle = s.mint ? "#bff3d6" : "#f2fff8";
        ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, 6.2832); ctx.fill();
      }
      ctx.globalAlpha = 1;
    };
    var loop = function (t) {
      raf = 0;
      if (!visible || !motionOK()) return;
      if (t - lastT > 60) { lastT = t; draw(t); }
      raf = window.requestAnimationFrame(loop);
    };
    var kick = function () {
      if (raf) return;
      if (visible && motionOK()) raf = window.requestAnimationFrame(loop); else draw(0);
    };
    build(); draw(0); kick();
    var rt;
    window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(function () { build(); draw(0); kick(); }, 200); });
    if (hasIO) {
      new IntersectionObserver(function (en) { visible = en[0].isIntersecting; if (visible) kick(); }).observe(canvas);
    }
    if (reduceMQ.addEventListener) reduceMQ.addEventListener("change", function () { draw(0); kick(); });
  }

  /* ---------- Video: hero + lora-journey ---------- */
  function setupVideo(video, box, opts) {
    if (!video) return;
    var btn = box ? $("[data-media-toggle]", box) : null;
    var label = btn ? $("span", btn) : null;
    var failed = false;
    var userPaused = false;
    var inView = true;
    var autoOK = motionOK() && !saveData;

    function sync() {
      if (!btn) return;
      var paused = video.paused;
      btn.setAttribute("data-state", paused ? "paused" : "playing");
      if (label) label.textContent = (paused ? "Putar " : "Jeda ") + opts.noun;
    }
    function reveal() { if (!failed) { video.classList.add("is-ready"); if (opts.onReady) opts.onReady(); } }
    function fail() {
      failed = true;
      video.classList.remove("is-ready");
      if (opts.onFail) opts.onFail();
      if (btn) btn.hidden = true;
      try { video.pause(); } catch (e) {}
    }
    function play() {
      var p;
      try { p = video.play(); } catch (e) { return; }
      if (p && p.catch) p.catch(function () { sync(); });
    }

    var srcs = $$("source", video);
    if (srcs.length) srcs[srcs.length - 1].addEventListener("error", fail);
    video.addEventListener("error", fail);
    video.addEventListener("playing", function () { reveal(); sync(); });
    video.addEventListener("pause", sync);
    video.addEventListener("play", sync);
    video.addEventListener("loadedmetadata", function () { if (btn && !failed) btn.hidden = false; sync(); });

    if (autoOK) {
      play();
    } else {
      /* Gerak dikurangi / hemat data: tampilkan poster saja, putar hanya bila pengguna meminta. */
      var poster = video.getAttribute("poster");
      if (poster) { var im = new Image(); im.onload = reveal; im.src = poster; }
    }

    if (btn) {
      btn.addEventListener("click", function () {
        if (video.paused) { userPaused = false; play(); } else { userPaused = true; video.pause(); }
        sync();
      });
    }

    if (hasIO && box) {
      new IntersectionObserver(function (en) {
        inView = en[0].isIntersecting;
        if (failed) return;
        if (!inView) { if (!video.paused) video.pause(); }
        else if (autoOK && !userPaused && video.paused && motionOK()) play();
      }, { threshold: 0.15 }).observe(box);
    }
    if (reduceMQ.addEventListener) {
      reduceMQ.addEventListener("change", function () {
        if (reduceMQ.matches && !video.paused) video.pause();
      });
    }
    doc.addEventListener("visibilitychange", function () {
      if (doc.hidden && !video.paused) video.pause();
      else if (!doc.hidden && autoOK && !userPaused && inView && video.paused && !failed && motionOK()) play();
    });
    sync();
  }
  var heroEl = $(".hero");
  setupVideo($("#hero-video"), $("[data-media='hero']"), {
    noun: "animasi latar",
    onReady: function () { if (heroEl) heroEl.classList.add("video-on"); },
    onFail: function () { if (heroEl) heroEl.classList.remove("video-on"); }
  });
  setupVideo($("#journey-video"), $("[data-media='journey']"), { noun: "animasi" });

  /* ---------- Video YouTube: fasad. Tidak ada permintaan ke YouTube sebelum tombol ditekan. ---------- */
  var yt = $("[data-youtube-id]");
  if (yt) {
    var ytId = (yt.getAttribute("data-youtube-id") || "").trim();
    var ytStage = $(".yt-stage", yt);
    var ytPlay = $(".yt-play", yt);
    var ytSoon = $(".yt-soon", yt);
    if (/^[A-Za-z0-9_-]{11}$/.test(ytId) && ytStage && ytPlay) {
      if (ytSoon) ytSoon.hidden = true;
      ytPlay.hidden = false;
      ytPlay.addEventListener("click", function () {
        var f = doc.createElement("iframe");
        f.src = "https://www.youtube-nocookie.com/embed/" + ytId + "?autoplay=1&rel=0";
        f.title = "Video AURORA";
        f.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
        f.allowFullscreen = true;
        f.referrerPolicy = "strict-origin-when-cross-origin";
        ytStage.innerHTML = "";
        ytStage.appendChild(f);
      });
    }
  }
})();
