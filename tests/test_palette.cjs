/** Run with node tests/test_palette.cjs; no Fusion or browser dependencies. */
/* global require */
const paletteSuites = [
  "master-layout-state.cjs",
  "master-layout-routing.cjs",
  "panel-ui.cjs",
  "panel-ui-interface.cjs",
  "panel-ui-end-menus.cjs",
  "panel-contact-geometry.cjs",
  "panel-contact-pos-import.cjs",
  "panel-contact-render.cjs",
  "panel-contact-projection.cjs",
  "panel-contact-interactions.cjs",
  "panel-contact-auto-pin.cjs",
  "panel-contact-auto-connect.cjs",
  "panel-navigation.cjs",
  "panel-associations.cjs",
  "panel-connections.cjs",
  "panel-properties.cjs",
  "master-style.cjs",
];

paletteSuites.forEach((suite) => require(`./palette/${suite}`));
