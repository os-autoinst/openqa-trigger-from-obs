"""Integration tests for deploy_on_pull.py, cleanup_on_deploy.py and
deploy-hook.sh, run against a scratch git repository."""

import fcntl
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = (
    "scriptgen.py",
    "cfg.py",
    "validate_xml.py",
    "deploy_common.py",
    "deploy_on_pull.py",
    "cleanup_on_deploy.py",
    "deploy-hook.sh",
)
FLAVOR = '<flavor name="FLAVOR" distri="DISTRI" iso="iso"/>'
BATCHED = f'<batch name="one">{FLAVOR}</batch>\n<batch name="two">{FLAVOR}</batch>'


def git_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_CONFIG_GLOBAL="/dev/null",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="test",
        GIT_COMMITTER_EMAIL="test@example.com",
    )
    return env


class Output:
    def __init__(self, proc):
        self.returncode = proc.returncode
        self.stdout = proc.stdout
        self.out = proc.stdout + proc.stderr


class Repo:
    def __init__(self, root):
        self.root = root

    def path(self, *parts):
        return self.root.joinpath(*parts)

    def git(self, *args, **kwargs):
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True,
            capture_output=True,
            text=True,
            env=git_env(),
            **kwargs,
        ).stdout

    def commit(self, msg="change"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)
        return self.git("rev-parse", "HEAD").strip()

    def xml(self, name, pattern, body=FLAVOR, attrs=""):
        pattern = pattern.replace("<", "&lt;").replace(">", "&gt;")
        self.path("xml", "obs", name).write_text(
            f'<openQA project_pattern="{pattern}"{attrs}>\n{body}\n</openQA>\n'
        )

    def run(self, script, *args):
        proc = subprocess.run(
            [sys.executable, str(self.path("script", script)), *args],
            capture_output=True,
            text=True,
            env=git_env(),
            cwd="/",
            check=False,
        )
        return Output(proc)

    def deploy(self, *args):
        return self.run("deploy_on_pull.py", *args)

    def cleanup(self, *args):
        return self.run("cleanup_on_deploy.py", *args)

    def hook(self, *args, env=None, cwd=None):
        proc = subprocess.run(
            [str(self.path("script", "deploy-hook.sh")), *args],
            capture_output=True,
            text=True,
            env=env or git_env(),
            cwd=cwd or self.root,
            check=False,
        )
        return Output(proc)

    def state(self, name):
        path = self.path(".deploy-state", name + ".json")
        return json.loads(path.read_text()) if path.exists() else None

    def head(self):
        return self.git("rev-parse", "HEAD").strip()

    def generated(self, *parts):
        path = self.path(*parts, "print_openqa.sh")
        return path.exists() and "GENERATED" in path.read_text().splitlines()[0]


def make_repo(root):
    (root / "script").mkdir(parents=True)
    for name in SCRIPTS:
        shutil.copy2(REPO / "script" / name, root / "script" / name)
    shutil.copy2(REPO / ".gitignore", root / ".gitignore")
    shutil.copy2(REPO / "Makefile", root / "Makefile")
    (root / "xml" / "obs").mkdir(parents=True)
    (root / "t" / "obs" / "Multi:A").mkdir(parents=True)
    (root / "t" / "obs" / "Multi:A" / "files_iso.lst").write_text("")
    repo = Repo(root)
    repo.xml("Foo:Bar.xml", "Foo:(?P<version>Bar):ToTest", BATCHED)
    repo.xml("Baz.xml", "Baz:Qux")
    repo.xml("Multi.xml", "Multi:(?P<version>[A-Z])")
    repo.git("init", "-q", "-b", "master")
    repo.commit("initial")
    return repo


@pytest.fixture
def repo(tmp_path):
    """A deployed checkout with state, like after the first-time setup."""
    repo = make_repo(tmp_path / "repo-obs")
    for project in ("Foo:Bar:ToTest", "Baz:Qux", "Multi:A"):
        repo.path(project).mkdir()
        subprocess.run(
            [sys.executable, "script/scriptgen.py", project],
            cwd=repo.root,
            check=True,
            capture_output=True,
        )
    assert repo.deploy().returncode == 0
    assert repo.cleanup().returncode == 0
    return repo


