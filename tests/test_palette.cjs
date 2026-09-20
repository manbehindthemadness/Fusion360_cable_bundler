/** Run with node tests/test_palette.cjs; no Fusion or browser dependencies. */
/* global require */
const paletteSuites = [
  "master-layout-state.cjs",
  "master-layout-routing.cjs",
  "panel-ui.cjs",
  "master-style.cjs",
];

paletteSuites.forEach((suite) => require(`./palette/${suite}`));
