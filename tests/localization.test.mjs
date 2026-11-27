import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { applyTranslations, installLocalization, MODULE_ID, registerCompendiums } from "../scripts/localization.mjs";

const manifest = JSON.parse(await readFile(new URL("../module.json", import.meta.url)));
const root = new URL("../", import.meta.url);

function environment({ lang = "ru", system = "pf1", babeleActive = true } = {}) {
  const game = {
    system: { id: system },
    modules: new Map([
      [MODULE_ID, { languages: structuredClone(manifest.languages) }],
      ["ru-ru", { active: true }],
      ["babele", { active: babeleActive }]
    ]),
    i18n: { lang, translations: { CORE: { Keep: "Базовый перевод" }, PF1: { ArmorClass: "Класс Брони", Untouched: "Сохранено" } } }
  };
  const requested = [];
  // Small model of Foundry's documented deep merge, not a running Foundry implementation.
  const mergeObject = (target, source, options) => {
    assert.equal(options.overwrite, true);
    assert.equal(options.performDeletions, false);
    for (const [key, value] of Object.entries(source)) {
      if (typeof value === "object") mergeObject(target[key] ??= {}, value, options);
      else target[key] = value;
    }
    return target;
  };
  const utils = { getRoute: (path) => `/foundry/${path}`, mergeObject };
  const fetcher = async (url) => {
    const prefix = `/foundry/modules/${MODULE_ID}/`;
    assert.ok(url.startsWith(prefix), "URLs must respect the Foundry route prefix");
    const path = url.slice(prefix.length);
    requested.push(path);
    return { ok: true, json: async () => JSON.parse(await readFile(new URL(path, root))) };
  };
  return { game, utils, fetcher, requested };
}

test("override replaces an existing key, preserves the base and real format placeholders", async () => {
  const env = environment();
  const original = env.game.i18n.translations;
  const applied = await applyTranslations(env);
  assert.equal(env.game.i18n.translations, original, "dictionary identity stays stable");
  assert.equal(original.PF1.ArmorClass, "Класс брони");
  assert.equal(original.PF1.AbilityCon, "Выносливость");
  assert.equal(original.PF1.Untouched, "Сохранено");
  assert.equal(original.CORE.Keep, "Базовый перевод");
  assert.equal(original.BABELE.CompendiumTranslations, "Переводы библиотек");
  assert.equal(original.PF1.SavingThrowRoll.replace("{save}", "Воли"), "Испытание Воли");
  assert.deepEqual(applied, manifest.languages.map(({ path }) => path));
});

test("Save means saving form changes while SavingThrow keeps the base terminology", async () => {
  const env = environment();
  Object.assign(env.game.i18n.translations.PF1, {
    Save: "Испытание",
    SavingThrow: "Испытание",
    SavingThrowPlural: "Испытания",
    SavingThrowFort: "Стойкость"
  });
  await applyTranslations(env);
  assert.equal(env.game.i18n.translations.PF1.Save, "Сохранить");
  assert.equal(env.game.i18n.translations.PF1.SavingThrow, "Испытание");
  assert.equal(env.game.i18n.translations.PF1.SavingThrowPlural, "Испытания");
  assert.equal(env.game.i18n.translations.PF1.SavingThrowFort, "Стойкость");
});

test("sheet batch overlays ten English labels and keeps third-party sheet entries", async () => {
  const fixtures = JSON.parse(await readFile(new URL("tests/fixtures/upstream-keys.json", root)));
  const sheets = Object.entries(fixtures.pf1.keys).filter(([key]) => key.startsWith("PF1.Sheet."));
  assert.equal(sheets.length, 10);
  const env = environment();
  env.game.i18n.translations.PF1.Sheet = Object.fromEntries(sheets.map(([key, value]) => [key.slice(10), value]));
  const original = env.game.i18n.translations.PF1.Sheet;
  original.ThirdPartySheet = "Чужой лист";
  await applyTranslations(env);
  assert.equal(env.game.i18n.translations.PF1.Sheet, original);
  for (const [key, english] of sheets) {
    const russian = original[key.slice(10)];
    assert.notEqual(russian, english, key);
    assert.match(russian, /[А-Яа-яЁё]/u, key);
  }
  assert.equal(original.ThirdPartySheet, "Чужой лист");
});

