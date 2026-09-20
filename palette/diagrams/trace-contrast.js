/** Contrast-aware SVG trace halos that preserve authoritative material colors. */

const TRACE_MINIMUM_CONTRAST_RATIO = 3;
const TRACE_LIGHT_CANVAS_COLOR = "#dfe5ea";
const TRACE_DARK_CANVAS_COLOR = "#1b2025";

function traceRgb(hexColor) {
  const match = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(hexColor || "");
  if (!match) return null;
  const digits = match[1].length === 3
    ? [...match[1]].map((digit) => `${digit}${digit}`).join("")
    : match[1];
  return [0, 2, 4].map((offset) => Number.parseInt(digits.slice(offset, offset + 2), 16));
}

function traceRelativeLuminance(hexColor) {
  const rgb = traceRgb(hexColor);
  if (!rgb) return null;
  const channels = rgb.map((value) => {
    const channel = value / 255;
    return channel <= 0.04045
      ? channel / 12.92
      : ((channel + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function traceContrastRatio(leftColor, rightColor) {
  const left = traceRelativeLuminance(leftColor);
  const right = traceRelativeLuminance(rightColor);
  if (left === null || right === null) return 1;
  return (Math.max(left, right) + 0.05) / (Math.min(left, right) + 0.05);
}

function traceCanvasHaloClasses(traceColor) {
  const classes = ["trace-contrast-halo"];
  if (traceContrastRatio(traceColor, TRACE_LIGHT_CANVAS_COLOR)
      < TRACE_MINIMUM_CONTRAST_RATIO) {
    classes.push("trace-contrast-light-theme");
  }
  if (traceContrastRatio(traceColor, TRACE_DARK_CANVAS_COLOR)
      < TRACE_MINIMUM_CONTRAST_RATIO) {
    classes.push("trace-contrast-dark-theme");
  }
  return classes;
}

/** Append a theme-aware halo and then the exact material-colored trace. */
function appendContrastTrace(parent, attributes, options) {
  const haloClasses = traceCanvasHaloClasses(attributes.stroke);
  const haloAttributes = {
    class: haloClasses.join(" "),
    d: attributes.d,
    "stroke-width": options.haloWidth,
    "aria-hidden": "true",
  };
  ["data-wire-group-id", "data-wire-group-ids"].forEach((name) => {
    if (attributes[name]) haloAttributes[name] = attributes[name];
  });
  const halo = svgElement("path", haloAttributes);
  const trace = svgElement("path", attributes);
  parent.append(halo, trace);
  return trace;
}