def generating(proc):
    return sorted(
        line.split(": ")[1]
        for line in proc.stdout.splitlines()
        if line.endswith(": generating")
    )


# deploy_on_pull.py


def test_first_run_regenerates_all_and_stores_state(repo):
    assert repo.state("deploy") == {"sha": repo.head(), "pending": []}
    assert repo.state("cleanup")["sha"] == repo.head()
    assert repo.generated("Foo:Bar:ToTest", "one")
    assert repo.generated("Baz:Qux")
    proc = repo.deploy()
    assert proc.returncode == 0
    assert generating(proc) == []
    assert "nothing to generate" in proc.out


def test_modified_xml_regenerates_only_its_projects(repo):
    repo.xml("Baz.xml", "Baz:Qux", FLAVOR.replace("DISTRI", "NEWDISTRI"))
    repo.commit()
    proc = repo.deploy()
    assert proc.returncode == 0, proc.out
    assert generating(proc) == ["Baz:Qux"]
    assert "NEWDISTRI" in repo.path("Baz:Qux", "print_openqa.sh").read_text()
    assert repo.state("deploy")["sha"] == repo.head()


def test_generator_change_regenerates_all(repo):
    with open(repo.path("script", "cfg.py"), "a") as f:
        f.write("\n# change\n")
    repo.commit()
    proc = repo.deploy()
    assert generating(proc) == ["Baz:Qux", "Foo:Bar:ToTest", "Multi:A"]


def test_pattern_moved_to_other_xml(repo):
    repo.xml("Baz.xml", "Baz:Other")
    repo.xml(
        "Multi.xml",
        "(?P<version>Multi:[A-Z]|Baz:Qux)",
        FLAVOR.replace("DISTRI", "MOVED"),
    )
    repo.commit()
    proc = repo.deploy()
    assert "Baz:Qux" in generating(proc)
    assert "MOVED" in repo.path("Baz:Qux", "print_openqa.sh").read_text()


def test_failure_is_retried(repo):
    shutil.rmtree(repo.path("Foo:Bar:ToTest", "one"))
    repo.path("Foo:Bar:ToTest", "one").write_text("in the way")
    repo.xml(
        "Foo:Bar.xml",
        "Foo:(?P<version>Bar):ToTest",
        BATCHED.replace("DISTRI", "RETRIED"),
    )
    sha = repo.commit()
    proc = repo.deploy()
    assert proc.returncode == 1
    assert "Foo:Bar:ToTest: scriptgen failed, will retry" in proc.out
    assert repo.state("deploy") == {"sha": sha, "pending": ["Foo:Bar:ToTest"]}

    repo.path("Foo:Bar:ToTest", "one").unlink()
    proc = repo.deploy()
    assert proc.returncode == 0, proc.out
    assert generating(proc) == ["Foo:Bar:ToTest"]
    assert repo.state("deploy") == {"sha": sha, "pending": []}
    assert (
        "RETRIED" in repo.path("Foo:Bar:ToTest", "one", "print_openqa.sh").read_text()
    )


def test_new_literal_xml_creates_project(repo):
    repo.xml("New.xml", "New:(?P<version>Proj):ToTest", BATCHED)
    repo.commit()
    proc = repo.deploy()
    assert proc.returncode == 0, proc.out
    assert generating(proc) == ["New:Proj:ToTest"]
    assert "New:Proj:ToTest: creating project dir" in proc.out
    assert repo.generated("New:Proj:ToTest", "one")
    assert repo.generated("New:Proj:ToTest", "two")
    assert repo.deploy().returncode == 0
    assert generating(repo.deploy()) == []


