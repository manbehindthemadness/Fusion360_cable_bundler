/** Keep the palette aligned with Fusion's fixed or device-following UI theme. */

const paletteDeviceThemeQuery = typeof window.matchMedia === "function"
  ? window.matchMedia("(prefers-color-scheme: dark)")
  : null;
const PALETTE_THEME_STORAGE_KEY = "wireBundler.paletteTheme";
let paletteThemeMode = "fixed";
let paletteActiveTheme = "light";

function applyPaletteTheme(theme) {
  if (!theme) return;
  paletteThemeMode = theme?.mode === "device" ? "device" : "fixed";
  paletteActiveTheme = theme?.active === "dark" ? "dark" : "light";
  const activeTheme = paletteThemeMode === "device" && paletteDeviceThemeQuery
    ? (paletteDeviceThemeQuery.matches ? "dark" : "light")
    : paletteActiveTheme;
  const root = document.documentElement || document.body;
  root.dataset.theme = activeTheme;
  root.style.colorScheme = activeTheme;
  try {
    window.sessionStorage.setItem(PALETTE_THEME_STORAGE_KEY, JSON.stringify({
      mode: paletteThemeMode,
      active: paletteActiveTheme,
    }));
  } catch (_error) {
    // Theme persistence only avoids a flash while Fusion reconnects the palette.
  }
}

function handleDeviceThemeChange() {
  if (paletteThemeMode === "device") {
    applyPaletteTheme({ mode: paletteThemeMode, active: paletteActiveTheme });
  }
}

let initialPaletteTheme = null;
try {
  initialPaletteTheme = JSON.parse(
    window.sessionStorage.getItem(PALETTE_THEME_STORAGE_KEY) || "null",
  );
} catch (_error) {
  // Fall through to the current device scheme if storage is unavailable or malformed.
}
applyPaletteTheme(initialPaletteTheme || {
  mode: "device",
  active: paletteDeviceThemeQuery?.matches ? "dark" : "light",
});

if (paletteDeviceThemeQuery?.addEventListener) {
  paletteDeviceThemeQuery.addEventListener("change", handleDeviceThemeChange);
} else if (paletteDeviceThemeQuery?.addListener) {
  paletteDeviceThemeQuery.addListener(handleDeviceThemeChange);
}
