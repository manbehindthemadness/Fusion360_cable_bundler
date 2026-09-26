/** Contact rendering, orientation, and label regressions. */
const { assert, contactItem, descendants, palette, readPaletteStyles, test } = require('./support.cjs');

test('Interface contacts keep positions within orientation clusters', () => {
  const { context } = palette();
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, [
    { contactId: 'a', kind: 'profile', name: 'A', linked: true,
      normal: [0, 0, 1], loops: [[[0, 0, 0], [10, 0, 0], [10, 10, 0]]] },
    { contactId: 'b', kind: 'face', name: 'B', linked: true,
      normal: [0, 0, 1], loops: [[[30, 0, 0], [40, 0, 0], [40, 10, 0]]] },
    { contactId: 'c', kind: 'face', name: 'C', linked: true,
      normal: [1, 0, 0], loops: [[[0, 0, 0], [0, 10, 0], [0, 10, 10]]] },
  ]);
  const svg = diagram.contactState.svg;
  assert.equal(svg.children.length, 2);
  const firstPaths = descendants(svg.children[0], (node) => node.tag === 'path');
  assert.equal(firstPaths.length, 2);
  const firstX = Number(firstPaths[0].attributes.d.match(/M([\d.]+)/)[1]);
  const secondX = Number(firstPaths[1].attributes.d.match(/M([\d.]+)/)[1]);
  const firstLoop = diagram.contactState.items[0].loops[0];
  const padWidth = Math.abs(firstLoop[1][0] - firstLoop[0][0]);
  assert.equal(Math.abs(secondX - firstX) / padWidth, 3);
  assert.equal(descendants(svg.children[1], (node) => node.tag === 'path').length, 1);
});

test('Opposing parallel faces form separate orientations even when their outlines overlap', () => {
  const { context } = palette();
  const diagram = context.document.createElement('div');
  const outline = [[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0]];
  context.renderInterfaceContacts(diagram, [
    { contactId: 'top', kind: 'face', name: 'Top', linked: true,
      normal: [0, 0, 1], loops: [outline] },
    { contactId: 'bottom', kind: 'face', name: 'Bottom', linked: true,
      normal: [0, 0, -1], loops: [outline.map(([x, y]) => [x, y, -10])] },
  ]);
  const svg = diagram.contactState.svg;
  assert.equal(svg.children.length, 2);
  assert.deepEqual(svg.children.map((group) => descendants(group, (node) => (
    node.className === 'interface-contact-item'
  )).map((item) => item.dataset.contactId)), [['top'], ['bottom']]);
  assert.equal(descendants(svg, (node) => node.tag === 'path').length, 2);
});

test('Value and Pin appear inside a contact with room for two lines', () => {
  const { context } = palette();
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, [{
    contactId: 'pad-1', kind: 'face', name: 'J5.2', assignedName: 'J5.2', pin: 'P7', linked: true,
    normal: [0, 0, 1], loops: [[[0, 0, 0], [3, 0, 0], [3, 1, 0], [0, 1, 0]]],
  }]);
  const labels = descendants(diagram.contactState.svg, (node) => (
    node.className === 'interface-contact-label'
  ));
  assert.equal(labels.length, 2);
  assert.equal(labels[0].textContent, 'J5.2');
  assert.equal(labels[1].textContent, 'Pin P7');
  assert.ok(Number(labels[0].attributes.y) < Number(labels[1].attributes.y));
  const actualSize = descendants(diagram, (node) => node.title === 'Reset zoom')[0];
  actualSize.events.click();
  const zoomOut = descendants(diagram, (node) => node.title === 'Zoom out')[0];
  zoomOut.events.click();
  const scale = Number.parseInt(diagram.contactState.workspace.zoomValue.textContent, 10) / 100;
  assert.equal(labels[0].style.display, '');
  assert.ok(Math.abs((Number(labels[1].attributes.y) - Number(labels[0].attributes.y))
    * scale - 14) < 0.2);
  for (let index = 0; index < 20; index += 1) zoomOut.events.click();
  assert.equal(labels[0].style.display, 'none');
  assert.equal(labels[1].style.display, 'none');
  const zoomIn = descendants(diagram, (node) => node.title === 'Zoom in')[0];
  for (let index = 0; index < 20; index += 1) zoomIn.events.click();
  assert.equal(labels[0].style.display, '');
  assert.equal(labels[1].style.display, '');
});

test('a contact with only Pin shows its pin in the diagram and accessible name', () => {
  const { context } = palette();
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, [{
    contactId: 'pin-only', kind: 'face', name: 'Pad', assignedName: '', pin: '12',
    linked: true, normal: [0, 0, 1],
    loops: [[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]],
  }]);
  const item = contactItem(diagram, 'pin-only');
  const label = descendants(item, (node) => node.className?.includes('interface-contact-label'))[0];
  assert.equal(label.textContent, 'Pin 12');
  assert.match(item.attributes['aria-label'], /Pin 12/);
});

test('compact contacts keep Value outside and unnamed contacts have a distinct appearance', () => {
  const { context } = palette();
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, [
    { contactId: 'named', kind: 'face', name: 'A1', assignedName: 'A1', linked: true,
      normal: [0, 0, 1], loops: [[[0, 0, 0], [1, 0, 0], [1, 1, 0]]] },
    { contactId: 'unnamed', kind: 'face', name: 'Pad', assignedName: '', linked: true,
      normal: [0, 0, 1], loops: [[[20, 0, 0], [21, 0, 0], [21, 1, 0]]] },
  ]);
  assert.equal(contactItem(diagram, 'named').dataset.named, 'true');
  assert.equal(contactItem(diagram, 'unnamed').dataset.named, 'false');
  assert.match(readPaletteStyles(), /\[data-named="false"\] \.interface-contact-outline/);
  const label = descendants(contactItem(diagram, 'named'), (node) => (
    node.className?.includes('interface-contact-label-outside')
  ))[0];
  assert.equal(label.textContent, 'A1');
  assert.equal(label.style.display, undefined);
  const zoomIn = descendants(diagram, (node) => node.title === 'Zoom in')[0];
  for (let index = 0; index < 20; index += 1) zoomIn.events.click();
  assert.equal(label.style.display, undefined);
  assert.equal(descendants(contactItem(diagram, 'named'), (node) => node.tag === 'title')[0]
    .textContent, 'A1');
  assert.match(descendants(contactItem(diagram, 'unnamed'), (node) => node.tag === 'title')[0]
    .textContent, /Unnamed contact/);
});

