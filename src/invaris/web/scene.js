(() => {
  "use strict";

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let paused = reducedMotion.matches;
  let disposeScene = () => {};
  let dialog = null;
  let returnFocus = null;

  function updateMotionControls() {
    document.body.dataset.motion = paused ? "paused" : "running";
    document.querySelectorAll("[data-action='toggle-motion']").forEach(control => {
      control.textContent = reducedMotion.matches ? "Reduced motion" : paused ? "Play motion" : "Pause motion";
      control.disabled = reducedMotion.matches;
      control.setAttribute("aria-pressed", String(paused));
    });
  }

  function createScene(canvas) {
    const context = canvas.getContext("2d");
    if (!context) return () => {};
    const container = canvas.parentElement;
    let width = 0;
    let height = 0;
    let frameId = 0;
    let lastFrame = 0;
    let elapsed = 0;
    let previousTime = 0;
    let pointerHorizontal = 0;
    let pointerVertical = 0;
    let focused = false;
    const vertices = [];
    const edges = [];
    for (const horizontal of [-1, 1]) {
      for (const vertical of [-1, 1]) {
        for (const depth of [-1, 1]) vertices.push([horizontal, vertical, depth]);
      }
    }
    vertices.forEach((point, index) => vertices.slice(index + 1).forEach((other, offset) => {
      if (point.filter((coordinate, axis) => coordinate !== other[axis]).length === 1) {
        edges.push([index, index + offset + 1]);
      }
    }));

    function project(point, yaw, pitch, scale) {
      const rotatedHorizontal = point[0] * Math.cos(yaw) - point[2] * Math.sin(yaw);
      const rotatedDepth = point[0] * Math.sin(yaw) + point[2] * Math.cos(yaw);
      const rotatedVertical = point[1] * Math.cos(pitch) - rotatedDepth * Math.sin(pitch);
      const finalDepth = point[1] * Math.sin(pitch) + rotatedDepth * Math.cos(pitch);
      const perspective = 5 / (5 + finalDepth);
      return { horizontal: width / 2 + rotatedHorizontal * scale * perspective,
        vertical: height / 2 + rotatedVertical * scale * perspective, depth: finalDepth };
    }

    function path(points, color, lineWidth, opacity = 1) {
      context.beginPath();
      points.forEach((point, index) => {
        if (index === 0) context.moveTo(point.horizontal, point.vertical);
        else context.lineTo(point.horizontal, point.vertical);
      });
      context.strokeStyle = color;
      context.lineWidth = lineWidth;
      context.globalAlpha = opacity;
      context.stroke();
      context.globalAlpha = 1;
    }

    function draw() {
      context.clearRect(0, 0, width, height);
      const scale = Math.min(width, height) * 0.205;
      const yaw = 0.66 + elapsed * 0.00007 + pointerHorizontal * 0.15;
      const pitch = -0.35 + Math.sin(elapsed * 0.00014) * 0.045 + pointerVertical * 0.1;
      const glow = context.createRadialGradient(width / 2, height / 2, 0, width / 2, height / 2, scale * 2.3);
      glow.addColorStop(0, "rgba(148,243,189,0.13)");
      glow.addColorStop(1, "rgba(148,243,189,0)");
      context.fillStyle = glow;
      context.fillRect(0, 0, width, height);
      for (const radius of [1.9, 2.12]) {
        const orbit = [];
        for (let index = 0; index <= 96; index += 1) {
          const angle = index / 96 * Math.PI * 2;
          orbit.push(project([Math.cos(angle) * radius, 0.1, Math.sin(angle) * radius], yaw, pitch, scale));
        }
        path(orbit, "#b7ddd0", 0.7, 0.13);
      }
      for (const layer of [1.05, 0.78, 0.52]) {
        const corners = vertices.map(point => project(point.map(coordinate => coordinate * layer), yaw, pitch, scale));
        edges.forEach(([start, end]) => path([corners[start], corners[end]], "#b7f4cb", layer === 1.05 ? 1.4 : 0.7,
          0.28 + (2 - (corners[start].depth + corners[end].depth) / 2) * 0.13));
        if (layer === 1.05) corners.forEach(point => {
          context.beginPath();
          context.arc(point.horizontal, point.vertical, 2.4, 0, Math.PI * 2);
          context.fillStyle = "#caffd7";
          context.fill();
        });
      }
      for (const strand of [0, 1]) {
        const points = [];
        for (let index = 0; index <= 120; index += 1) {
          const progress = index / 120;
          const angle = progress * Math.PI * 3.2 + strand * Math.PI + elapsed * 0.00015;
          points.push(project([Math.cos(angle) * 1.5, (progress - 0.5) * 3.5,
            Math.sin(angle) * 1.5], yaw, pitch, scale));
        }
        path(points, strand === 0 ? "#b1fac3" : "#a5c2e2", 1.2, 0.45);
        for (let index = 0; index < 5; index += 1) {
          const progress = ((index / 5 + elapsed * 0.000065) % 1);
          const point = points[Math.floor(progress * 120)];
          context.beginPath();
          context.arc(point.horizontal, point.vertical, 2.7, 0, Math.PI * 2);
          context.fillStyle = strand === 0 ? "#cfff9b" : "#c3dbf5";
          context.shadowColor = context.fillStyle;
          context.shadowBlur = 9;
          context.fill();
          context.shadowBlur = 0;
        }
      }
      const middle = project([0, 0, 0], yaw, pitch, scale);
      context.fillStyle = "#dbffe7";
      context.font = "500 11px Consolas, monospace";
      context.textAlign = "center";
      context.fillText("INVARIANT", middle.horizontal, middle.vertical + 4);
    }

    function resize() {
      const bounds = canvas.getBoundingClientRect();
      width = Math.max(1, bounds.width);
      height = Math.max(1, bounds.height);
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(width * pixelRatio);
      canvas.height = Math.round(height * pixelRatio);
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
      draw();
    }

    function frame(time) {
      frameId = 0;
      if (!paused && !document.hidden && focused && time - lastFrame >= 32) {
        elapsed += previousTime ? Math.min(time - previousTime, 64) : 0;
        previousTime = time;
        lastFrame = time;
        draw();
      } else if (paused || document.hidden || !focused) previousTime = 0;
      if (!paused && !document.hidden && focused) frameId = requestAnimationFrame(frame);
    }

    function resume() {
      if (frameId) cancelAnimationFrame(frameId);
      frameId = 0;
      previousTime = 0;
      if (!paused && !document.hidden && focused) frameId = requestAnimationFrame(frame);
      else draw();
    }

    function pointer(event) {
      if (paused || event.pointerType === "touch") return;
      const bounds = container.getBoundingClientRect();
      pointerHorizontal = (event.clientX - bounds.left) / bounds.width - 0.5;
      pointerVertical = (event.clientY - bounds.top) / bounds.height - 0.5;
    }

    function leave() { pointerHorizontal = 0; pointerVertical = 0; }
    const resizeObserver = new ResizeObserver(resize);
    const intersectionObserver = new IntersectionObserver(entries => {
      focused = entries[0]?.isIntersecting === true;
      resume();
    }, { threshold: 0.05 });
    resizeObserver.observe(canvas);
    intersectionObserver.observe(canvas);
    container.addEventListener("pointermove", pointer);
    container.addEventListener("pointerleave", leave);
    document.addEventListener("visibilitychange", resume);
    document.addEventListener("invaris:motion", resume);
    resize();
    return () => {
      cancelAnimationFrame(frameId);
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      container.removeEventListener("pointermove", pointer);
      container.removeEventListener("pointerleave", leave);
      document.removeEventListener("visibilitychange", resume);
      document.removeEventListener("invaris:motion", resume);
    };
  }

  function mount(root) {
    disposeScene();
    const disposers = [...root.querySelectorAll("canvas[data-invariant-scene]")].map(createScene);
    disposeScene = () => disposers.forEach(dispose => dispose());
    updateMotionControls();
  }

  function toggleMotion() {
    if (reducedMotion.matches) return;
    paused = !paused;
    updateMotionControls();
    document.dispatchEvent(new Event("invaris:motion"));
  }

  function openCommandPalette(items, navigate) {
    if (dialog?.open) return;
    returnFocus = document.activeElement;
    dialog = document.createElement("dialog");
    dialog.className = "command-dialog";
    dialog.setAttribute("aria-label", "Navigate Invaris");
    const header = document.createElement("div");
    header.className = "command-header";
    const input = document.createElement("input");
    input.type = "search";
    input.placeholder = "Go to a page or find a run…";
    input.setAttribute("aria-label", "Search pages and recorded runs");
    const close = document.createElement("button");
    close.type = "button";
    close.className = "command-close";
    close.textContent = "Esc";
    close.setAttribute("aria-label", "Close navigation");
    const list = document.createElement("div");
    list.className = "command-list";
    const hint = document.createElement("p");
    hint.className = "command-hint";
    hint.textContent = "Navigation only. Running an agent always requires separate approval.";
    let highlighted = 0;
    let visible = [];

    function drawResults() {
      visible = items.filter(item => (item.label + " " + item.detail).toLowerCase().includes(input.value.toLowerCase())).slice(0, 12);
      highlighted = Math.min(highlighted, Math.max(0, visible.length - 1));
      list.replaceChildren();
      if (!visible.length) {
        const empty = document.createElement("p");
        empty.className = "command-empty";
        empty.textContent = "No matching pages or recorded runs.";
        list.append(empty);
      }
      visible.forEach((item, index) => {
        const result = document.createElement("button");
        result.type = "button";
        result.className = "command-result" + (index === highlighted ? " highlighted" : "");
        const name = document.createElement("strong");
        name.textContent = item.label;
        const detail = document.createElement("span");
        detail.textContent = item.detail;
        result.append(name, detail);
        result.addEventListener("click", () => { dialog.close(); navigate(item.path); });
        list.append(result);
      });
    }

    input.addEventListener("input", () => { highlighted = 0; drawResults(); });
    input.addEventListener("keydown", event => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        highlighted = Math.max(0, Math.min(visible.length - 1, highlighted + (event.key === "ArrowDown" ? 1 : -1)));
        drawResults();
        list.children[highlighted]?.scrollIntoView({ block: "nearest" });
      } else if (event.key === "Enter" && visible[highlighted]) {
        event.preventDefault();
        const selected = visible[highlighted];
        dialog.close();
        navigate(selected.path);
      }
    });
    close.addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener("close", () => { dialog.remove(); dialog = null; if (returnFocus?.isConnected) returnFocus.focus(); });
    header.append(input, close);
    dialog.append(header, list, hint);
    document.body.append(dialog);
    drawResults();
    dialog.showModal();
    input.focus();
  }

  reducedMotion.addEventListener("change", () => {
    paused = reducedMotion.matches;
    updateMotionControls();
    document.dispatchEvent(new Event("invaris:motion"));
  });
  window.addEventListener("pagehide", () => disposeScene());
  window.addEventListener("pageshow", event => { if (event.persisted) mount(document.getElementById("app")); });
  function transition(update) {
    if (!document.startViewTransition || paused || document.hidden) { update(); return; }
    const visualTransition = document.startViewTransition(update);
    visualTransition.finished.catch(() => {});
  }

  window.InvarisVisuals = { mount, toggleMotion, openCommandPalette, transition };
})();
