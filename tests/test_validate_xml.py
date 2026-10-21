import os
import subprocess
from pathlib import Path
from xml.etree import ElementTree

import pytest

from script import deploy_common, scriptgen, validate_xml

REPO = Path(__file__).resolve().parent.parent

FLAVOR = '<flavor name="FLAVOR" distri="distri" iso="iso"/>'


@pytest.fixture
def root(tmp_path, monkeypatch):
    """An empty checkout; the name ends in "obs" because scriptgen takes the
    brand from the cwd."""
    root = tmp_path / "repo-obs"
    (root / "xml" / "obs").mkdir(parents=True)
    (root / "t" / "obs").mkdir(parents=True)
    monkeypatch.chdir(root)
    for name in list(os.environ):
        if name.startswith("GIT_"):
            monkeypatch.delenv(name)
    return root


def write_xml(root, name, pattern, body=FLAVOR, attrs=""):
    pattern = pattern.replace("<", "&lt;").replace(">", "&gt;")
    path = root / "xml" / "obs" / name
    path.write_text(
        f'<openQA project_pattern="{pattern}"{attrs}>\n    {body}\n</openQA>\n'
    )
    return path


def errors(dirs=("xml/obs",)):
    return validate_xml.validate(dirs).errors


# literal project names


@pytest.mark.parametrize(
    "pattern, expected",
    [
        ("KDE:Medias", "KDE:Medias"),
        (
            "devel:ARM:(?P<version>Factory):ARMv9:ToTest",
            "devel:ARM:Factory:ARMv9:ToTest",
        ),
        (
            "openSUSE:(?P<version>Factory):LegacyARM:ToTest",
            "openSUSE:Factory:LegacyARM:ToTest",
        ),
        ("openSUSE:(?P<version>Factory):ToTest", "openSUSE:Factory:ToTest"),
        (
            "openSUSE:Leap:(?P<version>15.6):Images:ToTest",
            "openSUSE:Leap:15.6:Images:ToTest",
        ),
        ("openSUSE:Leap:(?P<version>16.0):ToTest", "openSUSE:Leap:16.0:ToTest"),
        ("openSUSE:Slowroll:Build:iso", "openSUSE:Slowroll:Build:iso"),
        ("SUSE:ALP:Products:Micro:0.1", "SUSE:ALP:Products:Micro:0.1"),
        ("systemsmanagement:Agama:Devel", "systemsmanagement:Agama:Devel"),
        ("Test(?P<version>OnlyIsosPost)", "TestOnlyIsosPost"),
        (r"Foo:1\.2:(?:Bar)", "Foo:1.2:Bar"),
        # a bare "." is a wildcard unless it is between two digits
        ("openSUSE:(?P<version>Slowroll:Build:.)", None),
        ("openSUSE:Leap:(?P<version>15.[3-9]):ToTest", None),
        ("openSUSE:Leap:Micro:(?P<version>6.[0-9]):ToTest", None),
        ("openSUSE:(?P<version>Factory):(Staging:[A-Z]|Rings:1-MinimalX)", None),
        ("OBS:Server:(?P<version>[2-9].[0-9]:Staging|Unstable)", None),
        (
            "openSUSE:Leap:(?P<version>15(?P<sp>.[0-9]+)?):(Staging:[A-Z]|Rings:1-MinimalX)",
            None,
        ),
        ("TestIsoHdd-(?P<version>[0-9]+)", None),
        (r"Foo:\d", None),
        ("Foo:(?P<v>Bar)?", None),
        ("", None),
    ],
)
def test_literal_project(pattern, expected):
    assert validate_xml.literal_project(pattern) == expected


STAGING = "openSUSE:(?P<version>Factory):(Staging:[A-Z]|Rings:1-MinimalX)"


