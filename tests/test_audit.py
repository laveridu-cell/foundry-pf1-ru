"""Audit regressions use synthetic text, never redistribute upstream dictionaries."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("audit", ROOT / "tools/audit_localization.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.policy = {"groups": {"other": "Other", "unclassified": "Unclassified"},
                       "group_rules": [{"id": "other", "pattern": r"^PF1\.", "group": "other"}],
                       "notations": {"PF1.ID": "ID"}, "identity_review_prefixes": ["PF1.Language."]}

    def test_missing_english_technical_and_ambiguous_are_distinct(self):
        source = {"PF1.Missing": "Missing label", "PF1.English": "Click here", "PF1.ID": "ID",
                  "PF1.Abbr": "ABC", "PF1.Language.One": "InventedName", "PF1.Changed": "English label"}
        russian = {k: v for k, v in source.items() if k != "PF1.Missing"}
        russian["PF1.Changed"] = "An older English label"
        data = audit.build_inventory(source, russian, {}, self.policy)
        rows = {e["key"]: e for e in data["entries"]}
        self.assertEqual(rows["PF1.Missing"]["phenomen_status"], "missing")
        self.assertEqual(rows["PF1.English"]["phenomen_status"], "identical")
        self.assertEqual(rows["PF1.English"]["effective_coverage"], "untranslated")
        self.assertEqual(rows["PF1.Changed"]["effective_coverage"], "untranslated")
        self.assertEqual(rows["PF1.ID"]["effective_coverage"], "notation")
        self.assertEqual(rows["PF1.Abbr"]["effective_coverage"], "review")
        self.assertEqual(rows["PF1.Language.One"]["effective_coverage"], "review")

    def test_own_overlay_is_effective_but_does_not_hide_upstream_state(self):
        data = audit.build_inventory({"PF1.Save": "Save"}, {"PF1.Save": "Испытание"},
                                     {"PF1.Save": {"value": "Сохранить", "path": "own.json"}}, self.policy)
        row = data["entries"][0]
        self.assertEqual(row["module"]["value"], "Сохранить")
        self.assertEqual(row["phenomen"]["sha256"], audit.digest("Испытание"))
        self.assertIsNone(row["phenomen"]["value"])

    def test_placeholder_multiplicity_markup_links_and_rolls(self):
        original = '<a href="/one" data-id="fixed">{name} {name}</a> [[/r 1d6]] @UUID[Actor.a] <code>@hp.max</code>'
        changed = '<a href="/two" data-id="changed">{name}</a> [[/r 2d6]] @UUID[Actor.b] <code>@hp.min</code>'
        issues = audit.differences(original, changed)
        for feature in ["placeholders", "html_attributes", "inline_rolls", "enriched_targets", "formula_references", "code"]:
            self.assertIn(f"technical:{feature}", issues)
        self.assertFalse(audit.differences('<b>{name}</b><br>', '<b>{name}</b><br/>'))
        self.assertIn("technical:html_tags", audit.differences('<b>One</b>', 'Один'))
        self.assertIn("technical:invalid_translation_html", audit.differences('<b>One</b>', '<b>Один'))
        self.assertEqual(set(audit.differences("Roll 1d6 @Check[reflex]", "Бросок 2d6 @Check[fortitude]")),
                         {"technical:dice", "technical:enriched_targets"})

    def test_duplicate_and_colliding_keys_fail_instead_of_silently_overwriting(self):
        with self.assertRaises(ValueError):
            audit.flatten({"PF1": {"One": "A"}, "PF1.One": "B"})
        with self.assertRaises(ValueError):
            audit.unique_object([("A", "one"), ("A", "two")])

    def test_update_reports_added_removed_changed_and_retains_own_translation(self):
        own = {"PF1.Keep": {"value": "Утверждено", "path": "own.json"}}
        before = audit.build_inventory({"PF1.Keep": "Old", "PF1.Remove": "Remove"}, {}, own, self.policy)
        after = audit.build_inventory({"PF1.Keep": "New", "PF1.Add": "Add"}, {}, own, self.policy)
        change = audit.compare(before, after)
        self.assertEqual(change["added"], ["PF1.Add"])
        self.assertEqual(change["removed"], ["PF1.Remove"])
        self.assertEqual(change["changed"], [{"key": "PF1.Keep", "changed_sources": ["english"]}])
        self.assertEqual(next(e for e in after["entries"] if e["key"] == "PF1.Keep")["module"]["value"], "Утверждено")
        self.assertFalse(change["writes_translations"])

    def test_phenomen_changes_and_obsolete_keys_are_reported_separately(self):
        before = audit.build_inventory({"PF1.One": "One"}, {"PF1.One": "Один", "PF1.Obsolete": "Старое"}, {}, self.policy)
        after = audit.build_inventory({"PF1.One": "One"}, {"PF1.One": "Другой", "PF1.Extra": "Лишнее"}, {}, self.policy)
        change = audit.compare(before, after)
        self.assertEqual(change["changed"], [{"key": "PF1.One", "changed_sources": ["phenomen"]}])
        self.assertEqual(change["phenomen_only_delta"], {"added": ["PF1.Extra"], "removed": ["PF1.Obsolete"], "changed": []})

    def test_unknown_context_stays_unclassified_and_private_output_cannot_enter_repo(self):
        self.assertEqual(audit.group_for("UNKNOWN.One", self.policy)[0], "unclassified")
        with self.assertRaises(ValueError):
            audit.write_json(ROOT / "lang/system/pf1.json", {})
        with self.assertRaises(ValueError):
            audit.write_json(audit.AUDIT / "private.json", {}, private=True)
        with tempfile.TemporaryDirectory() as folder:
            audit.write_json(Path(folder) / "private.json", {}, private=True)

    def test_long_english_sentence_is_not_exempt_because_key_ends_in_short(self):
        self.assertEqual(audit.coverage("PF1.RangeShort", "25 ft. plus five feet per level",
                                       "25 ft. plus five feet per level", self.policy)[0], "untranslated")
        self.assertEqual(audit.coverage("PF1.Format", "{value} – {unit}", "{value} – {unit}", self.policy)[0], "notation")

    def test_public_inventory_is_consistent_and_has_no_full_upstream_text(self):
        audit.check_inventory(audit.AUDIT / "inventory.json")


if __name__ == "__main__":
    unittest.main()