test("actor creation types use TYPES.Actor independently of sheet labels and preserve IDs and third-party items", async () => {
  const env = environment();
  const fixtures = JSON.parse(await readFile(new URL("tests/fixtures/upstream-keys.json", root)));
  const labels = Object.fromEntries(Object.entries(fixtures.pf1.keys)
    .filter(([key]) => key.startsWith("TYPES.Actor."))
    .map(([key, value]) => [key.slice("TYPES.Actor.".length), value]));
  env.game.i18n.translations.TYPES = {
    Actor: { ...labels, basic: "Basic (for modules)", thirdParty: "Third-party actor" },
    Item: { thirdParty: "Third-party item" }
  };
  const dictionary = env.game.i18n.translations.TYPES;
  const beforeIDs = Object.keys(dictionary.Actor);
  const beforeItems = structuredClone(dictionary.Item);
  await applyTranslations(env);
  assert.equal(env.game.i18n.translations.TYPES, dictionary);
  assert.deepEqual(Object.keys(dictionary.Actor), beforeIDs);
  for (const [key, value] of Object.entries(beforeItems)) assert.equal(dictionary.Item[key], value);
  assert.equal(dictionary.Actor.basic, "Basic (for modules)");
  assert.equal(dictionary.Actor.thirdParty, "Third-party actor");
  assert.deepEqual(Object.fromEntries(Object.keys(labels).map((id) => [id, dictionary.Actor[id]])), {
    character: "Персонаж игрока", npc: "Персонаж ведущего", haunt: "Видение",
    trap: "Ловушка", vehicle: "Транспортное средство"
  });
  for (const [id, sheet] of Object.entries({ character: "PC", npc: "NPC", haunt: "Haunt", trap: "Trap", vehicle: "Vehicle" })) {
    assert.equal(dictionary.Actor[id], env.game.i18n.translations.PF1.Sheet[sheet]);
  }
});

test("item and action overlays replace English labels without replacing unrelated Phenomen namespaces", async () => {
  const env = environment();
  const fixtures = JSON.parse(await readFile(new URL("tests/fixtures/upstream-keys.json", root)));
  const originals = (prefix) => Object.fromEntries(Object.entries(fixtures.pf1.keys)
    .filter(([key]) => key.startsWith(prefix)).map(([key, value]) => [key.slice(prefix.length), value]));
  const items = originals("TYPES.Item.");
  const actions = originals("PF1.ActionTypes.");
  assert.equal(Object.keys(items).length, 12);
  assert.equal(Object.keys(actions).length, 11);
  env.game.i18n.translations.TYPES = { Item: { ...items, thirdParty: "Другой модуль" } };
  Object.assign(env.game.i18n.translations.PF1, {
    ActionTypes: { ...actions, thirdParty: "Другое действие" },
    Subtypes: { Item: { feat: { feat: "Черта из базового перевода" } } },
    SavingThrow: "Испытание",
    LimitedUses: { Periods: { single: "Однократно из базового перевода" } }
  });
  const dictionary = env.game.i18n.translations;
  const subtypes = structuredClone(dictionary.PF1.Subtypes);
  const limitedUses = structuredClone(dictionary.PF1.LimitedUses);
  const sheets = originals("PF1.Sheet.");
  await applyTranslations(env);
  for (const [entries, target] of [[items, dictionary.TYPES.Item], [actions, dictionary.PF1.ActionTypes]]) {
    for (const [key, english] of Object.entries(entries)) {
      assert.notEqual(target[key], english, key);
      assert.match(target[key], /[А-Яа-яЁё]/u, key);
    }
    assert.deepEqual(Object.keys(target).sort(), [...Object.keys(entries), "thirdParty"].sort());
  }
  assert.equal(dictionary.TYPES.Item.thirdParty, "Другой модуль");
  assert.equal(dictionary.PF1.ActionTypes.thirdParty, "Другое действие");
  assert.deepEqual(dictionary.PF1.Subtypes, subtypes);
  assert.deepEqual(dictionary.PF1.LimitedUses, limitedUses, "Consumable does not rename limited-use settings");
  assert.deepEqual(Object.fromEntries(["race", "buff", "consumable", "implant"].map((id) => [id, dictionary.TYPES.Item[id]])), {
    race: "Народ", buff: "Эффект", consumable: "Расходуемый предмет", implant: "Имплантат"
  });
  assert.equal(dictionary.TYPES.Item.feat, "Особенность", "Feature is broader than the feat subtype");
  assert.equal(dictionary.TYPES.Item.container, dictionary.PF1.Sheet.Container);
  assert.equal(Object.keys(sheets).length, 10);
  assert.equal(dictionary.PF1.ActionTypes.save, "Испытание");
  assert.equal(dictionary.PF1.ActionTypes.spellSave, "Испытание (заклинание)");
  assert.equal(dictionary.PF1.Save, "Сохранить");
  assert.equal(dictionary.PF1.SavingThrow, "Испытание");
});