test('dense two-column contacts keep each outside label aligned to its pad', () => {
  const { context } = palette();
  const contacts = Array.from({ length: 38 }, (_unused, index) => {
    const column = index < 19 ? 0 : 1;
    const row = index % 19;
    const x = column * 20;
    const y = row * 2;
    return {
      contactId: `pad-${index}`, kind: 'face', name: `Pad ${index}`,
      assignedName: `V${index}`, pin: `${index + 1}`, linked: true, normal: [0, 0, 1],
      loops: [[[x, y, 0], [x + 0.5, y, 0], [x + 0.5, y + 0.5, 0], [x, y + 0.5, 0]]],
    };
  });
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, contacts);
  const { svg, items, diagramWidth, diagramHeight } = diagram.contactState;
  const labels = descendants(svg, (node) => node.className?.includes('interface-contact-label-outside'));
  const leaders = descendants(svg, (node) => node.className === 'interface-contact-label-leader');
  assert.equal(labels.length, 38);
  assert.equal(leaders.length, 38);
  assert.equal(labels[0].textContent, 'Pin 1 · V0');
  assert.notEqual(labels[0].attributes['text-anchor'], labels[19].attributes['text-anchor']);
  assert.ok(labels[0].attributes['text-anchor'] === 'end'
    ? Number(labels[0].attributes.x) < items[0].loops[0][0][0]
    : Number(labels[0].attributes.x) > items[0].loops[0][0][0]);
  assert.ok(labels[19].attributes['text-anchor'] === 'end'
    ? Number(labels[19].attributes.x) < items[19].loops[0][0][0]
    : Number(labels[19].attributes.x) > items[19].loops[0][0][0]);
  labels.forEach((label, index) => {
    const ys = items[index].loops[0].map((point) => point[1]);
    const padCenter = (Math.min(...ys) + Math.max(...ys)) / 2;
    assert.ok(Math.abs(Number(label.attributes.y) - padCenter) < 0.01);
  });
  assert.ok(Number.parseFloat(labels[0].style.fontSize) < 11);
  assert.ok(Number.parseFloat(labels[19].style.fontSize) < 11);
  for (const start of [0, 19]) {
    for (let index = start + 1; index < start + 19; index += 1) {
      const firstHeight = Number.parseFloat(labels[index - 1].style.fontSize) + 3;
      const secondHeight = Number.parseFloat(labels[index].style.fontSize) + 3;
      assert.ok(Number(labels[index].attributes.y) - Number(labels[index - 1].attributes.y)
        >= (firstHeight + secondHeight) / 2);
    }
  }
  assert.ok(labels.every((label) => Number(label.attributes.x) > 0
    && Number(label.attributes.x) < diagramWidth
    && Number(label.attributes.y) < diagramHeight));
});

test('vertical labels shrink only where neighboring pads are close', () => {
  const { context } = palette();
  const contacts = [0, 0.8, 15].map((y, index) => ({
    contactId: `pad-${index}`, kind: 'face', assignedName: `J4.${index + 1} (NC)`,
    linked: true, normal: [0, 0, 1],
    loops: [[[0, y, 0], [0.3, y, 0], [0.3, y + 0.3, 0], [0, y + 0.3, 0]]],
  }));
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, contacts);
  const labels = descendants(diagram.contactState.svg, (node) => (
    node.className?.includes('interface-contact-label-outside')
  ));
  assert.equal(labels.length, 3);
  assert.ok(Number.parseFloat(labels[0].style.fontSize) < 11);
  assert.ok(Number.parseFloat(labels[1].style.fontSize) < 11);
  assert.equal(Number.parseFloat(labels[2].style.fontSize), 11);
  labels.forEach((label, index) => {
    const ys = diagram.contactState.items[index].loops[0].map((point) => point[1]);
    assert.ok(Math.abs(Number(label.attributes.y) - (Math.min(...ys) + Math.max(...ys)) / 2) < 0.01);
  });
});

test('wide contact rows place compact labels above and below the geometry', () => {
  const { context } = palette();
  const contacts = [0, 1].flatMap((row) => Array.from({ length: 3 }, (_unused, column) => ({
    contactId: `${row}-${column}`, kind: 'face', assignedName: `V${row}${column}`,
    linked: true, normal: [0, 0, 1],
    loops: [[[column * 8, row * 2, 0], [column * 8 + 0.5, row * 2, 0],
      [column * 8 + 0.5, row * 2 + 0.5, 0], [column * 8, row * 2 + 0.5, 0]]],
  })));
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, contacts);
  const labels = descendants(diagram.contactState.svg, (node) => (
    node.className?.includes('interface-contact-label-outside')
  ));
  assert.equal(labels.length, 6);
  assert.equal(labels.slice(0, 3).every((label) => label.attributes['text-anchor'] === 'middle'), true);
  assert.ok(Number(labels[0].attributes.y) < diagram.contactState.items[0].loops[0][0][1]);
  assert.ok(Number(labels[3].attributes.y) > diagram.contactState.items[3].loops[0][0][1]);
});
