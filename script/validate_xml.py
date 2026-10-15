"""Validate the project XML files.

Run from the repository root. Used by `make validate_xml` (CI) and, as a
library, by deploy_on_pull.py and cleanup_on_deploy.py, which refuse to act
when any XML is invalid.

The structure (elements, attributes, batch names) is checked by the schema
xml/openQA.rng in `make validate_xml` only. This module checks what the
schema cannot: the project_pattern regex, unique batch names, that scriptgen
can process the file, the values of <projects_enabled>, and that every
project maps to exactly one XML.
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

# XMLs whose project name cannot be derived (see project_names): the
# project_pattern is a regex, it has no <projects_enabled> and no
# t/<brand>/<Project> test dir matches it. They predate this check, so they
# are accepted, but deploy_on_pull.py cannot create their project dirs. Do not
# add new entries: make the pattern literal, add <projects_enabled> or add a
# test dir instead (see README).
GRANDFATHERED = frozenset(
    {
        "xml/obs/openSUSE:Leap:15.xml",
        "xml/obs/openSUSE:Leap:15:ARM.xml",
        "xml/obs/openSUSE:Leap:15:Staging.xml",
        "xml/obs/openSUSE:Slowroll:Staging-images.xml",
        "xml/ibs/SUSE:SLE-15:Update:SLERT.xml",
    }
)

# abs is the test brand, its projects are never deployed
TEST_BRANDS = frozenset({"abs"})

# more names than this make a pattern count as not enumerable
MAX_PROJECTS = 64
# at most this many projects can be enabled by one XML
MAX_ENABLED = 256

_QUANTIFIER = re.compile(r"[+*?]|\{\d+(?:,\d*)?\}")


@dataclass
class Result:
    patterns: dict = field(default_factory=dict)
    # {xml: [project names]} of the XMLs with <projects_enabled>
    enabled: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def full_match(regex, name):
    """Same matching rule as scriptgen.parse_dir()."""
    m = regex.match(name)
    return bool(m) and m.group(0) == name


class _NotEnumerable(Exception):
    pass


class _Parser:
    r"""Parse a regex into a tree whose names can be enumerated.

    Enumerable: literals, escaped punctuation, groups ((...), (?:...),
    (?P<name>...)), alternation, character classes without negation, and the
    quantifiers ? and {m} / {m,n}. A bare "." is a literal dot only between two
    digits (e.g. "15.6"). Other wildcards and quantifiers (".", "\d", "[^x]",
    "*", "+") become ("any",) nodes; syntax the parser does not know (anchors,
    lookarounds) raises _NotEnumerable.

    Nodes: ("lit", str), ("set", chars), ("any",), ("cat", nodes),
    ("alt", nodes), ("group", name, node), ("rep", node, min, max).
    """

    def __init__(self, pattern):
        self.s = pattern
        self.i = 0

    def parse(self):
        node = self.alternation()
        if self.i != len(self.s):
            raise _NotEnumerable
        return node

    def peek(self):
        return self.s[self.i] if self.i < len(self.s) else ""

    def alternation(self):
        branches = [self.sequence()]
        while self.peek() == "|":
            self.i += 1
            branches.append(self.sequence())
        return branches[0] if len(branches) == 1 else ("alt", branches)

    def sequence(self):
        items = []
        while self.peek() not in ("", "|", ")"):
            items.append(self.quantified())
        return ("cat", items)

    def quantified(self):
        node = self.atom()
        c = self.peek()
        if c == "?":
            self.i += 1
            node = ("rep", node, 0, 1)
        elif c in ("*", "+"):
            self.i += 1
            node = ("any",)
        elif c == "{":
            m = re.compile(r"\{(\d+)(?:(,)(\d*))?\}").match(self.s, self.i)
            if not m:
                raise _NotEnumerable
            self.i = m.end()
            low = int(m.group(1))
            if not m.group(2):
                node = ("rep", node, low, low)
            elif m.group(3) and int(m.group(3)) >= low:
                node = ("rep", node, low, int(m.group(3)))
            else:
                node = ("any",)
        else:
            return node
        if self.peek() in ("?", "+"):
            self.i += 1
        return node

    def atom(self):
        s, i = self.s, self.i
        c = s[i]
        if c == "(":
            self.i += 1
            name = None
            if s.startswith("?P<", self.i):
                end = s.find(">", self.i)
                if end < 0:
                    raise _NotEnumerable
                name = s[self.i + 3 : end]
                self.i = end + 1
            elif s.startswith("?:", self.i):
                self.i += 2
            elif self.peek() == "?":
                raise _NotEnumerable
            node = self.alternation()
            if self.peek() != ")":
                raise _NotEnumerable
            self.i += 1
            return ("group", name, node)
        if c == "[":
            return self.char_class()
        self.i += 1
        if c == "\\":
            self.i += 1
            nxt = s[i + 1 : i + 2]
            if not nxt:
                raise _NotEnumerable
            return ("any",) if nxt.isalnum() else ("lit", nxt)
        if c == ".":
            if 0 < i < len(s) - 1 and s[i - 1].isdigit() and s[i + 1].isdigit():
                return ("lit", c)
            return ("any",)
        if c in "^$*+?{}]":
            raise _NotEnumerable
        return ("lit", c)

    def char_class(self):
        self.i += 1
        negated = self.peek() == "^"
        if negated:
            self.i += 1
        if self.peek() == "]":
            raise _NotEnumerable
        chars = set()
        unbounded = negated
        while self.peek() != "]":
            low = self.class_char()
            if self.peek() == "-" and self.s[self.i + 1 : self.i + 2] not in ("]", ""):
                self.i += 1
                high = self.class_char()
                if low is None or high is None or high < low:
                    unbounded = True
                else:
                    chars.update(chr(o) for o in range(ord(low), ord(high) + 1))
            elif low is None:
                unbounded = True
            else:
                chars.add(low)
        self.i += 1
        return ("any",) if unbounded else ("set", sorted(chars))

    def class_char(self):
        r"""The next character of a class, None for a class escape like \d."""
        c = self.peek()
        if not c or c == "[":
            raise _NotEnumerable
        self.i += 1
        if c != "\\":
            return c
        nxt = self.peek()
        if not nxt:
            raise _NotEnumerable
        self.i += 1
        return None if nxt.isalnum() else nxt


def _limited(names):
    if len(names) > MAX_PROJECTS:
        raise _NotEnumerable
    return names


def _expand(node):
    kind = node[0]
    if kind == "any":
        raise _NotEnumerable
    if kind == "lit":
        return {node[1]}
    if kind == "set":
        return _limited(set(node[1]))
    if kind == "cat":
        names = {""}
        for item in node[1]:
            tails = _expand(item)
            names = _limited({a + b for a in names for b in tails})
        return names
    if kind == "alt":
        return _limited(set().union(*(_expand(b) for b in node[1])))
    if kind == "group":
        return _expand(node[2])
    _, child, low, high = node
    once = _expand(child)
    names = set()
    current = {""}
    for count in range(high + 1):
        if count >= low:
            names = _limited(names | current)
        if count < high:
            current = _limited({a + b for a in current for b in once})
    return names


def expand_pattern(pattern):
    """Return the sorted names a pattern matches, or None if they cannot be
    enumerated (unsupported syntax or more than MAX_PROJECTS names)."""
    try:
        regex = re.compile(pattern)
        names = _expand(_Parser(pattern).parse())
    except (re.error, _NotEnumerable):
        return None
    return sorted(n for n in names if full_match(regex, n))


def literal_project(pattern):
    """Return the single project name a pattern matches, or None."""
    names = expand_pattern(pattern)
    if names and len(names) == 1 and names[0]:
        return names[0]
    return None


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
    """Project dir names of an XML without <projects_enabled>.

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


