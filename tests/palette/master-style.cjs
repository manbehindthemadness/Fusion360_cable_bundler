/** Focused palette regression suite. */
/* global require, __dirname */
const { assert, join, readFileSync, test } = require('./support.cjs');

test('master relationship viewport uses a distinct darker backdrop', () => {
  const styles = readFileSync(join(__dirname, '..', '..', 'palette', 'styles.css'), 'utf8');
  assert.match(styles, /\.relationship-map-viewport \{[^}]*background: #dfe5ea;/s);
});
