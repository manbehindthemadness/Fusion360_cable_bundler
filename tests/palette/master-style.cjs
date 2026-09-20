/** Focused palette regression suite. */
/* global require, __dirname */
const { assert, readPaletteStyles, test } = require('./support.cjs');

test('master relationship viewport uses a distinct darker backdrop', () => {
  const styles = readPaletteStyles();
  assert.match(styles, /\.relationship-map-viewport \{[^}]*background: var\(--canvas\);/s);
});

test('palette defines fixed light and dark semantic color sets', () => {
  const styles = readPaletteStyles();

  assert.match(styles, /:root \{[^}]*color-scheme: light;[^}]*--surface: #fff;/s);
  assert.match(
    styles,
    /:root\[data-theme="dark"\] \{[^}]*color-scheme: dark;[^}]*--surface: #2b3136;/s,
  );
  assert.doesNotMatch(styles, /\.wire-trace[^,{]*\{[^}]*stroke:/s);
});

test('low-contrast trace halos switch neutrally with the palette theme', () => {
  const styles = readPaletteStyles();

  assert.match(styles, /:root \{[^}]*--trace-halo: #242a2f;/s);
  assert.match(styles, /:root\[data-theme="dark"\] \{[^}]*--trace-halo: #eef2f5;/s);
  assert.match(
    styles,
    /:root\[data-theme="dark"\] \.trace-contrast-halo\.trace-contrast-dark-theme[^}]*stroke: var\(--trace-halo\);/s,
  );
});

test('Wire Details fills most of the window and uses the shared diagram workspace', () => {
  const styles = readPaletteStyles();
  assert.match(styles, /\.wire-group-details-popup \{[^}]*width: 90vw;[^}]*height: 90vh;/s);
  assert.match(
    styles,
    /\.block-diagram-workspace \{[^}]*grid-template-rows: auto minmax\(0, 1fr\);/s,
  );
  assert.match(styles, /\.block-diagram-viewport \{[^}]*overflow: hidden;/s);
  assert.match(styles, /\.block-diagram-stage \{[^}]*transform-origin: 0 0;/s);
  assert.match(styles, /\.wire-group-route-link \{[^}]*fill: none;[^}]*stroke-linecap: round;/s);
});

test('Route Editor uses three independently scrollable columns', () => {
  const styles = readPaletteStyles();
  const columnPattern = [
    String.raw`\.create-wires-layout \{[^}]*grid-template-columns: `,
    String.raw`minmax\(0, 1fr\) minmax\(0, 2fr\) minmax\(0, 1fr\);`,
  ].join('');
  assert.match(
    styles,
    new RegExp(columnPattern, 's'),
  );
  assert.match(styles, /\.create-wires-column \{[^}]*overflow-y: auto;/s);
  assert.match(
    styles,
    /\.create-wires-end-pool \{[^}]*grid-template-rows: auto minmax\(0, 1fr\);/s,
  );
  assert.match(styles, /\.create-wires-end-list \{[^}]*min-height: 0;/s);
  assert.match(styles, /\.create-wires-assignment-content \{[^}]*min-height: 0;/s);
  assert.doesNotMatch(
    styles,
    /\.create-wires-assignment-content \{[^}]*min-height: 100%;/s,
  );
  assert.match(
    styles,
    /\.create-wires-assignment-row \{[^}]*grid-template-columns: minmax\(0, 1fr\) 12px minmax\(0, 1fr\);/s,
  );
  assert.match(
    styles,
    /\.create-wires-assignment-row\[data-complete="true"\][^{]*\{[^}]*background: var\(--accent\);/s,
  );
  assert.match(
    styles,
    /\.create-wires-assignment-slot\[data-drop="slot"\][^{]*\{[^}]*outline: 2px solid var\(--accent\);/s,
  );
  assert.match(
    styles,
    /\.create-wires-end-card\[data-drop="swap"\][^{]*\{[^}]*outline: 2px solid var\(--accent\);/s,
  );
  assert.doesNotMatch(
    styles,
    /\.create-wires-assignment-slot \.create-wires-end-card small \{[^}]*display: none;/s,
  );
});

test('long wire-end names expand horizontally instead of wrapping', () => {
  const styles = readPaletteStyles();

  assert.match(
    styles,
    /\.relationship-end-entry strong \{[^}]*white-space: nowrap;/s,
  );
});

test('master context submenus open only while their parent is hovered', () => {
  const styles = readPaletteStyles();

  assert.match(
    styles,
    /\.context-menu-branch:hover > \.context-menu-submenu \{[^}]*display: grid;[^}]*grid-template-columns: minmax\(0, 1fr\);/s,
  );
  assert.doesNotMatch(styles, /context-menu-branch:focus-within/);
});

test('context menus size to their contents without fixed minimum widths', () => {
  const styles = readPaletteStyles();

  assert.match(
    styles,
    /\.relationship-map-context-menu \{[^}]*width: max-content;/s,
  );
  assert.doesNotMatch(styles, /\.relationship-map-context-menu \{[^}]*min-width:/s);
  assert.doesNotMatch(styles, /\.context-menu-submenu \{[^}]*min-width:/s);
});
