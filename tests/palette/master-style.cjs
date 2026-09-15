/** Focused palette regression suite. */
/* global require, __dirname */
const { assert, join, readFileSync, test } = require('./support.cjs');

test('master relationship viewport uses a distinct darker backdrop', () => {
  const styles = readFileSync(join(__dirname, '..', '..', 'palette', 'styles.css'), 'utf8');
  assert.match(styles, /\.relationship-map-viewport \{[^}]*background: #dfe5ea;/s);
});

test('Create Wires uses three independently scrollable columns', () => {
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
  assert.doesNotMatch(
    styles,
    /\.create-wires-assignment-slot \.create-wires-end-card small \{[^}]*display: none;/s,
  );
});