@pytest.mark.parametrize(
    "pattern, expected",
    [
        ("A:[A-C]", ["A:A", "A:B", "A:C"]),
        ("A:(B|C:[1-2])", ["A:B", "A:C:1", "A:C:2"]),
        (r"A:[x\-]", ["A:-", "A:x"]),
        ("A:(?P<v>B)?", ["A:", "A:B"]),
        ("A:B{2}", ["A:BB"]),
        ("A:[0-1]{1,2}", ["A:0", "A:00", "A:01", "A:1", "A:10", "A:11"]),
        (r"A:1\.2", ["A:1.2"]),
        ("A:[A-Z][A-Z]", None),
        ("A:[^B]", None),
        ("A:B+", None),
        ("A:B{2,}", None),
        ("A:.", None),
        (r"A:\d", None),
        ("A:(?=B)B", None),
        ("^A$", None),
        ("A:(", None),
    ],
)
def test_expand_pattern(pattern, expected):
    assert validate_xml.expand_pattern(pattern) == expected


def enabled(pattern, *elements):
    body = "".join(f"<projects_enabled {e}/>" for e in elements)
    root = ElementTree.fromstring(f"<openQA>{body}</openQA>")
    return validate_xml.enabled_names(root, pattern)


@pytest.mark.parametrize(
    "pattern, slots",
    [
        ("A:B", []),
        ("A:[A-Z]", ["[A-Z]"]),
        ("A:(?P<v>[0-9]+):B", ["[0-9]+"]),
        (r"A:\[x\]:[]a]{1,2}", ["[]a]{1,2}"]),
        (r"A:[\]x]", [r"[\]x]"]),
        ("A:[0-9]+:[A-Z]", ["[0-9]+", "[A-Z]"]),
    ],
)
def test_find_slots(pattern, slots):
    assert [pattern[a:b] for a, b in validate_xml.find_slots(pattern)] == slots


def test_enabled_names():
    assert enabled(STAGING) == (None, [])
    names, errs = enabled(STAGING, 'range="A..O" project="Z,Y,A"')
    assert errs == []
    letters = [chr(c) for c in range(ord("A"), ord("P"))] + ["Y", "Z"]
    assert names == ["openSUSE:Factory:Rings:1-MinimalX"] + [
        f"openSUSE:Factory:Staging:{c}" for c in letters
    ]
    assert enabled("T(?P<version>[0-9]+)", 'range="1..3" project="1025,2"') == (
        ["T1", "T1025", "T2", "T3"],
        [],
    )
    assert enabled("L:(?P<version>15.[3-9]):T", 'range="5..6"') == (
        ["L:15.5:T", "L:15.6:T"],
        [],
    )
    assert enabled("A:[A-Z]", 'project="B"', 'range="A..B"') == (["A:A", "A:B"], [])


def test_enabled_literal_project():
    names = ["openSUSE:Factory:Rings:1-MinimalX", "openSUSE:Factory:Staging:A"]
    assert enabled(STAGING, 'project="Rings:1-MinimalX,A"') == (names, [])
    assert enabled(STAGING, 'project="Rings:1-MinimalX"') == (names[:1], [])
    _, errs = enabled(STAGING, 'project="Rings:2"')
    assert "project 'Rings:2' is not of the same class" in errs[0]


@pytest.mark.parametrize(
    "pattern, element, message",
    [
        ("A:[A-Z]", 'range="A...O"', "invalid range 'A...O'"),
        ("A:[A-Z]", 'range="A-O"', "invalid range 'A-O'"),
        ("A:[A-Z]", 'range="O..A"', "the start is after the end"),
        ("A:[A-Z]", 'range="A..9"', "single letters or both numbers"),
        ("A:[A-Z]", 'range="AA..AC"', "single letters or both numbers"),
        ("A:[A-Za-z]", 'range="a..C"', "same case"),
        ("A:[0-9]+", 'range="0..9999"', "more than 256 values"),
        ("A:[A-Z]", 'range="A..C" project="99"', "'99' is not of the same class"),
        ("A:[A-Z]", 'project="A,9"', "'9' is not of the same class"),
        ("A:[A-Z]", 'project="A-1"', "'A-1' is not of the same class"),
        ("A:[A-Z]", 'range="1..3"', "'1' does not match '[A-Z]'"),
        ("A:[1-9]", 'project="512"', "'512' does not match '[1-9]'"),
        ("A:[0-9]+", 'project="MyProject"', "'MyProject' does not match"),
        ("A:B", 'range="1..2"', "exactly one character class in 'A:B', found 0"),
        ("A:[0-9]+:[A-Z]", 'range="1..2"', "found 2"),
        ("A.B:[A-Z]", 'range="A..B"', "outside the character class must be literal"),
    ],
)
def test_enabled_names_errors(pattern, element, message):
    _, errs = enabled(pattern, element)
    assert any(message in e for e in errs), errs


