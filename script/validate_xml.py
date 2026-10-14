"""Validate the project XML files.

Run from the repository root. Used by `make validate_xml` (CI) and, as a
library, by deploy_on_pull.py and cleanup_on_deploy.py, which refuse to act
when any XML is invalid.
"""

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from xml.etree import ElementTree

try:
    from . import scriptgen
except ImportError:
    import scriptgen

DEFAULT_DIRS = ("xml/obs", "xml/abs")

# XMLs whose project name cannot be derived: the project_pattern is a regex
# and no t/<brand>/<Project> test dir matches it. They predate this check, so
# they are accepted, but deploy_on_pull.py cannot create their project dirs
# when they are added. Do not add new entries: make the pattern literal or add
# a test dir instead (see README).
GRANDFATHERED = frozenset(
    {
        "xml/obs/openSUSE:Leap:15.xml",
        "xml/obs/openSUSE:Leap:15:ARM.xml",
        "xml/obs/openSUSE:Leap:15:Staging.xml",
        "xml/obs/openSUSE:Slowroll:Staging-images.xml",
    }
)

# abs is the test brand, its projects are never deployed
TEST_BRANDS = frozenset({"abs"})

# a group without nested groups or alternation: (?P<name>X), (?:X) or (X)
_SIMPLE_GROUP = re.compile(r"\((?:\?P<\w+>|\?:)?([^()|]*)\)")
_REGEX_META = frozenset(".^$*+?{}[]\\|()")


@dataclass
class Result:
    patterns: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def full_match(regex, name):
    """Same matching rule as scriptgen.parse_dir()."""
    m = regex.match(name)
    return bool(m) and m.group(0) == name


def literal_project(pattern):
    """Return the single project name a pattern matches, or None.

    Simple groups are unwrapped. A bare "." counts as a literal dot only
    between two digits (e.g. "15.6"); elsewhere it is a wildcard. Any other
    regex syntax makes the pattern non-literal.
    """
    s = pattern
    while True:
        unwrapped = _SIMPLE_GROUP.sub(lambda m: m.group(1), s)
        if unwrapped == s:
            break
        s = unwrapped

    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            if i + 1 < len(s) and not s[i + 1].isalnum():
                out.append(s[i + 1])
                i += 2
                continue
            return None
        if (
            c == "."
            and 0 < i < len(s) - 1
            and s[i - 1].isdigit()
            and s[i + 1].isdigit()
        ):
            out.append(c)
        elif c in _REGEX_META:
            return None
        else:
            out.append(c)
        i += 1

    name = "".join(out)
    try:
        regex = re.compile(pattern)
    except re.error:
        return None
    if not name or not full_match(regex, name):
        return None
    return name


def tracked_test_dirs(brand):
    """Names of the t/<brand>/* test dirs known to git (or on disk outside git)."""
    tdir = os.path.join("t", brand)
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z", "--", tdir],
            capture_output=True,
            check=True,
        ).stdout.decode()
        names = {p.split("/")[2] for p in out.split("\0") if p.count("/") >= 3}
        if names:
            return sorted(names)
    except (OSError, subprocess.CalledProcessError):
        pass
    if not os.path.isdir(tdir):
        return []
    return sorted(d for d in os.listdir(tdir) if os.path.isdir(os.path.join(tdir, d)))


def project_names(pattern, test_dirs):
    """Project dir names to create for an XML.

    The literal name of the pattern if it has one, else the test dirs that
    match the pattern.
    """
    name = literal_project(pattern)
    if name:
        return [name]
    try:
        regex = re.compile(pattern)
    except re.error:
        return []
    return sorted(d for d in test_dirs if full_match(regex, d))


def is_safe_name(name):
    return (
        bool(name) and "/" not in name and "\0" not in name and not name.startswith(".")
    )


