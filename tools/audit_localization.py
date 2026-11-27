"""Read-only, reproducible PF1 localization audit; never writes runtime translations."""
import argparse
from collections import Counter, defaultdict
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs/localization-audit"
CYRILLIC = re.compile(r"[\u0400-\u04ff]")
KEY = re.compile(r"(?<![\w.])(?:PF1|TOKEN|TYPES|EFFECT)\.[\w.-]+")


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def flatten(data, prefix=""):
    if not isinstance(data, dict):
        raise ValueError(f"Expected dictionary: {prefix}")
    result = {}
    for key, value in data.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            children = flatten(value, name)
            if result.keys() & children.keys():
                raise ValueError(f"Colliding dotted/nested keys: {name}")
            result.update(children)
        else:
            if not isinstance(value, str) or name in result:
                raise ValueError(f"Non-string or colliding key: {name}")
            result[name] = value
    return result


class Markup(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.tags, self.attributes, self.stack, self.errors = [], [], [], []
        self.feed(text)
        self.close()
        self.errors.extend(f"unclosed:{tag}" for tag in self.stack)

    def handle_starttag(self, tag, attrs):
        self.tags.append(f"<{tag}>")
        # Visible title/alt text may be translated; automation attributes may not.
        self.attributes.extend((tag, name, value or "") for name, value in attrs if name not in {"title", "alt"})
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        self.tags.append(f"</{tag}>")
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.errors.append(f"unexpected-close:{tag}")


def technical(text):
    markup = Markup(text)
    return {
        "placeholders": sorted(Counter(re.findall(r"(?<!\{)\{[^{}]+\}(?!\})", text)).items()),
        "html_tags": markup.tags,
        "html_attributes": sorted(markup.attributes),
        "enriched_targets": sorted(re.findall(r"@[A-Za-z][\w.]*\[[^\]]+\]", text)),
        "inline_rolls": sorted(re.findall(r"\[\[.*?\]\]", text, re.S)),
        "formula_references": sorted(re.findall(r"@[A-Za-z_]\w*(?:\.\w+)+", text)),
        "dice": sorted(re.findall(r"\b\d*d\d+\b", text)),
        "code": re.findall(r"<code\b[^>]*>(.*?)</code>", text, re.S | re.I),
        "urls": sorted(re.findall(r"https?://[^\s<>\"']+", text)),
        "html_errors": markup.errors,
    }


def differences(english, translation):
    if translation is None:
        return []
    left, right = technical(english), technical(translation)
    issues = [f"technical:{key}" for key in left if key != "html_errors" and left[key] != right[key]]
    if right["html_errors"] and right["html_errors"] != left["html_errors"]:
        issues.append("technical:invalid_translation_html")
    return issues


def raw_status(english, russian):
    if russian is None:
        return "missing"
    if not russian.strip():
        return "empty"
    return "identical" if english == russian else "different"


def coverage(key, english, russian, policy):
    if russian is None or not russian.strip():
        return "untranslated", "missing_or_empty"
    if CYRILLIC.search(russian):
        return "translated", "cyrillic_present_not_quality_approval"
    if russian == english:
        if policy.get("notations", {}).get(key) == english:
            return "notation", "explicit_technical_notation"
        visible = re.sub(r"\{[^{}]*\}|<[^>]+>", "", russian)
        if not re.search(r"[A-Za-z]", visible):
            return "notation", "no_language_words"
        for prefix in policy.get("identity_review_prefixes", []):
            if key.startswith(prefix):
                return "review", "name_or_source_title_needs_review"
        if re.fullmatch(r"[A-Z0-9/().+ −-]{1,12}", russian) or (
                len(russian) <= 12 and re.search(r"(?:Abbr|Short)(?:\.|$)", key)):
            return "review", "abbreviation_needs_context"
    return "untranslated", "english_text_remains"


def group_for(key, policy):
    # Ordered explicit rules only. Unrecognized/new keys stay unclassified.
    for rule in policy["group_rules"]:
        if re.search(rule["pattern"], key):
            return rule["group"], rule["id"]
    return "unclassified", "no_matching_rule"


def source_usages(root, keys):
    result = defaultdict(list)
    files = [root / "pf1.mjs"]
    for directory in ["module", "public/templates", "public/tours", "help"]:
        files.extend(sorted((root / directory).rglob("*")))
    for path in files:
        if not path.is_file() or path.suffix not in {".mjs", ".hbs", ".json", ".html"}:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for key in set(KEY.findall(line)) & keys:
                result[key].append({"path": path.relative_to(root).as_posix(), "line": number})
    return result


def describe(value, private=False):
    if value is None:
        return {"present": False, "value": None, "sha256": None, "length": 0}
    return {"present": True, "value": value if private else None,
            "sha256": digest(value), "length": len(value)}


def summarize(entries, groups):
    rows = {name: {"total": 0, "translated": 0, "untranslated": 0, "notation": 0,
                   "review": 0, "needs_review": 0} for name in groups}
    for entry in entries:
        row = rows[entry["group"]]
        row["total"] += 1
        row[entry["effective_coverage"]] += 1
        row["needs_review"] += bool(entry["review_flags"])
    return {"total": len(entries), "phenomen_status": dict(Counter(e["phenomen_status"] for e in entries)),
            "phenomen_coverage": dict(Counter(e["phenomen_coverage"] for e in entries)),
            "effective_coverage": dict(Counter(e["effective_coverage"] for e in entries)),
            "module_keys": sum(e["module"]["present"] for e in entries),
            "technical_mismatch_keys": sum(bool(e["phenomen_technical_issues"]) for e in entries),
            "groups": rows}


def build_inventory(english, russian, overlays, policy, usages=None, private=False):
    usages = usages or {}
    entries = []
    for key, original in sorted(english.items()):
        existing = russian.get(key)
        own = overlays.get(key)
        effective = own["value"] if own else existing
        base_coverage, _ = coverage(key, original, existing, policy)
        state, reason = coverage(key, original, effective, policy)
        group, rule = group_for(key, policy)
        base_issues = differences(original, existing)
        effective_issues = differences(original, effective)
        flags = list(effective_issues)
        if state == "review":
            flags.append(reason)
        if group == "unclassified":
            flags.append("unclassified_context")
        review_ids = [item["id"] for item in policy.get("reviews", []) if key in item["keys"]]
        flags.extend(f"editorial:{item}" for item in review_ids)
        if effective and CYRILLIC.search(effective):
            visible = re.sub(r"<[^>]+>|\{[^{}]+\}|@[A-Za-z]+\[[^\]]+\]|https?://\S+", "", effective)
            if re.search(r"\b[A-Za-z]{3,}\b", visible):
                flags.append("mixed_script_needs_context")
        entries.append({
            "key": key, "english": describe(original, private), "phenomen": describe(existing, private),
            "module": {"present": own is not None, "value": own["value"] if own else None,
                       "path": own["path"] if own else None,
                       "sha256": digest(own["value"]) if own else None},
            "phenomen_status": raw_status(original, existing),
            "phenomen_coverage": base_coverage, "effective_coverage": state, "coverage_reason": reason,
            "group": group, "group_rule": rule,
            "phenomen_technical_issues": base_issues, "effective_technical_issues": effective_issues,
            "review_flags": sorted(set(flags)), "review_ids": review_ids,
            "approved_term": policy.get("approved_terms", {}).get(key),
            "static_usages_count": len(usages.get(key, [])), "static_usages": usages.get(key, [])[:3],
        })
    return {"schema_version": 1, "values_mode": "private_full" if private else "public_fingerprints",
            "groups": policy["groups"], "summary": summarize(entries, policy["groups"]), "entries": entries,
            "phenomen_only": [{"key": key, "phenomen": describe(russian[key], private)}
                              for key in sorted(russian.keys() - english.keys())]}


def compare(before, after):
    old, new = ({e["key"]: e for e in data["entries"]} for data in [before, after])
    changed = []
    for key in sorted(old.keys() & new.keys()):
        fields = [field for field in ["english", "phenomen", "module"]
                  if old[key][field].get("sha256") != new[key][field].get("sha256")]
        if fields:
            changed.append({"key": key, "changed_sources": fields})
    extra_old, extra_new = ({e["key"]: e["phenomen"]["sha256"] for e in data.get("phenomen_only", [])}
                            for data in [before, after])
    return {"added": sorted(new.keys() - old.keys()), "removed": sorted(old.keys() - new.keys()),
            "changed": changed, "phenomen_only_delta": {
                "added": sorted(extra_new.keys() - extra_old.keys()),
                "removed": sorted(extra_old.keys() - extra_new.keys()),
                "changed": sorted(key for key in extra_old.keys() & extra_new.keys() if extra_old[key] != extra_new[key])},
            "writes_translations": False}


def write_json(path, value, private=False):
    path = Path(path).resolve()
    if path.is_relative_to(ROOT) and (private or not path.is_relative_to(AUDIT)):
        raise ValueError("Audit output must be in docs/localization-audit; private values must be outside the repository")
    path.parent.mkdir(parents=True, exist_ok=True)
    if "entries" in value:
        # One key per physical line makes future inventory diffs reviewable.
        header = json.dumps({k: v for k, v in value.items() if k != "entries"}, ensure_ascii=False, indent=2)
        rows = ["    " + json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in value["entries"]]
        start = header[:-2] + "," if len(value) > 1 else "{"
        output = start + '\n  "entries": [\n' + ",\n".join(rows) + "\n  ]\n}\n"
    else:
        output = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.write_text(output, encoding="utf-8")


def generate(args):
    policy, lock = read_json(args.policy), read_json(args.sources)
    paths = {"pf1": Path(args.pf1_root) / lock["pf1"]["file"],
             "phenomen": Path(args.phenomen_root) / lock["phenomen"]["file"]}
    for name, path in paths.items():
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        if observed != lock[name]["sha256"]:
            raise ValueError(f"{name}: source hash differs from the lock; prepare a new source lock for an update")
    pf1_root = Path(args.pf1_root)
    if (pf1_root / ".git").exists():
        observed_commit = subprocess.check_output(["git", "-C", str(pf1_root), "rev-parse", "HEAD"], text=True).strip()
        if observed_commit != lock["pf1"]["commit"]:
            raise ValueError("PF1 checkout commit differs from the source lock")
    for name, manifest_path in [("pf1", pf1_root / "public/system.json"),
                                ("phenomen", Path(args.phenomen_root) / "module.json")]:
        if read_json(manifest_path)["version"] != lock[name]["version"]:
            raise ValueError(f"{name}: manifest version differs from the source lock")
    english, russian = (flatten(read_json(paths[name])) for name in ["pf1", "phenomen"])
    overlays = {}
    for entry in read_json(ROOT / "module.json")["languages"]:
        if entry.get("system") != "pf1":
            continue
        for key, value in flatten(read_json(ROOT / entry["path"])).items():
            overlays[key] = {"value": value, "path": entry["path"]}
    result = build_inventory(english, russian, overlays, policy,
                             source_usages(Path(args.pf1_root), set(english)), args.private_values)
    result["sources"] = lock
    result["policy_sha256"] = hashlib.sha256(Path(args.policy).read_bytes()).hexdigest()
    result["unmatched_policy_keys"] = sorted(
        ({key for review in policy.get("reviews", []) for key in review["keys"]}
         | set(policy.get("notations", {})) | set(policy.get("approved_terms", {}))) - english.keys())
    write_json(args.output, result, args.private_values)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


def check_inventory(path):
    data = read_json(path)
    if data["values_mode"] != "public_fingerprints":
        raise ValueError("A public inventory must not contain full upstream values")
    keys = [entry["key"] for entry in data["entries"]]
    if keys != sorted(set(keys)):
        raise ValueError("Inventory keys must be unique and sorted")
    for entry in [*data["entries"], *data.get("phenomen_only", [])]:
        for field in ["english", "phenomen"]:
            if field in entry and entry[field]["value"] is not None:
                raise ValueError("Full upstream text found in public inventory")
    if data["summary"] != summarize(data["entries"], data["groups"]):
        raise ValueError("Inventory summary does not match entries")
    if data.get("unmatched_policy_keys"):
        raise ValueError("Policy refers to keys absent from the original")
    print(f"OK audit inventory: {len(keys)} keys; upstream values withheld")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("generate")
    run.add_argument("--pf1-root", required=True)
    run.add_argument("--phenomen-root", required=True)
    run.add_argument("--policy", default=str(AUDIT / "policy.json"))
    run.add_argument("--sources", default=str(AUDIT / "sources.json"))
    run.add_argument("--output", default=str(AUDIT / "inventory.json"))
    run.add_argument("--private-values", action="store_true")
    delta = sub.add_parser("compare")
    delta.add_argument("before")
    delta.add_argument("after")
    delta.add_argument("--output")
    check = sub.add_parser("check")
    check.add_argument("path", nargs="?", default=str(AUDIT / "inventory.json"))
    args = parser.parse_args()
    try:
        if args.command == "generate":
            generate(args)
        elif args.command == "check":
            check_inventory(args.path)
        else:
            result = compare(read_json(args.before), read_json(args.after))
            if args.output:
                write_json(args.output, result)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit(f"ERROR: {error}")


if __name__ == "__main__":
    main()
