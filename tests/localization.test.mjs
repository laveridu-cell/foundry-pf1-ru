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