def test_new_regex_xml_creates_projects_of_test_dirs(repo):
    repo.xml("Reg.xml", "Reg:(?P<version>[0-9])")
    for name in ("Reg:1", "Reg:2"):
        repo.path("t", "obs", name).mkdir()
        repo.path("t", "obs", name, "files_iso.lst").write_text("")
    repo.commit()
    proc = repo.deploy()
    assert proc.returncode == 0, proc.out
    assert generating(proc) == ["Reg:1", "Reg:2"]
    assert repo.generated("Reg:1")


STG = "Stg:(?P<version>Fac):(Staging:[A-Z]|Rings:1)"


def stg_xml(repo, *elements):
    body = "".join(f"<projects_enabled {e}/>" for e in elements)
    repo.xml("Stg.xml", STG, body + FLAVOR)


def test_new_xml_creates_enabled_projects(repo):
    stg_xml(repo, 'range="A..B" project="Z"')
    repo.commit()
    proc = repo.deploy()
    assert proc.returncode == 0, proc.out
    projects = ["Stg:Fac:Rings:1", "Stg:Fac:Staging:A", "Stg:Fac:Staging:B"]
    projects.append("Stg:Fac:Staging:Z")
    assert generating(proc) == projects
    assert all(repo.generated(p) for p in projects)
    assert not repo.path("Stg:Fac:Staging:C").exists()


def test_widened_range_creates_new_projects(repo):
    stg_xml(repo, 'range="A..B"')
    repo.commit()
    assert repo.deploy().returncode == 0
    repo.path("Stg:Fac:Staging:X").mkdir()
    stg_xml(repo, 'range="A..C"')
    repo.commit()
    proc = repo.deploy()
    assert proc.returncode == 0, proc.out
    assert "Stg:Fac:Staging:C: creating project dir" in proc.out
    assert "Stg:Fac:Staging:A: creating" not in proc.out
    # a dir that is not enabled is still regenerated, rsync.sh syncs it
    assert generating(proc) == [
        "Stg:Fac:Rings:1",
        "Stg:Fac:Staging:A",
        "Stg:Fac:Staging:B",
        "Stg:Fac:Staging:C",
        "Stg:Fac:Staging:X",
    ]


@pytest.mark.parametrize("args", [(), ("--all",)])
def test_missing_enabled_projects_are_created(repo, args):
    stg_xml(repo, 'range="A..B"')
    repo.commit()
    assert repo.deploy().returncode == 0
    shutil.rmtree(repo.path("Stg:Fac:Staging:A"))
    # an unchanged XML does not bring back a dir removed by hand
    assert generating(repo.deploy()) == []
    if not args:
        shutil.rmtree(repo.path(".deploy-state"))
    proc = repo.deploy(*args)
    assert proc.returncode == 0, proc.out
    assert "Stg:Fac:Staging:A: creating project dir" in proc.out
    assert repo.generated("Stg:Fac:Staging:A")


def test_deployed_xml_without_projects_enabled_creates_nothing(repo):
    repo.path("t", "obs", "Multi:B").mkdir()
    repo.path("t", "obs", "Multi:B", "files_iso.lst").write_text("")
    repo.xml("Multi.xml", "Multi:(?P<version>[A-Z])", FLAVOR.replace("DISTRI", "X"))
    repo.commit()
    proc = repo.deploy()
    assert proc.returncode == 0, proc.out
    assert generating(proc) == ["Multi:A"]
    assert not repo.path("Multi:B").exists()


def test_invalid_projects_enabled_blocks_deploy(repo):
    stg_xml(repo, 'range="A..C" project="99"')
    repo.commit()
    proc = repo.deploy()
    assert proc.returncode == 1
    assert "project '99' is not of the same class" in proc.out
    assert "nothing done" in proc.out


def test_new_xml_for_existing_dir_regenerates_it(repo):
    repo.git("rm", "-q", "xml/obs/Baz.xml")
    repo.xml("Renamed.xml", "Baz:Qux", FLAVOR.replace("DISTRI", "RENAMED"))
    repo.commit()
    proc = repo.deploy()
    assert proc.returncode == 0, proc.out
    assert generating(proc) == ["Baz:Qux"]
    assert "creating" not in proc.out
    assert "RENAMED" in repo.path("Baz:Qux", "print_openqa.sh").read_text()


