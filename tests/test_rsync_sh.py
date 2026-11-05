"""Tests for script/rsync.sh, run against a scratch project directory with
stubbed generated scripts."""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PROJECT = "openSUSE:Factory:Staging:A"
ISO = "openSUSE-Tumbleweed-DVD-x86_64-Snapshot20200209-Media.iso"


@pytest.fixture
def root(tmp_path):
    # rsync.sh changes into the parent of its own directory, so give it a
    # scratch copy to keep the repository clean
    (tmp_path / "script").mkdir()
    shutil.copy(REPO / "script" / "rsync.sh", tmp_path / "script")
    (tmp_path / PROJECT).mkdir()
    return tmp_path


def add_subfolder(root, name, lst="files_repo.lst", **scripts):
    subfolder = root / PROJECT / name
    subfolder.mkdir()
    (subfolder / lst).write_text("1\n")
    defaults = {
        "read_files.sh": "",
        "print_rsync_iso.sh": "echo true",
        "print_rsync_repo.sh": "echo true",
        "print_openqa.sh": "echo true",
    }
    for script, content in {**defaults, **scripts}.items():
        (subfolder / script).write_text(content + "\n")
    return subfolder


def rsync(root):
    return subprocess.run(
        ["bash", str(root / "script" / "rsync.sh"), PROJECT],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_all_subfolders_are_synced(root):
    first = add_subfolder(root, "a")
    second = add_subfolder(root, "b")
    proc = rsync(root)
    assert proc.returncode == 0, proc.stderr
    assert (first / ".run_last" / "openqa.cmd.log").is_file()
    assert (second / ".run_last" / "openqa.cmd.log").is_file()
    assert not (root / PROJECT / "rsync.lock").exists()


@pytest.mark.parametrize(
    "script",
    ["print_rsync_iso.sh", "print_rsync_repo.sh", "print_openqa.sh"],
)
def test_failing_subfolder_does_not_stop_the_others(root, script):
    failing = add_subfolder(root, "a", **{script: "exit 1"})
    second = add_subfolder(root, "b")
    proc = rsync(root)
    assert proc.returncode == 1
    assert f"{PROJECT}/a/ exit code: 1 (1 failures total so far)" in proc.stderr
    # a failed step must not mark the subfolder as done, so it is retried
    assert not (failing / ".run_last").exists()
    assert (second / ".run_last" / "openqa.cmd.log").is_file()
    assert not (root / PROJECT / "rsync.lock").exists()


def test_failures_are_counted_across_subfolders(root):
    add_subfolder(root, "a", **{"print_openqa.sh": "exit 1"})
    add_subfolder(root, "b", **{"print_openqa.sh": "exit 1"})
    proc = rsync(root)
    assert proc.returncode == 2
    assert "(2 failures total so far)" in proc.stderr


def test_version_is_not_reused_by_next_subfolder(root):
    first = add_subfolder(root, "a", lst="files_iso.lst")
    (first / "files_iso.lst").write_text(ISO + "\n")
    second = add_subfolder(root, "b")
    proc = rsync(root)
    assert proc.returncode == 0, proc.stderr
    assert (first / ".run_last").resolve().name.endswith("_20200209")
    assert "20200209" not in (second / ".run_last").resolve().name


def test_lock_is_removed_on_sigterm_after_first_subfolder(root):
    first = add_subfolder(root, "a")
    # deliver SIGTERM to rsync.sh while it processes the second subfolder
    second = add_subfolder(root, "b", **{"read_files.sh": "kill -TERM $PPID"})
    rsync(root)
    assert (first / ".run_last").exists()
    assert not (second / ".run_last").exists()
    assert not (root / PROJECT / "rsync.lock").exists()
