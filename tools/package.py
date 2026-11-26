"""Create and inspect the Foundry distribution without publishing anything."""
from zipfile import ZIP_DEFLATED, ZipFile
from check_release import check_distribution, distribution_files
from validate import ROOT, validate

manifest = validate()
dist = ROOT / "dist"
dist.mkdir(exist_ok=True)
archive = dist / f'{manifest["id"]}.zip'
with ZipFile(archive, "w", ZIP_DEFLATED) as output:
    for path in distribution_files():
        output.write(path, path.relative_to(ROOT))
(dist / "module.json").write_bytes((ROOT / "module.json").read_bytes())
check_distribution(manifest)
print(f"OK: {archive.relative_to(ROOT)}; module.json в корне ZIP")