def test_new_xml_without_project_name_is_rejected_until_fixed(repo):
    sha = repo.head()
    repo.xml("NoName.xml", "NoName:[0-9]")
    repo.commit()
    proc = repo.deploy()
    assert proc.returncode == 1
    assert "NoName.xml: cannot derive a project name" in proc.out
    assert repo.state("deploy")["sha"] == sha

    repo.path("t", "obs", "NoName:7").mkdir()
    repo.path("t", "obs", "NoName:7", "files_iso.lst").write_text("")
    repo.commit()
    proc = repo.deploy()
    assert proc.returncode == 0, proc.out
    assert generating(proc) == ["NoName:7"]


def test_new_xml_that_scriptgen_does_not_map_is_retried(repo):
    repo.xml("Bad.xml", "Bad:One", attrs=' dist_path="`id`"')
    sha = repo.commit()
    proc = repo.deploy()
    assert proc.returncode == 1
    assert "Bad:One would be generated from no XML" in proc.out
    assert not repo.path("Bad:One").exists()
    assert repo.state("deploy") == {"sha": sha, "pending": ["xml/obs/Bad.xml"]}

    repo.xml("Bad.xml", "Bad:One")
    repo.commit()
    proc = repo.deploy()
    assert proc.returncode == 0, proc.out
    assert generating(proc) == ["Bad:One"]
    assert repo.state("deploy")["pending"] == []


def test_unmapped_dir_is_skipped(repo):
    repo.path("Stray:Dir").mkdir()
    proc = repo.deploy("--all")
    assert "Stray:Dir" not in proc.out
    assert generating(proc) == ["Baz:Qux", "Foo:Bar:ToTest", "Multi:A"]


def test_pending_project_ending_in_xml(repo):
    repo.xml("Dot.xml", r"Dot:P\.xml")
    repo.commit()
    assert repo.deploy().returncode == 0
    state = repo.state("deploy")
    state["pending"] = ["Dot:P.xml"]
    repo.path(".deploy-state", "deploy.json").write_text(json.dumps(state))
    proc = repo.deploy()
    assert proc.returncode == 0, proc.out
    assert generating(proc) == ["Dot:P.xml"]
    assert "no longer exists" not in proc.out


def test_invalid_xml_does_nothing(repo):
    sha = repo.head()
    repo.path("xml", "obs", "Baz.xml").write_text("<openQA")
    repo.commit()
    for proc in (repo.deploy(), repo.cleanup()):
        assert proc.returncode == 1
        assert "xml/obs is invalid, nothing done" in proc.out
    assert repo.state("deploy")["sha"] == sha
    assert repo.state("cleanup")["sha"] == sha


def test_dry_run(repo):
    state = repo.state("deploy")
    repo.xml("New.xml", "New:Proj")
    repo.git("rm", "-q", "xml/obs/Baz.xml")
    repo.commit()
    proc = repo.deploy("--dry-run")
    assert "New:Proj: would create and generate" in proc.out
    assert not repo.path("New:Proj").exists()
    proc = repo.cleanup("--dry-run")
    assert "Baz:Qux: would remove" in proc.out
    assert repo.path("Baz:Qux").exists()
    assert repo.state("deploy") == state


def test_from(repo):
    sha = repo.head()
    repo.xml("New.xml", "New:Proj")
    repo.commit()
    shutil.rmtree(repo.path(".deploy-state"))
    proc = repo.deploy()
    assert not repo.path("New:Proj").exists()
    proc = repo.deploy("--from", sha)
    assert generating(proc) == ["New:Proj"]


# cleanup_on_deploy.py


