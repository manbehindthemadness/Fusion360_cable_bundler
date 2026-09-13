/** Focused palette regression suite. */
/* global require */
const { assert, descendants, palette, test } = require('./support.cjs');

test('damaged harness editor offers confirmed component deletion', () => {
  const { context, calls } = palette();
  context.window.confirm = () => true;
  context.renderEditor({
    componentName: 'Broken Harness',
    deletionToken: 'current-token',
    error: 'Stored definition is malformed.',
    status: 'damaged',
  });

  const remove = descendants(
    context.ui.editor,
    (node) => node.textContent === 'Delete damaged harness',
  )[0];
  assert.ok(remove);
  remove.events.click();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].action, 'delete_damaged_harness');
  assert.equal(calls[0].payload.deletionToken, 'current-token');
});
