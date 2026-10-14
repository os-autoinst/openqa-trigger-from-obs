"""Delete batch and project dirs that were removed from the XML (#399).

Runs after deploy_on_pull.py (see script/deploy-hook.sh). rsync.sh syncs
every subfolder of a project dir, so a leftover dir keeps triggering jobs.

- A batch subfolder that is not a batch of the project's XML any more is
  deleted if it holds generated scripts and no customized ones. Every project
  dir is checked on every run.
- A project dir that no XML matches is deleted if the old pattern of an XML
  changed or deleted since the last run (.deploy-state/cleanup.json) matched
  it. Other unmatched dirs are only reported.

Dirs of a project that rsync.sh is syncing are skipped and retried on the
next run.
"""

import argparse
import os
import shutil
import sys

try:
    from . import deploy_common as common
    from . import scriptgen, validate_xml
except ImportError:
    import deploy_common as common
    import scriptgen
    import validate_xml

STATE = "cleanup"


class Cleanup:
    def __init__(self, dry_run, warned, log):
        self.dry_run = dry_run
        self.warned = set(warned)
        self.new_warned = set()
        self.pending = []
        self.failed = False
        self.log = log

    def warn_once(self, msg):
        """Report a condition once, not on every run while it persists."""
        self.new_warned.add(msg)
        if msg not in self.warned:
            self.log.warning(msg)

    def remove(self, path):
        if self.dry_run:
            self.log.info(f"{path}: would remove")
            return
        self.log.info(f"{path}: removing")
        shutil.rmtree(path)

    def custom_scripts(self, project):
        folders = [project] + [
            os.path.join(project, s)
            for s in sorted(os.listdir(project))
            if not s.startswith(".") and os.path.isdir(os.path.join(project, s))
        ]
        return [f for f in folders if common.has_custom_script(f)]

    def orphan(self, project, removed):
        if not removed:
            self.warn_once(
                f"{project}: no XML matches it; remove it by hand if it is not needed"
            )
            return
        custom = self.custom_scripts(project)
        if custom:
            self.warn_once(
                f"{project}: XML removed, but kept because of customized scripts in {', '.join(custom)}"
            )
            return
        if common.rsync_lock_live(project):
            self.log.warning(f"{project}: rsync.sh is running, will retry")
            self.pending.append(project)
            self.failed = True
            return
        if not self.dry_run and not common.take_rsync_lock(project):
            self.log.warning(f"{project}: cannot take rsync.lock, will retry")
            self.pending.append(project)
            self.failed = True
            return
        self.remove(project)

    def stale_batches(self, project):
        try:
            ag = scriptgen.load_generator(project)
        except Exception as e:  # noqa: BLE001 - skip projects scriptgen cannot load
            self.log.error(f"{project}: {e!r}")
            ag = None
        if ag is None:
            self.warn_once(f"{project}: scriptgen cannot load its XML, skipped")
            return
        expected = scriptgen.batch_subfolders(ag)
        stale = []
        for sub in sorted(os.listdir(project)):
            path = os.path.join(project, sub)
            if (
                sub.startswith(".")
                or sub in expected
                or os.path.islink(path)
                or not os.path.isdir(path)
            ):
                continue
            if common.has_generated_script(path) and not common.has_custom_script(path):
                stale.append(path)
            else:
                self.warn_once(
                    f"{path}: not a batch in the XML, kept because it has no generated or has customized scripts"
                )
        if not stale:
            return
        if self.dry_run:
            if common.rsync_lock_live(project):
                self.log.info(f"{project}: rsync.sh is running")
            for path in stale:
                self.remove(path)
            return
        if not common.take_rsync_lock(project):
            self.log.warning(f"{project}: rsync.sh is running, will retry")
            self.failed = True
            return
        try:
            for path in stale:
                self.remove(path)
        finally:
            common.release_rsync_lock(project)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--from", dest="from_rev", metavar="REV", help="process XML changes since REV"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="only print what would be done"
    )
    args = parser.parse_args(argv)

    log = common.Logger("cleanup_on_deploy")
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    patterns = common.validate(log)
    if patterns is None:
        return 1

    head = common.head()
    state = common.read_state(STATE)
    pending = set(state["pending"]) if state else set()
    old = args.from_rev or (state["sha"] if state else None)
    old_patterns = {}
    if old is None:
        log.info("no state, unmatched project dirs are only reported")
    elif not common.commit_exists(old):
        log.warning(f"unknown commit {old}, unmatched project dirs are only reported")
    else:
        xml_changes = common.changed_xmls(common.changed_paths(old, head))
        old_patterns = common.old_patterns(old, [p for s, p in xml_changes if s != "A"])

    cleanup = Cleanup(args.dry_run, state.get("warned", []) if state else [], log)
    for project in common.project_dirs():
        matching = common.matching_xmls(project, patterns)
        if not matching:
            removed = project in pending or any(
                validate_xml.full_match(r, project) for r in old_patterns.values()
            )
            cleanup.orphan(project, removed)
        elif len(matching) > 1:
            cleanup.warn_once(
                f"{project}: matched by more than one XML ({', '.join(matching)}), skipped"
            )
        else:
            cleanup.stale_batches(project)

    if not args.dry_run:
        common.write_state(
            STATE,
            {
                "sha": head,
                "pending": sorted(set(cleanup.pending)),
                "warned": sorted(cleanup.new_warned),
            },
        )
    return 1 if cleanup.failed else 0


if __name__ == "__main__":
    sys.exit(main())
