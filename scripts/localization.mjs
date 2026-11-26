export const MODULE_ID = "foundry-pf1-ru";

/** Manifest order is also the explicit overlay priority; corrections come last. */
export async function applyTranslations({ game, utils, fetcher = globalThis.fetch }) {
  if (game.system.id !== "pf1" || game.i18n.lang !== "ru") return [];

  const layers = game.modules.get(MODULE_ID).languages.filter((entry) =>
    entry.lang === "ru"
    && (!entry.system || entry.system === game.system.id)
    && (!entry.module || game.modules.get(entry.module)?.active)
  );

  // Load everything before modifying the dictionary; a failed request keeps the base intact.
  // Promise.all preserves manifest order even when requests finish out of order.
  const dictionaries = await Promise.all(layers.map(async ({ path }) => {
    const url = utils.getRoute(`modules/${MODULE_ID}/${path}`);
    const response = await fetcher(url, { cache: "no-cache" });
    if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
    const data = await response.json();
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      throw new Error(`${path}: ожидается объект JSON`);
    }
    return data;
  }));

  // A concurrent switch to another language must not receive Russian overlays.
  if (game.i18n.lang !== "ru") return [];
  for (const data of dictionaries) {
    utils.mergeObject(game.i18n.translations, data, {
      inplace: true,
      overwrite: true,
      insertKeys: true,
      insertValues: true,
      performDeletions: false
    });
  }
  return layers.map(({ path }) => path);
}

/** Wrap the awaited language API, so PF1's i18nInit caches see the overlay. */
export function installLocalization({ game, utils, wrapper, fetcher, logger = console }) {
  const status = { language: null, applied: [], error: null };
  game.modules.get(MODULE_ID).api = Object.freeze({
    localizationStatus: () => structuredClone(status)
  });

  wrapper.register(MODULE_ID, "game.i18n.setLanguage", async function (wrapped, ...args) {
    const result = await wrapped(...args);
    status.language = game.i18n.lang;
    status.applied = [];
    status.error = null;
    try {
      status.applied = await applyTranslations({ game, utils, fetcher });
    } catch (error) {
      status.error = error.message;
      logger.error(`${MODULE_ID} | Не удалось применить дополнения перевода`, error);
    }
    return result;
  }, "WRAPPER");
}

export function registerCompendiums(game, babele) {
  if (game.system.id !== "pf1") return;
  babele.register({ module: MODULE_ID, lang: "ru", dir: "compendium/ru" });
}