def test_removed_batch_is_deleted(repo):
    repo.xml(
        "Foo:Bar.xml",
        "Foo:(?P<version>Bar):ToTest",
        f'<batch name="one">{FLAVOR}</batch>',
    )
    repo.commit()
    assert repo.deploy().returncode == 0
    proc = repo.cleanup()
    assert proc.returncode == 0, proc.out
    assert "Foo:Bar:ToTest/two: removing" in proc.out
    assert not repo.path("Foo:Bar:ToTest", "two").exists()
    assert repo.generated("Foo:Bar:ToTest", "one")
    assert not repo.path("Foo:Bar:ToTest", "rsync.lock").exists()


def test_customized_and_foreign_subdirs_are_kept(repo):
    custom = repo.path("Foo:Bar:ToTest", "custom")
    shutil.copytree(repo.path("Foo:Bar:ToTest", "two"), custom)
    custom.joinpath("read_files.sh").write_text("echo custom\n")
    notes = repo.path("Foo:Bar:ToTest", "notes")
    notes.mkdir()
    notes.joinpath("README").write_text("notes\n")
    repo.path("Foo:Bar:ToTest", ".run_last").mkdir()
    proc = repo.cleanup()
    assert proc.returncode == 0
    assert custom.exists() and notes.exists()
    assert proc.out.count("kept because") == 2
    # reported once only
    assert "kept because" not in repo.cleanup().out


def test_live_rsync_lock_defers_cleanup(repo):
    repo.xml(
        "Foo:Bar.xml",
        "Foo:(?P<version>Bar):ToTest",
        f'<batch name="one">{FLAVOR}</batch>',
    )
    repo.git("rm", "-q", "xml/obs/Baz.xml")
    repo.commit()
    rsync = subprocess.Popen(["sleep", "60"])
    try:
        for project in ("Foo:Bar:ToTest", "Baz:Qux"):
            repo.path(project, "rsync.lock").write_text(f"{rsync.pid}\n")
        proc = repo.cleanup()
        assert proc.returncode == 1
        assert "Foo:Bar:ToTest: rsync.sh is running, will retry" in proc.out
        assert "Baz:Qux: rsync.sh is running, will retry" in proc.out
        assert repo.path("Foo:Bar:ToTest", "two").exists()
        assert repo.path("Baz:Qux").exists()
        assert repo.state("cleanup")["pending"] == ["Baz:Qux"]
    finally:
        rsync.kill()
        rsync.wait()
    proc = repo.cleanup()
    assert proc.returncode == 0, proc.out
    assert not repo.path("Foo:Bar:ToTest", "two").exists()
    assert not repo.path("Baz:Qux").exists()
    assert repo.state("cleanup")["pending"] == []


def test_deleted_xml_removes_project(repo):
    repo.git("rm", "-q", "xml/obs/Baz.xml")
    repo.commit()
    proc = repo.cleanup()
    assert proc.returncode == 0, proc.out
    assert "Baz:Qux: removing" in proc.out
    assert not repo.path("Baz:Qux").exists()


@pytest.mark.parametrize("archive", [False, True])
def test_deleted_xml_removes_customized_project(repo, archive):
    repo.path("Baz:Qux", "read_files.sh").write_text("echo custom\n")
    if archive:
        repo.path("xml", "archive", "obs").mkdir(parents=True)
        repo.git("mv", "xml/obs/Baz.xml", "xml/archive/obs/Baz.xml")
    else:
        repo.git("rm", "-q", "xml/obs/Baz.xml")
    repo.commit()
    proc = repo.cleanup()
    assert proc.returncode == 0, proc.out
    assert "removing it with its customized scripts in Baz:Qux" in proc.out
    assert not repo.path("Baz:Qux").exists()


