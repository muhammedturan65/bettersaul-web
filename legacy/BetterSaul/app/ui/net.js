(function () {
  var canvas = document.getElementById("nn");
  if (!canvas) return;
  var ctx = canvas.getContext("2d");
  var nodes = [];
  var stars = [];
  var w = 0;
  var h = 0;
  var mouse = { x: -9999, y: -9999 };
  var COUNT = 42;
  var STARS = 140;
  var LINK = 140;

  function cssRgb(name, fallback) {
    var raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return raw || fallback;
  }

  function resize() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = window.innerWidth;
    h = window.innerHeight;
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (!nodes.length) spawn();
  }

  function spawn() {
    nodes = [];
    stars = [];
    for (var i = 0; i < COUNT; i++) {
      nodes.push({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.28,
        vy: (Math.random() - 0.5) * 0.28,
        r: 1.1 + Math.random() * 1.7,
        pulse: Math.random() * Math.PI * 2,
      });
    }
    for (var s = 0; s < STARS; s++) {
      stars.push({
        x: Math.random() * w,
        y: Math.random() * h,
        r: 0.4 + Math.random() * 1.35,
        pulse: Math.random() * Math.PI * 2,
        speed: 0.012 + Math.random() * 0.03,
      });
    }
  }

  var last = 0;
  function tick(now) {
    if (now - last < 48) { requestAnimationFrame(tick); return; }
    last = now;
    var accent = cssRgb("--nn-accent", "201, 162, 39");
    var bright = cssRgb("--nn-accent-dark", "232, 197, 71");
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, w, h);

    var i, j, a, b, dx, dy, d, alpha, star, tw;
    for (i = 0; i < stars.length; i++) {
      star = stars[i];
      star.pulse += star.speed;
      tw = 0.25 + 0.75 * Math.abs(Math.sin(star.pulse));
      ctx.beginPath();
      ctx.fillStyle = "rgba(255,255,255," + (0.18 + tw * 0.72) + ")";
      ctx.arc(star.x, star.y, star.r * (0.7 + tw * 0.5), 0, Math.PI * 2);
      ctx.fill();
    }
    for (i = 0; i < nodes.length; i++) {
      a = nodes[i];
      a.x += a.vx;
      a.y += a.vy;
      a.pulse += 0.018;
      if (a.x < 0 || a.x > w) a.vx *= -1;
      if (a.y < 0 || a.y > h) a.vy *= -1;
      dx = a.x - mouse.x;
      dy = a.y - mouse.y;
      d = Math.hypot(dx, dy);
      if (d < 180 && d > 1) {
        a.vx -= (dx / d) * 0.018;
        a.vy -= (dy / d) * 0.018;
      }
      var sp = Math.hypot(a.vx, a.vy);
      if (sp > 0.55) {
        a.vx *= 0.96;
        a.vy *= 0.96;
      }
    }

    for (i = 0; i < nodes.length; i++) {
      a = nodes[i];
      for (j = i + 1; j < nodes.length; j++) {
        b = nodes[j];
        dx = a.x - b.x;
        dy = a.y - b.y;
        d = Math.hypot(dx, dy);
        if (d < LINK) {
          alpha = (1 - d / LINK) * 0.42;
          ctx.strokeStyle = "rgba(" + accent + "," + alpha + ")";
          ctx.lineWidth = 0.7;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }
    }

    for (i = 0; i < nodes.length; i++) {
      a = nodes[i];
      var glow = 0.4 + 0.4 * Math.sin(a.pulse);
      ctx.beginPath();
      ctx.fillStyle = "rgba(" + bright + "," + (glow * 0.22) + ")";
      ctx.arc(a.x, a.y, a.r * 4.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.fillStyle = "rgba(" + accent + "," + (0.55 + glow * 0.4) + ")";
      ctx.arc(a.x, a.y, a.r, 0, Math.PI * 2);
      ctx.fill();
    }
    requestAnimationFrame(tick);
  }

  window.addEventListener("resize", resize);
  window.addEventListener("mousemove", function (ev) {
    mouse.x = ev.clientX;
    mouse.y = ev.clientY;
  });
  resize();
  requestAnimationFrame(tick);
})();