def _check_batches(rel, root, result):
    nodes = list(root.iter("batch"))
    if nodes:
        names = []
        for node in nodes:
            name = node.attrib.get("name", "")
            if not name:
                result.errors.append(f"{rel}: <batch> without name attribute")
                continue
            if not is_safe_name(name) or name == "default":
                result.errors.append(f"{rel}: invalid batch name {name!r}")
            names.append(name)
    else:
        names = root.attrib.get("batches", "default").split("|")
        for name in names:
            if not is_safe_name(name):
                result.errors.append(
                    f"{rel}: invalid batch name {name!r} in batches attribute"
                )
    for name in sorted({n for n in names if names.count(n) > 1}):
        result.errors.append(f"{rel}: duplicate batch name {name!r}")


def _validate_file(path, brand, test_dirs, result):
    rel = os.path.normpath(path)
    try:
        root = ElementTree.parse(path).getroot()
    except (ElementTree.ParseError, OSError) as e:
        result.errors.append(f"{rel}: cannot parse: {e}")
        return
    if root.tag != "openQA":
        result.errors.append(f"{rel}: root element is <{root.tag}>, expected <openQA>")
        return
    pattern = root.attrib.get("project_pattern", "")
    if not pattern:
        result.errors.append(f"{rel}: missing project_pattern")
        return
    try:
        regex = re.compile(pattern)
    except re.error as e:
        result.errors.append(f"{rel}: invalid project_pattern {pattern!r}: {e}")
        return
    result.patterns[rel] = regex

    _check_batches(rel, root, result)

    names = project_names(pattern, test_dirs)
    try:
        ag = scriptgen.ActionGenerator(
            os.getcwd(), names[0] if names else "validate", "", "", brand
        )
        ag.doFile(path)
    except Exception as e:  # noqa: BLE001 - any failure makes the XML invalid
        result.errors.append(f"{rel}: scriptgen cannot process it: {e!r}")

    if not names:
        if rel not in GRANDFATHERED:
            result.errors.append(
                f"{rel}: cannot derive a project name from {pattern!r}: make the "
                f"pattern literal or add a matching t/{brand}/<Project> test dir"
            )
        return
    if brand not in TEST_BRANDS:
        for name in names:
            if ":" not in name or not is_safe_name(name):
                result.errors.append(
                    f"{rel}: project name {name!r} is not a valid project dir name"
                )
    if not any(full_match(regex, d) for d in test_dirs):
        result.warnings.append(
            f"{rel}: no t/{brand}/<Project> test dir matches {pattern!r}"
        )


def validate(dirs=DEFAULT_DIRS):
    """Validate all XMLs below dirs (paths relative to the repository root,
    which must be the cwd). Missing dirs (e.g. a dangling xml/ibs symlink) are
    skipped."""
    result = Result()
    for d in dirs:
        if not os.path.isdir(d):
            result.notes.append(f"{d}: not a directory, skipped")
            continue
        brand = os.path.basename(os.path.normpath(d))
        test_dirs = tracked_test_dirs(brand)
        brand_xmls = []
        for root, _, files in sorted(os.walk(d)):
            for f in sorted(files):
                if not f.endswith(".xml"):
                    continue
                path = os.path.join(root, f)
                _validate_file(path, brand, test_dirs, result)
                brand_xmls.append(os.path.normpath(path))

        # every test dir and derived project name must map to exactly one XML,
        # otherwise scriptgen picks one depending on the directory order
        brand_patterns = {
            x: result.patterns[x] for x in brand_xmls if x in result.patterns
        }
        candidates = set(test_dirs)
        for regex in brand_patterns.values():
            candidates.update(project_names(regex.pattern, test_dirs))
        for name in sorted(candidates):
            matching = sorted(
                x for x, r in brand_patterns.items() if full_match(r, name)
            )
            if len(matching) > 1:
                result.errors.append(
                    f"{name}: matched by more than one XML: {', '.join(matching)}"
                )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate project XML files.")
    parser.add_argument(
        "dirs", nargs="*", default=list(DEFAULT_DIRS), help="XML directories"
    )
    args = parser.parse_args(argv)
    result = validate(args.dirs)
    for n in result.notes:
        print("NOTE: " + n, file=sys.stderr)
    for w in result.warnings:
        print("WARNING: " + w, file=sys.stderr)
    for e in result.errors:
        print("ERROR: " + e, file=sys.stderr)
    if result.errors:
        return 1
    print(f"OK: {len(result.patterns)} XML files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
