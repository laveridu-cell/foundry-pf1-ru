"""Exercise version changes and release artifacts in isolated repository copies."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="pf1-ru-release-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "module"
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns(".git", "dist", "node_modules", "__pycache__"))
        self.initial = json.loads((self.root / "module.json").read_text())
        self.version = self.initial["version"]
        self.major, self.minor, self.patch = map(int, self.version.split("."))
        self.next = f"{self.major}.{self.minor}.{self.patch + 1}"

    def run_tool(self, tool, *args, success=True):
        result = subprocess.run([sys.executable, str(self.root / "tools" / tool), *args],
                                cwd=self.root, capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_patch_builds_an_installable_release_with_synchronized_versions(self):
        self.run_tool("bump_version.py", "patch")
        manifest = json.loads((self.root / "module.json").read_text())
        self.assertEqual(manifest["version"], self.next)
        self.assertEqual(json.loads((self.root / "package.json").read_text())["version"], self.next)
        self.assertEqual(manifest["download"],
                         f"https://github.com/laveridu-cell/foundry-pf1-ru/releases/download/v{self.next}/foundry-pf1-ru.zip")
        self.assertEqual(manifest["id"], self.initial["id"])
        self.assertEqual(manifest["manifest"], self.initial["manifest"])
        self.assertEqual(manifest["compatibility"], self.initial["compatibility"])
        self.assertEqual(manifest["relationships"], self.initial["relationships"])
        self.run_tool("package.py")
        self.run_tool("check_release.py", "--tag", f"v{self.next}")
        self.run_tool("check_release.py", "--tag", f"v{self.version}", success=False)
        with ZipFile(self.root / "dist/foundry-pf1-ru.zip") as bundle:
            self.assertEqual(json.loads(bundle.read("module.json")), manifest)

    def test_exact_version_and_dry_run(self):
        before = [(self.root / name).read_bytes() for name in ["module.json", "package.json"]]
        self.run_tool("bump_version.py", self.next, "--dry-run")
        self.assertEqual(before, [(self.root / name).read_bytes() for name in ["module.json", "package.json"]])
        self.run_tool("bump_version.py", self.next)
        self.run_tool("validate.py", "--tag", f"v{self.next}")

    def test_same_lower_or_malformed_version_cannot_change_files(self):
        before = [(self.root / name).read_bytes() for name in ["module.json", "package.json"]]
        for target in [self.version, "0.0.0", f"v{self.next}", "01.2.3", "invalid"]:
            with self.subTest(target=target):
                self.run_tool("bump_version.py", target, success=False)
                self.assertEqual(before, [(self.root / name).read_bytes() for name in ["module.json", "package.json"]])

    def test_stale_manifest_or_zip_is_rejected(self):
        self.run_tool("package.py")
        standalone = self.root / "dist/module.json"
        original = standalone.read_bytes()
        changed = json.loads(original)
        changed["version"] = self.next
        standalone.write_text(json.dumps(changed))
        self.run_tool("check_release.py", success=False)
        standalone.write_bytes(original)
        archive = self.root / "dist/foundry-pf1-ru.zip"
        with ZipFile(archive) as bundle:
            entries = {name: bundle.read(name) for name in bundle.namelist()}
        entries["module.json"] = json.dumps(changed).encode()
        with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
            for name, data in entries.items():
                bundle.writestr(name, data)
        self.run_tool("check_release.py", success=False)
        entries["module.json"] = original
        del entries["scripts/localization.mjs"]
        with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
            for name, data in entries.items():
                bundle.writestr(name, data)
        self.run_tool("check_release.py", success=False)

    def test_wrong_download_or_manifest_or_id_is_rejected(self):
        path = self.root / "module.json"
        for key, value in [("download", self.initial["manifest"]),
                           ("manifest", self.initial["download"]), ("id", "another-module")]:
            with self.subTest(key=key):
                data = dict(self.initial)
                data[key] = value
                path.write_text(json.dumps(data))
                self.run_tool("validate.py", "--tag", f"v{self.version}", success=False)

    def test_glossary_policy_source_needs_explicit_approval(self):
        path = self.root / "terminology/glossary.json"
        glossary = json.loads(path.read_text())
        term = next(term for term in glossary["terms"] if term["source"] == "AGENTS.md")
        del term["approvedBy"]
        path.write_text(json.dumps(glossary))
        self.run_tool("validate.py", success=False)

    def test_mapped_glossary_terms_still_have_to_match_localization(self):
        path = self.root / "terminology/glossary.json"
        glossary = json.loads(path.read_text())
        term = next(term for term in glossary["terms"] if term.get("key") == "PF1.Save")
        term["ru"] = "Испытание"
        path.write_text(json.dumps(glossary))
        self.run_tool("validate.py", success=False)

    def test_core_rulebook_source_with_citation_is_supported(self):
        path = self.root / "terminology/glossary.json"
        glossary = json.loads(path.read_text())
        term = next(term for term in glossary["terms"] if term["source"] == "AGENTS.md")
        term["source"] = "user-core-rulebook"
        term["reference"] = "Тестовая библиографическая ссылка и страница; не реальное издание"
        del term["approvedBy"]
        path.write_text(json.dumps(glossary))
        self.run_tool("validate.py")

    def test_audit_materials_are_not_distributed(self):
        audit = self.root / "docs/localization-audit/upstream/nested"
        audit.mkdir(parents=True, exist_ok=True)
        (audit / "source.json").write_text('{"not-for-distribution": "local audit only"}')
        self.run_tool("package.py")
        self.run_tool("check_release.py")
        with ZipFile(self.root / "dist/foundry-pf1-ru.zip") as bundle:
            self.assertFalse(any(name.startswith("docs/localization-audit/") for name in bundle.namelist()))


if __name__ == "__main__":
    unittest.main()
