/** Run with node tests/test_palette.cjs; no Fusion or browser dependencies. */
/* global require */
const paletteSuites = [
  "editor-recovery.cjs",
  "master-interactions.cjs",
  "master-rendering.cjs",
  "editors.cjs",
  "host.cjs",
  "materials.cjs",
  "master-style.cjs",
];

paletteSuites.forEach((suite) => require(`./palette/${suite}`));