test("awaited loading supplies item choices and PF1's action cache while option values remain technical", async () => {
  const env = environment();
  const fixtures = JSON.parse(await readFile(new URL("tests/fixtures/upstream-keys.json", root)));
  const typeLabels = Object.freeze(Object.fromEntries(Object.keys(fixtures.pf1.keys)
    .filter((key) => key.startsWith("TYPES.Item.")).map((key) => [key.slice(11), key])));
  // PF1 11.11 module/config.mjs:1112. In particular, value spellsave differs from key spellSave.
  const actionLabels = Object.freeze({
    mwak: "PF1.ActionTypes.mwak", rwak: "PF1.ActionTypes.rwak", twak: "PF1.ActionTypes.twak",
    msak: "PF1.ActionTypes.msak", rsak: "PF1.ActionTypes.rsak", mcman: "PF1.ActionTypes.mcman",
    rcman: "PF1.ActionTypes.rcman", spellsave: "PF1.ActionTypes.spellSave",
    save: "PF1.ActionTypes.save", heal: "PF1.ActionTypes.heal", other: "PF1.ActionTypes.other"
  });
  const localize = (key) => key.split(".").reduce((value, part) => value?.[part], env.game.i18n.translations) ?? key;
  let wrappedMethod;
  installLocalization({ ...env, wrapper: { register: (_id, _target, fn) => { wrappedMethod = fn; } } });
  await wrappedMethod(async () => {
    // Native dictionaries, including Phenomen's unchanged English entries, load first.
    for (const [key, value] of Object.entries(fixtures.pf1.keys)) {
      const parts = key.split(".");
      const leaf = parts.pop();
      const parent = parts.reduce((data, part) => data[part] ??= {}, env.game.i18n.translations);
      parent[leaf] = value;
    }
  }, "ru");
  // Contract model of consumers AFTER awaited setLanguage; not an execution of Foundry or PF1.
  const itemChoices = Object.fromEntries(Object.entries(typeLabels).map(([id, key]) => [id, localize(key)]));
  const actionCache = Object.fromEntries(Object.entries(actionLabels).map(([id, key]) => [id, localize(key)]));
  assert.deepEqual(Object.keys(itemChoices), Object.keys(typeLabels));
  assert.deepEqual(Object.keys(actionCache), Object.keys(actionLabels));
  for (const label of Object.values(itemChoices)) assert.match(label, /[А-Яа-яЁё]/u);
  for (const label of Object.values(actionCache)) assert.match(label, /[А-Яа-яЁё]/u);
  assert.equal(actionCache.spellsave, "Испытание (заклинание)");
  assert.equal(actionCache.spellSave, undefined, "a localization key must not become an action ID");
  assert.equal(typeLabels.weapon, "TYPES.Item.weapon");
  assert.equal(actionLabels.save, "PF1.ActionTypes.save");
  assert.equal(localize("TYPES.Actor.character"), "Персонаж игрока");
  assert.equal(localize("PF1.Sheet.PC"), "Персонаж игрока");
});

test("awaited language loading exposes actor type labels before an i18nInit consumer reads them", async () => {
  const env = environment();
  let wrappedMethod;
  installLocalization({ ...env, wrapper: { register: (_id, _target, fn) => { wrappedMethod = fn; } } });
  const typeLabels = Object.freeze({
    base: "TYPES.Base", character: "TYPES.Actor.character", npc: "TYPES.Actor.npc",
    vehicle: "TYPES.Actor.vehicle", haunt: "TYPES.Actor.haunt", trap: "TYPES.Actor.trap"
  });
  const systemTypes = Object.freeze(["character", "npc", "vehicle", "haunt", "trap"]);
  const localize = (key) => key.split(".").reduce((data, part) => data?.[part], env.game.i18n.translations) ?? key;
  // Contract model: the consumer reads configuration label keys after awaited setLanguage.
  // This does not execute Foundry's private initialization or infer its cache timing.
  await wrappedMethod(async () => {
    await Promise.resolve();
    env.game.i18n.translations.TYPES = { Base: "Base", Actor: {
      character: "Player Character (PC)", npc: "Nonplayer Character (NPC)",
      haunt: "Haunt", trap: "Trap", vehicle: "Vehicle"
    } };
  }, "ru");
  const choices = Object.fromEntries(systemTypes.map((id) => [id, localize(typeLabels[id])]));
  assert.deepEqual(choices, {
    character: "Персонаж игрока", npc: "Персонаж ведущего", haunt: "Видение",
    trap: "Ловушка", vehicle: "Транспортное средство"
  });
  assert.equal(typeLabels.character, "TYPES.Actor.character");
  assert.equal(typeLabels.base, "TYPES.Base");
  assert.equal(env.game.i18n.translations.TYPES.Base, "Base");
  assert.equal(env.game.modules.get(MODULE_ID).api.localizationStatus().error, null);
});

