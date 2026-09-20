/** Keep the palette aligned with Fusion's fixed or device-following UI theme. */

const paletteDeviceThemeQuery = typeof window.matchMedia === "function"
  ? window.matchMedia("(prefers-color-scheme: dark)")
  : null;
const PALETTE_THEME_STORAGE_KEY = "cableBundler.paletteTheme";
let paletteThemeMode = "fixed";
let paletteActiveTheme = "light";

function applyPaletteTheme(theme, deviceTheme = null) {
  if (!theme) return;
  paletteThemeMode = theme?.mode === "device" ? "device" : "fixed";
  paletteActiveTheme = theme?.active === "dark" ? "dark" : "light";
  const activeTheme = paletteThemeMode === "device" && deviceTheme
    ? deviceTheme
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
    applyPaletteTheme(
      { mode: paletteThemeMode, active: paletteActiveTheme },
      paletteDeviceThemeQuery?.matches ? "dark" : "light",
    );
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
const initialDeviceTheme = paletteDeviceThemeQuery?.matches ? "dark" : "light";
applyPaletteTheme(
  initialPaletteTheme || { mode: "device", active: initialDeviceTheme },
  initialDeviceTheme,
);

if (paletteDeviceThemeQuery?.addEventListener) {
  paletteDeviceThemeQuery.addEventListener("change", handleDeviceThemeChange);
} else if (paletteDeviceThemeQuery?.addListener) {
  paletteDeviceThemeQuery.addListener(handleDeviceThemeChange);
}