def find_slots(pattern):
    """[(start, end)] of each character class in pattern, with its quantifier."""
    slots = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "\\":
            i += 2
            continue
        if c != "[":
            i += 1
            continue
        start = i
        i += 1
        if pattern[i : i + 1] == "^":
            i += 1
        if pattern[i : i + 1] == "]":
            i += 1
        while i < len(pattern) and pattern[i] != "]":
            i += 2 if pattern[i] == "\\" else 1
        i += 1
        m = _QUANTIFIER.match(pattern, i)
        if m:
            i = m.end()
        slots.append((start, i))
    return slots


def _value_class(value):
    if value.isascii() and value.isdigit():
        return "number"
    if value.isascii() and value.isalpha():
        return "letters"
    return None


def _range_values(text):
    """The values of an inclusive range "X..Y", or raise ValueError."""
    low, sep, high = text.partition("..")
    if not sep or "." in high:
        raise ValueError("expected X..Y")
    classes = {_value_class(low), _value_class(high)}
    if classes == {"number"}:
        start, end, fmt = int(low), int(high), str
    elif classes == {"letters"} and len(low) == len(high) == 1:
        if low.isupper() != high.isupper():
            raise ValueError("both ends must have the same case")
        start, end, fmt = ord(low), ord(high), chr
    else:
        raise ValueError("both ends must be single letters or both numbers")
    if start > end:
        raise ValueError("the start is after the end")
    # checked before building the list, a huge range must not exhaust memory
    if end - start + 1 > MAX_ENABLED:
        raise ValueError(f"more than {MAX_ENABLED} values")
    return [fmt(v) for v in range(start, end + 1)], classes.pop()