def test_range_limit(monkeypatch):
    monkeypatch.setattr(validate_xml, "MAX_ENABLED", 9)
    _, errs = enabled("A:[0-9]+", 'range="0..9"')
    assert errs == ["invalid range '0..9': more than 9 values"], errs
    assert enabled("A:[0-9]+", 'range="1..9"')[1] == []


def test_current_staging_projects(monkeypatch):
    monkeypatch.chdir(REPO)
    result = validate_xml.validate(["xml/obs"])
    names = result.enabled["xml/obs/openSUSE:Factory:Staging.xml"]
    assert len(names) == 16
    assert "openSUSE:Factory:Rings:1-MinimalX" in names
    assert "openSUSE:Factory:Staging:P" not in names
    for name in names:
        xmlfile, _, _ = scriptgen.find_xml(name, "obs")
        assert os.path.normpath(xmlfile) == "xml/obs/openSUSE:Factory:Staging.xml"


@pytest.mark.parametrize("brand", ["obs", "abs"])
def test_project_names_map_to_their_xml(monkeypatch, brand):
    """Covers XMLs without a t/<brand> dir, which test_regen_all skips."""
    monkeypatch.chdir(REPO)
    result = validate_xml.validate([f"xml/{brand}"])
    test_dirs = validate_xml.tracked_test_dirs(brand)
    for xml, regex in result.patterns.items():
        names = result.enabled.get(xml) or validate_xml.project_names(
            regex.pattern, test_dirs
        )
        for name in names:
            xmlfile, _, _ = scriptgen.find_xml(name, brand)
            assert os.path.normpath(xmlfile) == xml, name


def test_project_names_falls_back_to_test_dirs():
    pattern = "Multi:(?P<version>[A-Z])"
    assert validate_xml.project_names(
        pattern, ["Multi:B", "Multi:A", "Multi:10", "Other:A"]
    ) == ["Multi:A", "Multi:B"]
    assert validate_xml.project_names("Lit:(?P<version>Eral)", ["Multi:A"]) == [
        "Lit:Eral"
    ]
    assert validate_xml.project_names(pattern, []) == []


# validate()


def test_current_repository_is_valid(monkeypatch):
    monkeypatch.chdir(REPO)
    result = validate_xml.validate()
    assert result.errors == []
    assert "xml/obs/openSUSE:Factory:LegacyARM.xml" in result.patterns


def test_valid_xmls(root):
    write_xml(
        root, "A.xml", "A:(?P<version>B)", '<batch name="one">' + FLAVOR + "</batch>"
    )
    write_xml(root, "Multi.xml", "Multi:(?P<version>[A-Z])")
    (root / "t" / "obs" / "Multi:A").mkdir()
    (root / "t" / "obs" / "A:B").mkdir()
    result = validate_xml.validate(["xml/obs"])
    assert result.errors == []
    assert result.warnings == []
    assert sorted(result.patterns) == ["xml/obs/A.xml", "xml/obs/Multi.xml"]


def test_literal_xml_without_test_dir_is_a_warning(root):
    write_xml(root, "A.xml", "A:B")
    result = validate_xml.validate(["xml/obs"])
    assert result.errors == []
    assert result.warnings == [
        "xml/obs/A.xml: no t/obs/<Project> test dir matches 'A:B'"
    ]


def test_missing_dirs_are_skipped(root):
    (root / "xml" / "ibs").symlink_to(root / "missing")
    result = validate_xml.validate(["xml/obs", "xml/ibs", "xml/abs"])
    assert result.errors == []
    assert len(result.notes) == 2
    assert validate_xml.main(["xml/ibs"]) == 0