test("approved skill points override the base while deferred R-01 R-02 R-03 stay untouched", async () => {
  const env = environment();
  const unresolved = ["AbilityScoreLinks", "AutomaticSpellSlots", "UseSpellPoints", "SpellPoints", "SpellPointsMax", "SpellPointsCost"];
  for (const key of unresolved) env.game.i18n.translations.PF1[key] = `base:${key}`;
  env.game.i18n.translations.PF1.SkillRankPlural = "Пункты навыка";
  env.game.i18n.translations.PF1.BGSkillRanks = "Ранги фоновых навыков";
  await applyTranslations(env);
  assert.equal(env.game.i18n.translations.PF1.SkillRankPlural, "Пункты навыков");
  assert.equal(env.game.i18n.translations.PF1.BGSkillRanks, "Пункты фоновых навыков");
  for (const key of unresolved) assert.equal(env.game.i18n.translations.PF1[key], `base:${key}`);
});

test("Foundry package paths never repeat the module directory", async () => {
  for (const leadingSlash of ["", "/"]) {
    const env = environment();
    env.game.modules.get(MODULE_ID).languages = manifest.languages.map((entry) => ({
      ...entry, path: `${leadingSlash}modules/${MODULE_ID}/${entry.path}`
    }));
    const requests = [];
    const fetchFile = env.fetcher;
    env.fetcher = async (url) => {
      assert.ok(!url.includes(`modules/${MODULE_ID}/modules/${MODULE_ID}/`), "module directory must occur only once");
      requests.push(url);
      return fetchFile(url);
    };
    await applyTranslations(env);
    assert.deepEqual(requests, manifest.languages.map(({ path }) => `/foundry/modules/${MODULE_ID}/${path}`));
    assert.equal(env.game.i18n.translations.BABELE.CompendiumTranslations, "Переводы библиотек");
  }
});

test("JSON URLs stay rooted with routePrefix regardless of the browser or ES-module base", async () => {
  for (const routePrefix of ["", "foundry", "games/pf1"]) {
    for (const routeSlash of ["", "/"]) {
      const env = environment();
      const prefix = [routePrefix, "modules", MODULE_ID].filter(Boolean).join("/");
      env.utils.getRoute = (path) => `${routeSlash}${[routePrefix, path].filter(Boolean).join("/")}`;
      const requests = [];
      env.fetcher = async (url) => {
        requests.push(url);
        assert.ok(url.startsWith("/") && !url.startsWith("//"), "fetch must receive a site-rooted path");
        const path = url.slice(`/${prefix}/`.length);
        for (const base of ["game", `modules/${MODULE_ID}/`, `modules/${MODULE_ID}/scripts/localization.mjs`]) {
          const resolved = new URL(url, `https://foundry.example/${routePrefix ? `${routePrefix}/` : ""}${base}`);
          assert.equal(resolved.origin, "https://foundry.example");
          assert.equal(resolved.pathname, `/${prefix}/${path}`);
          assert.equal(resolved.pathname.split(`/modules/${MODULE_ID}/`).length - 1, 1);
        }
        return { ok: true, json: async () => JSON.parse(await readFile(new URL(path, root))) };
      };
      await applyTranslations(env);
      assert.deepEqual(requests, manifest.languages.map(({ path }) => `/${prefix}/${path}`));
    }
  }
});

test("corrections win over earlier layers even if HTTP requests finish in reverse order", async () => {
  const env = environment();
  env.game.modules.get(MODULE_ID).languages = [manifest.languages[0], manifest.languages[2]];
  const resolvers = [];
  env.fetcher = () => new Promise((resolve) => resolvers.push(resolve));
  const pending = applyTranslations(env);
  resolvers[1]({ ok: true, json: async () => ({ PF1: { ArmorClass: "Последний слой" } }) });
  resolvers[0]({ ok: true, json: async () => ({ PF1: { ArmorClass: "Первый слой" } }) });
  await pending;
  assert.equal(env.game.i18n.translations.PF1.ArmorClass, "Последний слой");
});