def enabled_names(root, pattern):
    """Return (names, errors) of the <projects_enabled> elements of root.

    names is None if root has no such element. Each value replaces the one
    character class (with its quantifier) of the pattern; the rest of the
    pattern must be enumerable (e.g. literal alternatives).
    """
    elements = list(root.iter("projects_enabled"))
    if not elements:
        return None, []
    errors = []
    slots = find_slots(pattern)
    if len(slots) != 1:
        return [], [
            (
                f"<projects_enabled> needs exactly one character class in {pattern!r}, "
                f"found {len(slots)}"
            )
        ]
    start, end = slots[0]
    slot = re.compile(pattern[start:end])
    regex = re.compile(pattern)
    names = set()
    for element in elements:
        values = []
        range_class = None
        if "range" in element.attrib:
            try:
                values, range_class = _range_values(element.attrib["range"])
            except ValueError as e:
                errors.append(f"invalid range {element.attrib['range']!r}: {e}")
                continue
        project = element.attrib.get("project")
        extra = project.split(",") if project is not None else []
        expected = range_class or (_value_class(extra[0]) if extra else None)
        for value in extra:
            if _value_class(value) is None or _value_class(value) != expected:
                errors.append(
                    f"project {value!r} is not of the same class as the other values "
                    "(letters or a number)"
                )
            elif value not in values:
                values.append(value)
        for value in values:
            if not full_match(slot, value):
                errors.append(f"{value!r} does not match {slot.pattern!r}")
                continue
            expanded = expand_pattern(
                pattern[:start] + re.escape(value) + pattern[end:]
            )
            if not expanded:
                errors.append(
                    f"cannot derive the project names of {value!r} from {pattern!r}: "
                    "the pattern outside the character class must be literal"
                )
                continue
            names.update(n for n in expanded if n and full_match(regex, n))
    if len(names) > MAX_ENABLED:
        errors.append(f"more than {MAX_ENABLED} enabled projects")
    return sorted(names), errors


def is_safe_name(name):
    return (
        bool(name) and "/" not in name and "\0" not in name and not name.startswith(".")
    )


def _check_batches(rel, root, result):
    nodes = list(root.iter("batch"))
    if nodes:
        names = [node.attrib.get("name", "") for node in nodes]
    else:
        names = root.attrib.get("batches", "default").split("|")
    for name in sorted({n for n in names if names.count(n) > 1}):
        result.errors.append(f"{rel}: duplicate batch name {name!r}")


def _validate_file(path, brand, test_dirs, result):
    rel = os.path.normpath(path)
    try:
        root = ElementTree.parse(path).getroot()
    except (ElementTree.ParseError, OSError) as e:
        result.errors.append(f"{rel}: cannot parse: {e}")
        return
    pattern = root.attrib.get("project_pattern", "")
    try:
        regex = re.compile(pattern)
    except re.error as e:
        result.errors.append(f"{rel}: invalid project_pattern {pattern!r}: {e}")
        return
    result.patterns[rel] = regex

    _check_batches(rel, root, result)

    enabled, errors = enabled_names(root, pattern)
    result.errors.extend(f"{rel}: {e}" for e in errors)
    if enabled is not None:
        result.enabled[rel] = enabled
        names = enabled
    else:
        names = project_names(pattern, test_dirs)
    try:
        ag = scriptgen.ActionGenerator(
            os.getcwd(), names[0] if names else "validate", "", "", brand
        )
        ag.doFile(path)
    except Exception as e:  # noqa: BLE001 - any failure makes the XML invalid
        result.errors.append(f"{rel}: scriptgen cannot process it: {e!r}")

    if not names:
        if enabled is None and rel not in GRANDFATHERED:
            result.errors.append(
                f"{rel}: cannot derive a project name from {pattern!r}: make the "
                f"pattern literal, add <projects_enabled> or add a matching "
                f"t/{brand}/<Project> test dir"
            )
        return
    if brand not in TEST_BRANDS:
        for name in names:
            if ":" not in name or not is_safe_name(name):
                result.errors.append(
                    f"{rel}: project name {name!r} is not a valid project dir name"
                )
    matching = [d for d in test_dirs if full_match(regex, d)]
    if not matching:
        result.warnings.append(
            f"{rel}: no t/{brand}/<Project> test dir matches {pattern!r}"
        )
    if enabled is not None:
        for d in matching:
            if d not in enabled:
                result.warnings.append(
                    f"{rel}: test dir t/{brand}/{d} is not in <projects_enabled>"
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
        for x, regex in brand_patterns.items():
            if x in result.enabled:
                candidates.update(result.enabled[x])
            else:
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