def test_deleted_xml_with_live_lock_is_retried_with_customized_scripts(repo):
    repo.path("Baz:Qux", "read_files.sh").write_text("echo custom\n")
    repo.git("rm", "-q", "xml/obs/Baz.xml")
    repo.commit()
    rsync = subprocess.Popen(["sleep", "60"])
    try:
        repo.path("Baz:Qux", "rsync.lock").write_text(f"{rsync.pid}\n")
        proc = repo.cleanup()
        assert proc.returncode == 1
        assert repo.state("cleanup")["forced"] == ["Baz:Qux"]
    finally:
        rsync.kill()
        rsync.wait()
    proc = repo.cleanup()
    assert proc.returncode == 0, proc.out
    assert not repo.path("Baz:Qux").exists()


def test_changed_pattern_keeps_customized_orphan(repo):
    repo.path("Baz:Qux", "read_files.sh").write_text("echo custom\n")
    repo.xml("Baz.xml", "Baz:Quux")
    repo.commit()
    proc = repo.cleanup()
    assert "kept because of customized scripts in Baz:Qux" in proc.out
    assert repo.path("Baz:Qux").exists()


def test_narrowed_range_removes_disabled_projects(repo):
    stg_xml(repo, 'range="A..C"')
    repo.commit()
    assert repo.deploy().returncode == 0
    assert repo.cleanup().returncode == 0
    repo.path("Stg:Fac:Staging:C", "read_files.sh").write_text("echo custom\n")
    stg_xml(repo, 'range="A..A"')
    repo.commit()
    assert repo.deploy().returncode == 0
    proc = repo.cleanup()
    assert proc.returncode == 0, proc.out
    assert "Stg:Fac:Staging:B: removing" in proc.out
    assert not repo.path("Stg:Fac:Staging:B").exists()
    assert (
        "Stg:Fac:Staging:C: not in <projects_enabled> of xml/obs/Stg.xml any more, but kept"
        in proc.out
    )
    assert repo.path("Stg:Fac:Staging:A").exists()


def test_disabled_project_with_live_lock_is_retried(repo):
    stg_xml(repo, 'range="A..B"')
    repo.commit()
    assert repo.deploy().returncode == 0
    assert repo.cleanup().returncode == 0
    stg_xml(repo, 'project="A"')
    repo.commit()
    rsync = subprocess.Popen(["sleep", "60"])
    try:
        repo.path("Stg:Fac:Staging:B", "rsync.lock").write_text(f"{rsync.pid}\n")
        proc = repo.cleanup()
        assert proc.returncode == 1
        assert repo.state("cleanup")["pending"] == ["Stg:Fac:Staging:B"]
    finally:
        rsync.kill()
        rsync.wait()
    proc = repo.cleanup()
    assert proc.returncode == 0, proc.out
    assert not repo.path("Stg:Fac:Staging:B").exists()


def test_first_projects_enabled_only_reports(repo):
    repo.path("t", "obs", "Stg:Fac:Staging:Q").mkdir()
    repo.path("t", "obs", "Stg:Fac:Staging:Q", "files_iso.lst").write_text("")
    repo.xml("Stg.xml", STG)
    repo.commit()
    assert repo.deploy().returncode == 0
    assert repo.generated("Stg:Fac:Staging:Q")
    stg_xml(repo, 'range="A..B"')
    repo.commit()
    assert repo.deploy().returncode == 0
    proc = repo.cleanup()
    assert proc.returncode == 0, proc.out
    msg = "Stg:Fac:Staging:Q: not in <projects_enabled> of xml/obs/Stg.xml; remove"
    assert msg in proc.out
    assert repo.generated("Stg:Fac:Staging:Q")
    assert msg not in repo.cleanup().out


def test_unrelated_orphan_is_only_reported(repo):
    repo.path("Stray:Dir").mkdir()
    proc = repo.cleanup()
    assert proc.returncode == 0
    assert "Stray:Dir: no XML matches it" in proc.out
    assert repo.path("Stray:Dir").exists()
    shutil.rmtree(repo.path(".deploy-state"))
    repo.git("rm", "-q", "xml/obs/Baz.xml")
    repo.commit()
    proc = repo.cleanup()
    assert "Baz:Qux: no XML matches it" in proc.out
    assert repo.path("Baz:Qux").exists()


