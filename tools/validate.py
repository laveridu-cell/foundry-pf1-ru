"""Offline checks for manifests, translation keys and safe packaging inputs (stdlib only)."""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
IGNORED = {".git", "node_modules", "dist", "__pycache__"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Дублирующийся ключ JSON: {key}")
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object,
                      parse_constant=lambda value: require(False, f"Недопустимое значение JSON: {value}"))


def local_file(path):
    require(isinstance(path, str) and not Path(path).is_absolute(), f"Нужен относительный путь: {path}")
    resolved = (ROOT / path).resolve()
    require(resolved.is_relative_to(ROOT) and resolved.is_file(), f"Файл не найден или вне проекта: {path}")
    return resolved


def flatten(data, prefix=""):
    require(isinstance(data, dict), f"Ожидается объект перевода: {prefix}")
    result = {}
    for key, value in data.items():
        require(all(part not in {"__proto__", "prototype", "constructor"} and not part.startswith("-=")
                    for part in key.split(".")), f"Небезопасный ключ: {key}")
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            children = flatten(value, full)
            require(not result.keys() & children.keys(), f"Пересекающиеся ключи: {full}")
            result.update(children)
        else:
            require(isinstance(value, str) and value.strip(), f"Нужна непустая строка: {full}")
            require(full not in result, f"Дублирующийся путь: {full}")
            result[full] = value
    return result


def placeholders(text):
    return sorted(re.findall(r"\{[^{}]+\}", text))


