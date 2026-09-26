/** Directed contact projection and sizing regressions. */
const { assert, palette, test } = require('./support.cjs');

test('contact projection views asymmetric layouts from the picked face side', () => {
  const { context } = palette();
  for (const [normal, expectedRight, expectedUp] of [
    [[0, 0, 2], [-4, 0], [0, 2]],
    [[0, 0, -2], [4, 0], [0, 2]],
  ]) {
    const direction = context.contactOrientation(normal);
    const right = context.contactPlanePoint([4, 0, 0], direction);
    const up = context.contactPlanePoint([0, 2, 0], direction);
    assert.ok(right.every((value, index) => value === expectedRight[index]));
    assert.ok(up.every((value, index) => value === expectedUp[index]));
    const diagram = context.document.createElement('div');
    context.renderInterfaceContacts(diagram, [
      { contactId: 'front', kind: 'face', linked: true, normal,
        loops: [[[0, 0, 0], [4, 0, 0], [4, 2, 0]]] },
      { contactId: 'back', kind: 'face', linked: true, normal: normal.map((value) => -value),
        loops: [[[6, 0, 0], [7, 0, 0], [7, 1, 0]]] },
    ]);
    assert.equal(diagram.contactState.svg.children.length, 2);
    const [front, back] = diagram.contactState.items;
    const frontDirection = front.loops[0][1][0] - front.loops[0][0][0];
    const backDirection = back.loops[0][1][0] - back.loops[0][0][0];
    assert.equal(Math.sign(frontDirection), Math.sign(expectedRight[0]));
    assert.equal(Math.sign(backDirection), -Math.sign(expectedRight[0]),
      'each opposing face is viewed from its own picked side');
  }
});

test('board contact projection keeps the small pads below the long pads', () => {
  const { context } = palette();
  const diagram = context.document.createElement('div');
  context.renderInterfaceContacts(diagram, [
    { contactId: 'long', kind: 'face', linked: true, normal: [0, 0, 1],
      parentAxes: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
      loops: [[[0, 0, 0], [4, 0, 0], [4, 1, 0]]] },
    { contactId: 'small', kind: 'face', linked: true, normal: [0, 0, 1],
      parentAxes: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
      loops: [[[0, 5, 0], [1, 5, 0], [1, 6, 0]]] },
  ]);
  assert.ok(diagram.contactState.items[1].loops[0][0][1]
    > diagram.contactState.items[0].loops[0][0][1]);
});

test('contact clusters retain their local layout when the parent tilts and rotates', () => {
  const { context } = palette();
  const axes = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
  const contacts = [
    { contactId: 'a', kind: 'face', linked: true, normal: [0, 0, 1], parentAxes: axes,
      loops: [[[0, 0, 0], [4, 0, 0], [4, 1, 0]]] },
    { contactId: 'b', kind: 'face', linked: true, normal: [0, 0, -1],
      parentAxes: [[0, 1, 0], [-1, 0, 0], [0, 0, 1]],
      loops: [[[2, 5, 0], [3, 5, 0], [3, 6, 0]]] },
    { contactId: 'c', kind: 'face', linked: true, normal: [1, 0, 0], parentAxes: axes,
      loops: [[[0, 0, 0], [0, 4, 0], [0, 4, 1]]] },
  ];
  const baseline = context.document.createElement('div');
  context.renderInterfaceContacts(baseline, contacts);
  assert.equal(baseline.contactState.svg.children.length, 3);
  for (const angle of [0.4, 1.2, Math.PI / 2, Math.PI]) {
    const rotate = ([x, y, z]) => {
      const c = Math.cos(angle);
      const s = Math.sin(angle);
      const tiltedY = c * y - s * z;
      const tiltedZ = s * y + c * z;
      return [c * x - s * tiltedY, s * x + c * tiltedY, tiltedZ];
    };
    const rotated = contacts.map((contact) => ({
      ...contact,
      normal: rotate(contact.normal), parentAxes: contact.parentAxes.map(rotate),
      loops: contact.loops.map((loop) => loop.map((point) => (
        rotate(point).map((value, index) => value + [10, -20, 30][index])
      ))),
    }));
    const diagram = context.document.createElement('div');
    context.renderInterfaceContacts(diagram, rotated);
    assert.equal(diagram.contactState.svg.children.length, 3);
    diagram.contactState.items.forEach((item, index) => {
      item.loops[0].forEach((point, vertex) => {
        point.forEach((value, axis) => assert.ok(
          Math.abs(value - baseline.contactState.items[index].loops[0][vertex][axis]) < 1e-8,
          'parent rotation must preserve the complete projected arrangement',
        ));
      });
    });
  }
});

test('small contact pads fit the diagram without strokes swallowing their gaps', () => {
  const { context } = palette();
  for (const modelScale of [0.01, 1, 1000]) {
    const diagram = context.document.createElement('div');
    const contacts = Array.from({ length: 7 }, (_unused, index) => {
      const width = index < 5 ? 4 : 1.2;
      return {
        contactId: `pad-${index}`, kind: 'face', name: `Pad ${index}`, linked: true,
        normal: [0, 0, 1],
        loops: [[[0, index], [width, index], [width, index + 0.6], [0, index + 0.6]]
          .map(([x, y]) => [(20 + x) * modelScale, (30 + y) * modelScale, 0])],
      };
    });
    context.renderInterfaceContacts(diagram, contacts);
    const { items, svg, diagramHeight } = diagram.contactState;
    assert.equal(items.length, 7);
    const loops = items.map((item) => item.loops[0]);
    const width = Math.abs(loops[0][1][0] - loops[0][0][0]);
    const height = Math.abs(loops[0][2][1] - loops[0][1][1]);
    assert.ok(height > 10, 'pad interiors remain visible at the initial display scale');
    assert.ok(Math.abs(width / height - 4 / 0.6) < 1e-8);
    for (let index = 1; index < loops.length; index += 1) {
      assert.ok(loops[index][0][1] - loops[index - 1][2][1] > 3,
        'neighboring pad strokes must not overlap');
    }
    assert.ok(loops[6][2][1] < diagramHeight);
    assert.equal(svg.style.height, `${diagramHeight}px`, 'labels use display units');
  }
});