@pytest.mark.parametrize(
    "content, message",
    [
        ("<openQA", "cannot parse"),
        ('<openQA project_pattern="A:(B"/>', "invalid project_pattern"),
    ],
)
def test_broken_xml(root, content, message):
    (root / "xml" / "obs" / "A.xml").write_text(content)
    (found,) = errors()
    assert found.startswith("xml/obs/A.xml: " + message)
    assert validate_xml.main(["xml/obs"]) == 1


# the other batch name checks are in the schema, see test_xml_schema.py
def test_duplicate_batches(root):
    write_xml(root, "A.xml", "A:B", '<batch name="a"/><batch name="a"/>')
    assert errors() == ["xml/obs/A.xml: duplicate batch name 'a'"]
    write_xml(root, "A.xml", "A:B", attrs=' batches="a|b|a"')
    assert errors() == ["xml/obs/A.xml: duplicate batch name 'a'"]


def test_scriptgen_failure(root):
    write_xml(root, "A.xml", "A:B", '<batch name="a"><flavor iso1="x"/></batch>')
    (found,) = errors()
    assert found.startswith("xml/obs/A.xml: scriptgen cannot process it: KeyError")


def test_batch_references(root):
    body = f'<batch name="a" repos="b">{FLAVOR}</batch><batch name="b">{FLAVOR}</batch>'
    write_xml(root, "A.xml", "A:B", body)
    assert errors() == []
    # a path is an external repository, not a batch
    write_xml(root, "A.xml", "A:B", attrs=' repos="Other:Project/repo"')
    assert errors() == []
    write_xml(root, "A.xml", "A:B", attrs=' repos="missing"')
    assert errors() == [
        "xml/obs/A.xml: batch 'default': repos='missing' is not a batch"
    ]


def test_regex_xml_without_project_name_is_an_error(root):
    write_xml(root, "A.xml", "A:[0-9]")
    (found,) = errors()
    assert found.startswith("xml/obs/A.xml: cannot derive a project name")
    (root / "t" / "obs" / "A:1").mkdir()
    assert errors() == []


def test_grandfathered_xml(root):
    write_xml(
        root, "openSUSE:Leap:15.xml", "openSUSE:Leap:(?P<version>15.[3-9]):ToTest"
    )
    assert errors() == []


def test_project_name_needs_a_colon(root):
    write_xml(root, "A.xml", "AB")
    assert errors() == [
        "xml/obs/A.xml: project name 'AB' is not a valid project dir name"
    ]


def test_test_dir_matching_two_xmls(root):
    write_xml(root, "A.xml", "A:[0-9]")
    write_xml(root, "B.xml", "A:1|B:1")
    (root / "t" / "obs" / "A:1").mkdir()
    assert errors() == [
        "A:1: matched by more than one XML: xml/obs/A.xml, xml/obs/B.xml"
    ]


def test_literal_name_shadowed_by_other_xml(root):
    write_xml(root, "A.xml", "A:[A-Z]")
    write_xml(root, "B.xml", "A:(?P<version>B)")
    (root / "t" / "obs" / "A:C").mkdir()
    assert errors() == [
        "A:B: matched by more than one XML: xml/obs/A.xml, xml/obs/B.xml"
    ]


def test_projects_enabled(root):
    body = '<projects_enabled range="A..B" project="D"/>' + FLAVOR
    write_xml(root, "S.xml", "S:(?P<version>F):[A-Z]", body)
    (root / "t" / "obs" / "S:F:A").mkdir()
    (root / "t" / "obs" / "S:F:C").mkdir()
    result = validate_xml.validate(["xml/obs"])
    assert result.errors == []
    assert result.enabled == {"xml/obs/S.xml": ["S:F:A", "S:F:B", "S:F:D"]}
    assert result.warnings == [
        "xml/obs/S.xml: test dir t/obs/S:F:C is not in <projects_enabled>"
    ]


def test_projects_enabled_errors(root):
    body = '<projects_enabled range="A..C" project="99"/>' + FLAVOR
    write_xml(root, "S.xml", "S:[A-Z]", body)
    assert errors() == [
        (
            "xml/obs/S.xml: project '99' is not of the same class as the other "
            "values (letters or a number)"
        )
    ]


