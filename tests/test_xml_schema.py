import shutil
import subprocess
from pathlib import Path

import pytest

# TODO: This testsuite could be removed or only ran if a change in the schema happens, as it takes a long time to run and is not necessary for every test run.

REPO = Path(__file__).resolve().parent.parent
SCHEMA = REPO / "xml" / "openQA.rng"

pytestmark = pytest.mark.skipif(
    not shutil.which("xmllint"), reason="xmllint (libxml2-tools) is not installed"
)

FLAVOR = '<flavor name="FLAVOR" distri="distri" iso="iso"/>'


def xmllint(*paths):
    return subprocess.run(
        ["xmllint", "--noout", "--quiet", "--relaxng", str(SCHEMA), *map(str, paths)],
        capture_output=True,
        text=True,
        check=False,
    )


def check(tmp_path, content):
    path = tmp_path / "A.xml"
    path.write_text(content)
    return xmllint(path)


def test_repository_xmls_are_valid():
    paths = sorted(REPO.glob("xml/obs/*.xml")) + sorted(REPO.glob("xml/abs/*.xml"))
    assert paths
    result = xmllint(*paths)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "content",
    [
        f'<openQA project_pattern="A:B">{FLAVOR}</openQA>',
        '<openQA project_pattern="A:B" batches="one|two" rsynctimeout="60"/>',
        (
            '<openQA project_pattern="A:B"><batch name="one" sha="512" rsynctimeout="9">'
            f'{FLAVOR}<news iso="x"/></batch><batch name="1.0"/></openQA>'
        ),
        (
            '<openQA project_pattern="A:B"><flavor name="F" sha="256">'
            '<repos archs="x86_64"><oss folder="f" mirror="1"/><my-repo debug="1"/></repos>'
            '<assets folder="d"><libvirt filemask="m"/></assets>'
            '<iso filemask="i"/><hdd filemask="h" folder="f"/><asset filemask="a"/>'
            '<alias name="n" alias="a"/><renames><x to="y"/></renames>'
            "</flavor></openQA>"
        ),
        (
            '<openQA project_pattern="A:[A-Z]"><projects_enabled range="A..O" project="Z"/>'
            '<projects_enabled project="Y,X"/><projects_enabled range="P..Q"/></openQA>'
        ),
    ],
)
def test_valid(tmp_path, content):
    result = check(tmp_path, content)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "content, message",
    [
        ("<openQA", "Couldn't find end of Start Tag"),
        ('<other project_pattern="A:B"/>', "Expecting element openQA, got other"),
        ("<openQA/>", "Element openQA failed to validate attributes"),
        (
            '<openQA project_pattern=""/>',
            "Element openQA failed to validate attributes",
        ),
        ('<openQA project_pattern="A:B" archz="x"/>', "Invalid attribute archz"),
        # batches
        ('<openQA project_pattern="A:B"><batch/></openQA>', "batch failed to validate"),
        ('<openQA project_pattern="A:B"><batch name="a/b"/></openQA>', "batch failed"),
        ('<openQA project_pattern="A:B"><batch name=".h"/></openQA>', "batch failed"),
        ('<openQA project_pattern="A:B"><batch name="default"/></openQA>', "batch fai"),
        ('<openQA project_pattern="A:B" batches="a|../x"/>', "attribute batches"),
        ('<openQA project_pattern="A:B" batches="a||b"/>', "attribute batches"),
        # flavors and their children
        ('<openQA project_pattern="A:B"><flavor sha="128"/></openQA>', "attribute sha"),
        ('<openQA project_pattern="A:B"><flavor iso_path="x"/></openQA>', "iso_path"),
        # scriptgen.py only reads repos of <batch>, not of <flavor>
        ('<openQA project_pattern="A:B"><flavor repos="x"/></openQA>', "repos"),
        ('<openQA project_pattern="A:B"><flavor><hdd/></flavor></openQA>', "hdd"),
        (
            '<openQA project_pattern="A:B"><flavor><iso filemask=""/></flavor></openQA>',
            "iso",
        ),
        (
            (
                '<openQA project_pattern="A:B"><flavor><repos><oss foldr="x"/></repos>'
                "</flavor></openQA>"
            ),
            "Invalid attribute foldr for element oss",
        ),
        (
            (
                '<openQA project_pattern="A:B"><flavor><assets><libvirt/></assets>'
                "</flavor></openQA>"
            ),
            "libvirt",
        ),
        ('<openQA project_pattern="A:B"><news/><other/></openQA>', "other"),
        # projects_enabled
        (
            '<openQA project_pattern="A:[A-Z]"><projects_enabled/></openQA>',
            "projects_e",
        ),
        (
            '<openQA project_pattern="A:[A-Z]"><projects_enabled range="A...O"/></openQA>',
            "projects_enabled",
        ),
        (
            '<openQA project_pattern="A:[A-Z]"><projects_enabled range="A-O"/></openQA>',
            "projects_enabled",
        ),
        (
            '<openQA project_pattern="A:[A-Z]"><projects_enabled project="A,,B"/></openQA>',
            "projects_enabled",
        ),
        (
            '<openQA project_pattern="A:[A-Z]"><projects_enabled rang="A..B"/></openQA>',
            "projects_enabled",
        ),
    ],
)
def test_invalid(tmp_path, content, message):
    result = check(tmp_path, content)
    assert result.returncode != 0
    assert message in result.stderr


def test_make_validate_xml(tmp_path):
    xmls = tmp_path / "obs"
    xmls.mkdir()
    (xmls / "A.xml").write_text(f'<openQA project_pattern="A:B">{FLAVOR}</openQA>')
    make = ["make", "-s", "-C", str(REPO), "validate_xml", f"XML_DIRS={xmls}"]
    result = subprocess.run(make, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr

    (xmls / "A.xml").write_text(
        f'<openQA project_pattern="A:B" sha="1">{FLAVOR}</openQA>'
    )
    result = subprocess.run(make, capture_output=True, text=True, check=False)
    assert result.returncode != 0
    assert "Invalid attribute sha for element openQA" in result.stderr
