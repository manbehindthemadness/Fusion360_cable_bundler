/** Run with node tests/test_palette.cjs; no Fusion or browser dependencies. */
/* global require */
const paletteSuites = [
  "group-ui.cjs",
  "master-style.cjs",
];

paletteSuites.forEach((suite) => require(`./palette/${suite}`));