def test_enabled_name_matching_two_xmls(root):
    write_xml(root, "S.xml", "S:[A-Z]", '<projects_enabled range="A..C"/>' + FLAVOR)
    write_xml(root, "B.xml", "S:B")
    assert errors() == [
        "S:B: matched by more than one XML: xml/obs/B.xml, xml/obs/S.xml"
    ]


def test_tracked_test_dirs_prefers_git(root):
    (root / "t" / "obs" / "A:1").mkdir()
    (root / "t" / "obs" / "A:1" / "f").write_text("")
    (root / "t" / "obs" / "A:2").mkdir()
    assert validate_xml.tracked_test_dirs("obs") == ["A:1", "A:2"]
    subprocess.run(["git", "init", "-q"], check=True)
    subprocess.run(["git", "add", "t/obs/A:1/f"], check=True)
    assert validate_xml.tracked_test_dirs("obs") == ["A:1"]


# helpers factored out of scriptgen.py


@pytest.mark.parametrize(
    "content, customized",
    [
        (None, False),
        ("", False),
        ("#!/bin/bash\n", False),
        ("# GENERATED FILE - DO NOT EDIT\nset -e\n", False),
        ("#!/bin/bash\n# GENERATED FILE - DO NOT EDIT\n", False),
        ("#!/bin/bash\necho custom\n", True),
        ("echo custom\n", True),
    ],
)
def test_is_customized(tmp_path, content, customized):
    path = tmp_path / "read_files.sh"
    if content is not None:
        path.write_text(content)
    assert scriptgen.is_customized(str(path)) is customized


def test_find_xml_and_batch_subfolders(root):
    write_xml(
        root,
        "A.xml",
        "A:(?P<version>B)",
        '<batch name="one">' + FLAVOR + '</batch><batch name="two"/>',
    )
    write_xml(root, "C.xml", "C:D", attrs=' batches="x|y"')
    write_xml(root, "E.xml", "E:F")
    assert scriptgen.find_xml("A:B", "obs") == ("xml/obs/A.xml", "", "B")
    assert scriptgen.find_xml("A:C", "obs") == ("", "", "")
    assert scriptgen.batch_subfolders(scriptgen.load_generator("A:B")) == {"one", "two"}
    assert scriptgen.batch_subfolders(scriptgen.load_generator("C:D")) == {"x", "y"}
    assert scriptgen.batch_subfolders(scriptgen.load_generator("E:F")) == set()
    assert scriptgen.load_generator("X:Y") is None


# rsync.lock handling


def test_rsync_lock(root):
    project = root / "A:B"
    project.mkdir()
    lock = project / "rsync.lock"
    assert not deploy_common.rsync_lock_live("A:B")

    lock.write_text("garbage\n")
    assert not deploy_common.rsync_lock_live("A:B")

    dead = subprocess.Popen(["true"])
    dead.wait()
    lock.write_text(f"{dead.pid}\n")
    assert not deploy_common.rsync_lock_live("A:B")

    # pid 1 is alive; as non-root kill() fails with EPERM, still alive
    lock.write_text("1\n")
    assert deploy_common.rsync_lock_live("A:B")
    assert not deploy_common.take_rsync_lock("A:B")
    deploy_common.release_rsync_lock("A:B")
    assert lock.read_text() == "1\n"

    lock.unlink()
    assert deploy_common.take_rsync_lock("A:B")
    assert lock.read_text() == f"{os.getpid()}\n"
    deploy_common.release_rsync_lock("A:B")
    assert not lock.exists()

    # a lock taken over by someone else is not released
    assert deploy_common.take_rsync_lock("A:B")
    lock.write_text("1\n")
    deploy_common.release_rsync_lock("A:B")
    assert lock.exists()


def test_state(root):
    assert deploy_common.read_state("deploy") is None
    deploy_common.write_state("deploy", {"sha": "abc", "pending": ["A:B"]})
    assert deploy_common.read_state("deploy") == {"sha": "abc", "pending": ["A:B"]}
    (root / ".deploy-state" / "deploy.json").write_text("{corrupt")
    assert deploy_common.read_state("deploy") is None
    (root / ".deploy-state" / "deploy.json").write_text('{"sha": ""}')
    assert deploy_common.read_state("deploy") is None
