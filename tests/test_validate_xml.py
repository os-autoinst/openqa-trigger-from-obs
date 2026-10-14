import os
import subprocess
from pathlib import Path

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
        ('<other project_pattern="A:B"/>', "root element is <other>"),
        ("<openQA/>", "missing project_pattern"),
        ('<openQA project_pattern="A:(B"/>', "invalid project_pattern"),
    ],
)
def test_broken_xml(root, content, message):
    (root / "xml" / "obs" / "A.xml").write_text(content)
    (found,) = errors()
    assert found.startswith("xml/obs/A.xml: " + message)
    assert validate_xml.main(["xml/obs"]) == 1


@pytest.mark.parametrize(
    "batches, message",
    [
        ('<batch archs="x86_64"/>', "<batch> without name attribute"),
        ('<batch name="a"/><batch name="a"/>', "duplicate batch name 'a'"),
        ('<batch name="a/b"/>', "invalid batch name 'a/b'"),
        ('<batch name=".hidden"/>', "invalid batch name '.hidden'"),
        ('<batch name="default"/>', "invalid batch name 'default'"),
    ],
)
def test_bad_batches(root, batches, message):
    write_xml(root, "A.xml", "A:B", batches)
    assert errors() == ["xml/obs/A.xml: " + message]


def test_bad_batches_attribute(root):
    write_xml(root, "A.xml", "A:B", attrs=' batches="a|a|../x"')
    assert errors() == [
        "xml/obs/A.xml: invalid batch name '../x' in batches attribute",
        "xml/obs/A.xml: duplicate batch name 'a'",
    ]


def test_scriptgen_failure(root):
    write_xml(root, "A.xml", "A:B", '<batch name="a"><flavor iso1="x"/></batch>')
    (found,) = errors()
    assert found.startswith("xml/obs/A.xml: scriptgen cannot process it: KeyError")


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