def validate(tag=None):
    paths = [p for p in ROOT.rglob("*.json") if not IGNORED.intersection(p.relative_to(ROOT).parts)]
    for path in paths:
        read_json(path)
    manifest = read_json(ROOT / "module.json")
    package = read_json(ROOT / "package.json")
    require(manifest["id"] == "foundry-pf1-ru", "Неверный ID модуля")
    require(re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", manifest["version"]), "Неверная версия")
    require(package["version"] == manifest["version"], "Версии package.json и module.json различаются")
    if tag is not None:
        require(tag == f'v{manifest["version"]}', "Тег должен совпадать с версией module.json")
    require(manifest["compatibility"] == {"minimum": "13", "verified": "13", "maximum": "13"},
            "Целевая версия Foundry должна быть 13")
    require(manifest.get("title") and manifest.get("description") and manifest.get("authors"), "Неполный манифест")
    require(not manifest.get("coreTranslation"), "Базовую локализацию предоставляет Phenomen")
    require(not manifest.get("packs"), "Собственные игровые библиотеки пока не создаём")
    systems = manifest["relationships"]["systems"]
    require(systems == [{"id": "pf1", "type": "system", "compatibility": {
        "minimum": "11.11", "verified": "11.11", "maximum": "11.11"}}], "Ожидается pf1 11.11")
    dependencies = manifest["relationships"]["requires"]
    require({dep["id"] for dep in dependencies} == {"ru-ru", "babele", "lib-wrapper"}, "Неверные зависимости")
    require(len(dependencies) == 3 and all(dep["type"] == "module" for dep in dependencies), "Неверные типы зависимостей")
    for dep in dependencies:
        require(dep["manifest"].startswith("https://"), "Манифест зависимости должен использовать HTTPS")
    base = "https://github.com/laveridu-cell/foundry-pf1-ru"
    require(manifest["manifest"] == f"{base}/releases/latest/download/module.json", "Неверный URL обновлений")
    require(manifest["download"] == f'{base}/releases/download/v{manifest["version"]}/foundry-pf1-ru.zip',
            "URL архива не соответствует версии")
    for path in manifest["esmodules"] + [manifest["readme"]]:
        local_file(path)

    references = read_json(ROOT / "tests/fixtures/upstream-keys.json")
    babele = next(dep for dep in dependencies if dep["id"] == "babele")
    compatibility = babele["compatibility"]
    target_version = references["babele"]["version"]
    version = lambda value: tuple(int(part) for part in value.split("."))
    require(version(compatibility["minimum"]) <= version(target_version) <= version(compatibility["maximum"]),
            f"Манифест блокирует целевую Babele {target_version}")
    require(compatibility["verified"] == target_version, "Версия Babele не совпадает с проверенным источником")
    require(babele["manifest"] == f"https://gitlab.com/riccisi/foundryvtt-babele/-/raw/{target_version}/module/module.json",
            "Манифест зависимости должен соответствовать целевой версии Babele")
    originals = {key: value for ref in references.values() for key, value in ref["keys"].items()}
    languages = manifest["languages"]
    require(languages[-1]["path"] == "lang/overrides/phenomen.json", "Исправления должны идти последними")
    require(len({entry["path"] for entry in languages}) == len(languages), "Повтор пути локализации")
    registered = set()
    final_translations = {}
    for entry in languages:
        path = entry["path"]
        require(entry["lang"] == "ru" and entry.get("name"), f"Неверное описание языка: {path}")
        require(path.startswith("lang/"), f"Файл перевода должен находиться в lang/: {path}")
        require(entry.get("system", "pf1") == "pf1", f"Неизвестная система: {path}")
        if path.startswith("lang/modules/"):
            require(entry.get("module"), f"Укажите ID дополнительного модуля: {path}")
        data = flatten(read_json(local_file(path)))
        for key, value in data.items():
            require(key in originals, f"Ключ {key} не подтверждён в tests/fixtures/upstream-keys.json")
            require(placeholders(value) == placeholders(originals[key]), f"Изменены подстановки: {key}")
        registered.add(path)
        final_translations.update(data)
    actual = {str(p.relative_to(ROOT)) for p in (ROOT / "lang").rglob("*.json")}
    require(actual == registered, "Все JSON-файлы lang/ должны быть зарегистрированы в манифесте")

    glossary = read_json(ROOT / "terminology/glossary.json")
    require(glossary["source"] == "https://pathfinder.family/", "Неверный источник терминологии")
    require(glossary["entryNameFormat"] == "Русское название [English Name]", "Неверный формат названий")
    seen_terms = set()
    for term in glossary["terms"]:
        require(all(isinstance(term.get(field), str) and term[field].strip() for field in ["en", "ru", "source"]),
                "Термину нужны английское имя, русский вариант и источник")
        identity = (term["en"], term.get("context", ""))
        require(identity not in seen_terms, f'Повтор термина и контекста: {term["en"]}')
        seen_terms.add(identity)
        if term["source"] == "AGENTS.md":
            require(term.get("approvedBy") == "user", "Правило словаря требует явного утверждения пользователя")
            local_file("AGENTS.md")
        elif term["source"] == "user-core-rulebook":
            require(isinstance(term.get("reference"), str) and term["reference"].strip(),
                    "Нужна библиографическая ссылка и страница русской книги")
        elif not term["source"].startswith((glossary["source"], "https://www.pathfinder.family/",
                                            "https://www.d20pfsrd.com/", "https://d20pfsrd.com/")):
            require(term.get("approvedBy") == "user" and term["source"].startswith("https://"),
                    "Иной источник требует ссылки и согласования пользователя")
        # General game terms need not correspond to an interface localization key.
        if "key" in term:
            require(final_translations.get(term["key"]) == term["ru"],
                    f'Термин расходится с переводом: {term["en"]}')

    for directory in ["lang/system", "lang/overrides", "lang/modules", "compendium/ru", "terminology"]:
        require((ROOT / directory).is_dir(), f"Нет каталога {directory}")
    # Only names/descriptions are allowed initially; no formulas, IDs or arbitrary mappings.
    for path in (ROOT / "compendium/ru").glob("*.json"):
        data = read_json(path)
        require(re.fullmatch(r"[\w-]+\.[\w-]+\.json", path.name), f"Неверное имя библиотеки: {path.name}")
        require(set(data) <= {"label", "entries"}, f"Маппинг требует отдельного рассмотрения: {path.name}")
        require(isinstance(data.get("entries"), dict), "Ожидается объект entries Babele")
        for original, entry in data["entries"].items():
            require(isinstance(entry, dict) and set(entry) <= {"name", "description"}, "Допустимы только имя и описание")
            name = entry.get("name", "")
            require(name.endswith(f" [{original}]") and re.search(r"[А-Яа-яЁё]", name),
                    f"Ожидается Русское название [English Name]: {original}")
            require(all(isinstance(value, str) for value in entry.values()), "Значения Babele должны быть строками")
    print(f"OK: {len(paths)} JSON, {len(languages)} файлов локализации, {len(final_translations)} реальных ключей")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Проверить тег перед подготовкой релиза")
    args = parser.parse_args()
    try:
        validate(args.tag)
    except (ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"ERROR: {error}")
