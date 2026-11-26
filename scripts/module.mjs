import { installLocalization, registerCompendiums } from "./localization.mjs";

Hooks.once("init", () => {
  if (game.system.id !== "pf1") return;
  installLocalization({ game, utils: foundry.utils, wrapper: globalThis.libWrapper });
});

// Babele emits this during its init hook, before it reads packs on ready.
Hooks.once("babele.init", (babele) => registerCompendiums(game, babele));
