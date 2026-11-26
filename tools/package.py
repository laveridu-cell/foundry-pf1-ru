"""Create and inspect the Foundry distribution without publishing anything."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from validate import ROOT, validate

manifest = validate()
dist = ROOT / "dist"
dist.mkdir(exist_ok=True)
files = [ROOT / "module.json", ROOT / "README.md"]
for directory in ["scripts", "lang", "compendium", "terminology", "docs"]:
    files.extend(path for path in (ROOT / directory).rglob("*") if path.is_file())
archive = dist / f'{manifest["id"]}.zip'
with ZipFile(archive, "w", ZIP_DEFLATED) as output:
    for path in sorted(files):
        output.write(path, path.relative_to(ROOT))
(dist / "module.json").write_bytes((ROOT / "module.json").read_bytes())
with ZipFile(archive) as output:
    names = set(output.namelist())
    assert "module.json" in names  # Foundry expects it at the archive root.
    assert all(path in names for path in manifest["esmodules"])
    assert all(entry["path"] in names for entry in manifest["languages"])
    assert output.testzip() is None
print(f"OK: {archive.relative_to(ROOT)}, {len(names)} файлов; module.json в корне ZIP")
