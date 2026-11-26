"""Check that standalone and archived manifests describe the exact same release."""
import argparse
from zipfile import BadZipFile, ZipFile

from validate import ROOT, read_json, require, validate


def distribution_files():
    files = [ROOT / "module.json", ROOT / "README.md"]
    for directory in ["scripts", "lang", "compendium", "terminology", "docs"]:
        files.extend(path for path in (ROOT / directory).rglob("*") if path.is_file())
    return sorted(files)


def check_distribution(manifest):
    dist = ROOT / "dist"
    require(read_json(dist / "module.json") == manifest, "dist/module.json отличается от исходного манифеста")
    archive = dist / f'{manifest["id"]}.zip'
    with ZipFile(archive) as bundle:
        names = bundle.namelist()
        require(len(names) == len(set(names)), "В ZIP повторяются пути")
        required = {"module.json", *manifest["esmodules"], *(entry["path"] for entry in manifest["languages"])}
        require(required <= set(names), "В корне ZIP нет манифеста или в архиве отсутствуют файлы модуля")
        expected = {str(path.relative_to(ROOT)) for path in distribution_files()}
        require(set(names) == expected, "Состав ZIP не совпадает с полным составом модуля")
        require(bundle.read("module.json") == (dist / "module.json").read_bytes(),
                "Манифест внутри ZIP отличается от отдельного module.json")
        # A stale ZIP must not silently ship previous translations or scripts.
        for name in names:
            source = (ROOT / name).resolve()
            require(source.is_relative_to(ROOT) and source.is_file(), f"Неизвестный путь в ZIP: {name}")
            require(bundle.read(name) == source.read_bytes(), f"ZIP содержит устаревший файл: {name}")
        require(bundle.testzip() is None, "Нарушена целостность ZIP")
    print(f'OK release: {manifest["id"]} {manifest["version"]}, {len(names)} файлов; манифесты совпадают')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Ожидаемый тег vX.Y.Z")
    args = parser.parse_args()
    try:
        check_distribution(validate(args.tag))
    except (ValueError, KeyError, OSError, BadZipFile) as error:
        raise SystemExit(f"ERROR: {error}")
