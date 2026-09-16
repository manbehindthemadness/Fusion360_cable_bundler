/** Focused palette regression suite. */
/* global require, __dirname */
const { assert, join, readFileSync, test } = require('./support.cjs');

test('master relationship viewport uses a distinct darker backdrop', () => {
  const styles = readFileSync(join(__dirname, '..', '..', 'palette', 'styles.css'), 'utf8');
  assert.match(styles, /\.relationship-map-viewport \{[^}]*background: #dfe5ea;/s);
});

test('Wire Details fills most of the window and uses the shared diagram workspace', () => {
  const styles = readFileSync(join(__dirname, '..', '..', 'palette', 'styles.css'), 'utf8');
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
  const styles = readFileSync(join(__dirname, '..', '..', 'palette', 'styles.css'), 'utf8');
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
