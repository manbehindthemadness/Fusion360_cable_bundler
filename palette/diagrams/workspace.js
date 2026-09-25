const BLOCK_DIAGRAM_MIN_SCALE = 0.3;
const BLOCK_DIAGRAM_MAX_SCALE = 2.5;

/** Create an SVG node while mirroring data attributes into its dataset. */
function svgElement(tag, attributes = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attributes).forEach(([name, value]) => {
    node.setAttribute(name, `${value}`);
    if (name.startsWith("data-")) {
      const datasetName = name.slice(5).replace(/-([a-z])/g, (_match, letter) => (
        letter.toUpperCase()
      ));
      node.dataset[datasetName] = `${value}`;
    }
  });
  return node;
}

/**
 * Create a zoomable diagram workspace whose panning matches Fusion navigation.
 */
function createBlockDiagramWorkspace(label, options = {}) {
  const root = document.createElement("div");
  const toolbar = document.createElement("div");
  const redraw = options.onRedraw ? document.createElement("button") : null;
  const zoomOut = document.createElement("button");
  const zoomValue = document.createElement("output");
  const zoomIn = document.createElement("button");
  const actualSize = document.createElement("button");
  const fit = document.createElement("button");
  const viewport = document.createElement("div");
  const stage = document.createElement("div");
  const initialView = options.initialView || {};
  const minimumScale = Number.isFinite(options.minScale)
    ? Math.max(Number.EPSILON, options.minScale)
    : BLOCK_DIAGRAM_MIN_SCALE;
  let scale = Number.isFinite(initialView.scale)
    ? Math.min(BLOCK_DIAGRAM_MAX_SCALE, Math.max(minimumScale, initialView.scale))
    : 1;
  let offsetX = Number.isFinite(initialView.offsetX) ? initialView.offsetX : 0;
  let offsetY = Number.isFinite(initialView.offsetY) ? initialView.offsetY : 0;
  let pan = null;

  root.className = "block-diagram-workspace";
  toolbar.className = "block-diagram-toolbar";
  viewport.className = "block-diagram-viewport";
  viewport.tabIndex = 0;
  viewport.setAttribute("aria-label", label);
  stage.className = "block-diagram-stage";
  if (redraw) {
    redraw.type = "button";
    redraw.textContent = "Redraw";
    redraw.title = "Redraw and fit diagram";
    redraw.setAttribute("aria-label", redraw.title);
  }
  zoomOut.type = "button";
  zoomOut.textContent = "−";
  zoomOut.title = "Zoom out";
  zoomIn.type = "button";
  zoomIn.textContent = "+";
  zoomIn.title = "Zoom in";
  actualSize.type = "button";
  actualSize.textContent = "100%";
  actualSize.title = "Reset zoom";
  fit.type = "button";
  fit.textContent = "Fit";
  fit.title = "Fit diagram";
  zoomValue.className = "block-diagram-zoom";

  const renderTransform = (notify = true) => {
    stage.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;
    zoomValue.value = `${Math.round(scale * 100)}%`;
    zoomValue.textContent = zoomValue.value;
    if (notify && options.onViewChange) options.onViewChange({ scale, offsetX, offsetY });
  };
  const setScale = (nextScale, anchorX = viewport.clientWidth / 2,
    anchorY = viewport.clientHeight / 2) => {
    const clamped = Math.min(BLOCK_DIAGRAM_MAX_SCALE, Math.max(
      minimumScale, nextScale,
    ));
    const localX = (anchorX - offsetX) / scale;
    const localY = (anchorY - offsetY) / scale;
    scale = clamped;
    offsetX = anchorX - localX * scale;
    offsetY = anchorY - localY * scale;
    renderTransform();
  };
  const fitDiagram = () => {
    const width = Math.max(1, Number.isFinite(options.contentSize?.width)
      ? options.contentSize.width : stage.scrollWidth);
    const height = Math.max(1, Number.isFinite(options.contentSize?.height)
      ? options.contentSize.height : stage.scrollHeight);
    const availableWidth = Math.max(1, viewport.clientWidth - 24);
    const availableHeight = Math.max(1, viewport.clientHeight - 24);
    scale = Math.min(1, Math.max(
      minimumScale,
      Math.min(availableWidth / width, availableHeight / height),
    ));
    offsetX = Math.max(12, (viewport.clientWidth - width * scale) / 2);
    offsetY = Math.max(12, (viewport.clientHeight - height * scale) / 2);
    renderTransform();
  };

  zoomOut.addEventListener("click", () => setScale(scale / 1.2));
  zoomIn.addEventListener("click", () => setScale(scale * 1.2));
  actualSize.addEventListener("click", () => {
    scale = 1;
    offsetX = 12;
    offsetY = 12;
    renderTransform();
  });
  fit.addEventListener("click", fitDiagram);
  redraw?.addEventListener("click", options.onRedraw);
  viewport.addEventListener("wheel", (event) => {
    event.preventDefault();
    const bounds = viewport.getBoundingClientRect();
    setScale(
      scale * (event.deltaY < 0 ? 1.12 : 1 / 1.12),
      event.clientX - bounds.left,
      event.clientY - bounds.top,
    );
  }, { passive: false });
  viewport.addEventListener("pointerdown", (event) => {
    if (event.button !== 1 && !(event.button === 0 && options.panWithPrimaryButton?.())) return;
    event.preventDefault();
    pan = { pointerId: event.pointerId, x: event.clientX, y: event.clientY,
      offsetX, offsetY };
    viewport.classList.add("panning");
    viewport.setPointerCapture?.(event.pointerId);
  });
  viewport.addEventListener("pointermove", (event) => {
    if (!pan || pan.pointerId !== event.pointerId) return;
    offsetX = pan.offsetX + event.clientX - pan.x;
    offsetY = pan.offsetY + event.clientY - pan.y;
    renderTransform();
  });
  const stopPan = (event) => {
    if (!pan || pan.pointerId !== event.pointerId) return;
    viewport.releasePointerCapture?.(event.pointerId);
    pan = null;
    viewport.classList.remove?.("panning");
  };
  viewport.addEventListener("pointerup", stopPan);
  viewport.addEventListener("pointercancel", stopPan);

  if (redraw) toolbar.append(redraw);
  toolbar.append(zoomOut, zoomValue, zoomIn, actualSize, fit);
  viewport.append(stage);
  root.append(toolbar, viewport);
  renderTransform(false);
  return { root, stage, fit: fitDiagram, zoomValue, viewport };
}
