"""Helpers shared by deploy_on_pull.py and cleanup_on_deploy.py.

All paths are relative to the repository root, which must be the cwd (same
as for scriptgen.py, which takes the brand from the cwd name).
"""

import json
import os
import re
import subprocess
import sys
from xml.etree import ElementTree

try:
    from . import scriptgen, validate_xml
except ImportError:
    import scriptgen
    import validate_xml

STATE_DIR = ".deploy-state"
SCRIPTS = (
    "read_files.sh",
    "print_rsync_iso.sh",
    "print_rsync_repo.sh",
    "print_openqa.sh",
)
# changes to these files affect the scripts of every project
GENERATOR_FILES = ("script/scriptgen.py", "script/cfg.py")


class Logger:
    def __init__(self, prog):
        self.prog = prog

    def info(self, msg):
        print(f"{self.prog}: {msg}", flush=True)

    def warning(self, msg):
        print(f"{self.prog}: WARNING: {msg}", file=sys.stderr, flush=True)

    def error(self, msg):
        print(f"{self.prog}: ERROR: {msg}", file=sys.stderr, flush=True)


def git(*args):
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout


def head():
    return git("rev-parse", "--verify", "HEAD^{commit}").strip()


def commit_exists(rev):
    try:
        git("rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")
    except subprocess.CalledProcessError:
        return False
    return True


def brand():
    return scriptgen.detect_xml_dir("")


def xml_dir():
    return "xml/" + brand()


def generator_files():
    return GENERATOR_FILES + (f"script/{brand()}.py",)


def project_dirs():
    """Top-level project dirs (`*:*`, like .gitignore), sorted."""
    return sorted(
        d
        for d in os.listdir(".")
        if ":" in d
        and not d.startswith(".")
        and os.path.isdir(d)
        and not os.path.islink(d)
    )


def matching_xmls(project, patterns):
    """All XMLs whose pattern matches project, sorted."""
    return sorted(x for x, r in patterns.items() if validate_xml.full_match(r, project))


def mapped_xml(project):
    """The XML scriptgen uses for project, or ""."""
    try:
        xmlfile, _, _ = scriptgen.find_xml(project, brand())
    except Exception as e:  # noqa: BLE001 - treat any scriptgen failure as unmapped
        print(f"{project}: scriptgen cannot map it: {e!r}", file=sys.stderr)
        return ""
    return os.path.normpath(xmlfile) if xmlfile else ""


def changed_paths(old, new):
    """[(status, path)] between two commits, renames split into D + A."""
    out = git("diff", "--name-status", "--no-renames", "-z", old, new)
    fields = out.split("\0")
    return [(fields[i][0], fields[i + 1]) for i in range(0, len(fields) - 1, 2)]


def changed_xmls(changes):
    prefix = xml_dir() + "/"
    return [(s, p) for s, p in changes if p.startswith(prefix) and p.endswith(".xml")]


def old_patterns(rev, paths):
    """Compiled project_pattern of each path as of rev; unparsable ones are skipped."""
    patterns = {}
    for path in paths:
        try:
            content = git("show", f"{rev}:{path}")
            pattern = ElementTree.fromstring(content).attrib.get("project_pattern", "")
            if pattern:
                patterns[path] = re.compile(pattern)
        except (subprocess.CalledProcessError, ElementTree.ParseError, re.error):
            continue
    return patterns


def validate(log):
    """Validate the XMLs of the current brand. Returns the patterns or None."""
    if not os.path.isdir(xml_dir()):
        log.error(f"{xml_dir()} not found, run from the repository root")
        return None
    result = validate_xml.validate([xml_dir()])
    for e in result.errors:
        log.error(e)
    if result.errors:
        log.error(f"{xml_dir()} is invalid, nothing done")
        return None
    return result.patterns


def state_path(name):
    return os.path.join(STATE_DIR, name + ".json")


def read_state(name):
    """{"sha": str, "pending": [str], ...} or None if missing or corrupt."""
    try:
        with open(state_path(name)) as f:
            state = json.load(f)
    except (OSError, ValueError):
        return None
    if (
        not isinstance(state, dict)
        or not isinstance(state.get("sha"), str)
        or not state["sha"]
    ):
        return None
    pending = state.get("pending", [])
    state["pending"] = (
        [p for p in pending if isinstance(p, str)] if isinstance(pending, list) else []
    )
    return state


def write_state(name, state):
    os.makedirs(STATE_DIR, exist_ok=True)
    path = state_path(name)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def rsync_lock_path(project):
    return os.path.join(project, "rsync.lock")


def _lock_pid(project):
    """PID in the lock file, None if there is no lock file, -1 if unreadable."""
    try:
        with open(rsync_lock_path(project)) as f:
            content = f.read().strip()
    except FileNotFoundError:
        return None
    except OSError:
        return -1
    try:
        return int(content)
    except ValueError:
        return 0


def rsync_lock_live(project):
    """Same test as rsync.sh: the lock file holds the PID of a running process."""
    pid = _lock_pid(project)
    if pid is None or pid == 0:
        return False
    if pid < 0:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def take_rsync_lock(project):
    """Take the rsync.sh lock of project. Returns False if it is held."""
    if rsync_lock_live(project):
        return False
    with open(rsync_lock_path(project), "w") as f:
        f.write(f"{os.getpid()}\n")
    return _lock_pid(project) == os.getpid()


def release_rsync_lock(project):
    if _lock_pid(project) == os.getpid():
        os.remove(rsync_lock_path(project))


def has_generated_script(folder):
    for name in SCRIPTS:
        try:
            with open(os.path.join(folder, name)) as f:
                head = f.readline() + f.readline()
        except (OSError, UnicodeDecodeError):
            continue
        if "GENERATED" in head:
            return True
    return False


def has_custom_script(folder):
    for name in SCRIPTS:
        try:
            if scriptgen.is_customized(os.path.join(folder, name)):
                return True
        except (OSError, UnicodeDecodeError):
            return True
    return False