def test_batched_to_default(repo):
    repo.xml("Foo:Bar.xml", "Foo:(?P<version>Bar):ToTest")
    repo.commit()
    assert repo.deploy().returncode == 0
    assert repo.cleanup().returncode == 0
    assert repo.generated("Foo:Bar:ToTest")
    assert not repo.path("Foo:Bar:ToTest", "one").exists()
    assert not repo.path("Foo:Bar:ToTest", "two").exists()


# deploy-hook.sh


def install_hooks(clone):
    return subprocess.run(
        ["make", "-s", "install_hooks"],
        cwd=clone.root,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def clone(repo, tmp_path):
    """A clone of repo with the post-merge hook installed and state seeded."""
    subprocess.run(
        ["git", "clone", "-q", str(repo.root), str(tmp_path / "clone-obs")],
        check=True,
        env=git_env(),
    )
    clone = Repo(tmp_path / "clone-obs")
    for project in ("Foo:Bar:ToTest", "Baz:Qux"):
        shutil.copytree(repo.path(project), clone.path(project))
    proc = install_hooks(clone)
    assert proc.returncode == 0, proc.stderr
    assert clone.hook("tick").returncode == 0
    return clone


def test_pull_runs_hook(repo, clone):
    hook = clone.path(".git", "hooks", "post-merge")
    assert hook.resolve() == clone.path("script", "deploy-hook.sh")
    proc = install_hooks(clone)
    assert "already installed" in proc.stdout

    repo.xml(
        "Foo:Bar.xml",
        "Foo:(?P<version>Bar):ToTest",
        f'<batch name="one">{FLAVOR}</batch>',
    )
    repo.xml("New.xml", "New:Proj")
    repo.commit()
    proc = subprocess.run(
        ["git", "-C", str(clone.root), "pull", "-q", "--rebase", "origin", "master"],
        capture_output=True,
        text=True,
        env=git_env(),
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "New:Proj: generating" in proc.stdout + proc.stderr
    assert clone.generated("New:Proj")
    assert not clone.path("Foo:Bar:ToTest", "two").exists()
    assert clone.state("deploy")["sha"] == repo.head()
    assert clone.state("cleanup")["sha"] == repo.head()
    assert clone.hook("tick").returncode == 0


def test_install_hooks_keeps_foreign_hook(clone):
    hook = clone.path(".git", "hooks", "post-merge")
    hook.unlink()
    hook.write_text("#!/bin/sh\n")
    proc = install_hooks(clone)
    assert proc.returncode != 0
    assert "refusing to overwrite" in proc.stderr
    assert hook.read_text() == "#!/bin/sh\n"


def test_hook_ignores_inherited_git_env(clone):
    env = git_env()
    env.update(GIT_DIR=".git", GIT_WORK_TREE=".")
    proc = clone.hook("0", env=env, cwd=clone.path("xml"))
    assert proc.returncode == 0, proc.out
    assert "nothing to generate" in proc.out


def test_hook_exit_codes(repo, clone):
    clone.path("xml", "obs", "Baz.xml").write_text("<openQA")
    proc = clone.hook("tick")
    assert proc.returncode == 1
    assert "deploy_on_pull rc=1 cleanup_on_deploy rc=1" in proc.out
    assert clone.hook("0").returncode == 0
    # squash merge: nothing to do
    assert clone.hook("1").out == ""


def test_hook_needs_owner(clone, tmp_path):
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "id").write_text("#!/bin/sh\necho 99999\n")
    (fake / "id").chmod(0o755)
    env = git_env()
    env["PATH"] = f"{fake}:{env['PATH']}"
    proc = clone.hook("tick", env=env)
    assert proc.returncode == 1
    assert "not run as the owner" in proc.out
    assert clone.hook("0", env=env).returncode == 0


def test_hook_skips_when_locked(clone):
    with open(clone.path(".deploy.lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        proc = clone.hook("tick")
    assert proc.returncode == 0
    assert "another deploy is running" in proc.out