test("awaited setLanguage wrapper finishes before the simulated PF1 i18nInit cache", async () => {
  const env = environment();
  let wrappedMethod;
  installLocalization({ ...env, wrapper: { register(id, target, fn, type) {
    assert.deepEqual([id, target, type], [MODULE_ID, "game.i18n.setLanguage", "WRAPPER"]);
    wrappedMethod = fn;
  } } });
  const originalMethod = async (...args) => {
    assert.deepEqual(args, ["ru"]);
    await Promise.resolve();
    // Simulates core, system and Phenomen loading in any module order.
    env.game.i18n.translations.PF1.ArmorClass = "Класс Брони";
    return "original-result";
  };
  assert.equal(await wrappedMethod(originalMethod, "ru"), "original-result");
  const simulatedPF1Cache = env.game.i18n.translations.PF1.ArmorClass;
  assert.equal(simulatedPF1Cache, "Класс брони");
  assert.equal(env.game.modules.get(MODULE_ID).api.localizationStatus().error, null);
  // A fresh language load also receives the overlays.
  await wrappedMethod(originalMethod, "ru");
  assert.equal(env.game.i18n.translations.PF1.ArmorClass, "Класс брони");
});

test("English and other systems receive no overlay requests", async () => {
  for (const options of [{ lang: "en" }, { system: "pf2e" }]) {
    const env = environment(options);
    const before = structuredClone(env.game.i18n.translations);
    assert.deepEqual(await applyTranslations(env), []);
    assert.deepEqual(env.game.i18n.translations, before);
    assert.deepEqual(env.requested, []);
  }
});

test("translations of inactive optional modules are skipped", async () => {
  const env = environment({ babeleActive: false });
  await applyTranslations(env);
  assert.ok(!env.requested.includes("lang/modules/babele.json"));
  assert.equal(env.game.i18n.translations.BABELE, undefined);
  assert.equal(env.game.i18n.translations.PF1.AbilityStr, "Сила");
});

test("failed overlay fetch preserves all base keys and reports the failure without stopping startup", async () => {
  const env = environment();
  const before = structuredClone(env.game.i18n.translations);
  const actualFetch = env.fetcher;
  env.fetcher = async (url) => url.endsWith("phenomen.json")
    ? { ok: false, status: 404 }
    : actualFetch(url);
  let wrappedMethod;
  const errors = [];
  installLocalization({ ...env,
    wrapper: { register: (_id, _target, fn) => { wrappedMethod = fn; } },
    logger: { error: (...args) => errors.push(args) }
  });
  await wrappedMethod(async () => {});
  assert.deepEqual(env.game.i18n.translations, before);
  assert.equal(errors.length, 1);
  const report = env.game.modules.get(MODULE_ID).api.localizationStatus();
  assert.match(report.error, /phenomen.json: HTTP 404/);
  assert.deepEqual(report.applied, []);
});

test("Babele receives an explicit ru directory, with no settings or document writes", () => {
  const calls = [];
  registerCompendiums(environment().game, { register: (source) => calls.push(source) });
  assert.deepEqual(calls, [{ module: MODULE_ID, lang: "ru", dir: "compendium/ru" }]);
  registerCompendiums(environment({ system: "pf2e" }).game, { register: () => assert.fail("wrong system") });
});

test("entrypoint registers Babele before nested init events can fire", async (t) => {
  const callbacks = new Map();
  t.mock.method(globalThis, "fetch", async () => assert.fail("no startup fetch expected"));
  const previous = Object.fromEntries(["Hooks", "game", "foundry", "libWrapper"].map((key) => [key, globalThis[key]]));
  t.after(() => { for (const [key, value] of Object.entries(previous)) {
    if (value === undefined) delete globalThis[key]; else globalThis[key] = value;
  } });
  const env = environment();
  let installed = false;
  globalThis.Hooks = { once: (name, fn) => callbacks.set(name, fn) };
  globalThis.game = env.game;
  globalThis.foundry = { utils: env.utils };
  globalThis.libWrapper = { register: () => { installed = true; } };
  await import("../scripts/module.mjs");
  const registrations = [];
  callbacks.get("babele.init")({ register: (data) => registrations.push(data) });
  callbacks.get("init")();
  assert.equal(installed, true);
  assert.equal(registrations.length, 1);
});
