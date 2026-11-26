"""Synchronize local release metadata. Never creates commits, tags or releases."""
import argparse
import json
import re

from validate import ROOT, read_json, require, validate


def next_version(current, target):
    major, minor, patch = (int(part) for part in current.split("."))
    increments = {"patch": (major, minor, patch + 1), "minor": (major, minor + 1, 0), "major": (major + 1, 0, 0)}
    if target in increments:
        target = ".".join(map(str, increments[target]))
    require(re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", target),
            "Укажите patch, minor, major или версию X.Y.Z без префикса v")
    require(tuple(map(int, target.split("."))) > (major, minor, patch),
            "Новая версия должна быть больше текущей")
    return target


def bump(target, dry_run=False):
    manifest = validate()
    previous = manifest["version"]
    version = next_version(previous, target)
    package = read_json(ROOT / "package.json")
    manifest["version"] = package["version"] = version
    manifest["download"] = (
        f"https://github.com/laveridu-cell/foundry-pf1-ru/releases/download/v{version}/foundry-pf1-ru.zip"
    )
    print(f"{previous} -> {version}: module.json (version, download), package.json (version)")
    if dry_run:
        print("Проверка без записи: файлы не изменены")
        return
    updates = {ROOT / "module.json": manifest, ROOT / "package.json": package}
    original = {path: path.read_bytes() for path in updates}
    try:
        for path, data in updates.items():
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        validate()
    except Exception:
        for path, content in original.items():
            path.write_bytes(content)
        raise
    print("Версия обновлена. Коммит, тег и релиз не создавались; dist/ нужно пересобрать")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", default="patch", help="patch, minor, major или X.Y.Z")
    parser.add_argument("--dry-run", action="store_true", help="Показать новую версию без записи")
    args = parser.parse_args()
    try:
        bump(args.target, args.dry_run)
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit(f"ERROR: {error}")
