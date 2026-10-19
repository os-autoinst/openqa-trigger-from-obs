"""Delete batch and project dirs that were removed from the XML (#399).

Runs after deploy_on_pull.py (see script/deploy-hook.sh). rsync.sh syncs
every subfolder of a project dir, so a leftover dir keeps triggering jobs.

- A batch subfolder that is not a batch of the project's XML any more is
  deleted if it holds generated scripts and no customized ones. Every project
  dir is checked on every run.
- A project dir that no XML matches is deleted if the old pattern of an XML
  changed or deleted since the last run (.deploy-state/cleanup.json) matched
  it. If the XML was deleted (or moved out of xml/<brand>, e.g. archived),
  the dir is deleted even if it has customized scripts; otherwise customized
  scripts keep it. Other unmatched dirs are only reported.
- A project dir that was dropped from <projects_enabled> of its XML since the
  last run is deleted unless it has customized scripts. Matched dirs that are
  not enabled for another reason (e.g. when <projects_enabled> is first
  added) are only reported.

Dirs of a project that rsync.sh is syncing are skipped and retried on the
next run. Batch subfolders of a project whose generation failed
(deploy_on_pull.py will retry it) are kept until it succeeds.
"""

import argparse
import os
import shutil
import sys

try:
    from . import deploy_common as common
    from . import deploy_on_pull, scriptgen, validate_xml
except ImportError:
    import deploy_common as common
    import deploy_on_pull
    import scriptgen
    import validate_xml

STATE = "cleanup"


class Cleanup:
    def __init__(self, dry_run, warned, log):
        self.dry_run = dry_run
        self.warned = set(warned)
        self.new_warned = set()
        self.pending = []
        self.forced = []
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

    def orphan(self, project, removed, forced=False, reason="XML removed"):
        """Remove project if removed. Customized scripts keep it unless forced."""
        if not removed:
            self.warn_once(
                f"{project}: no XML matches it; remove it by hand if it is not needed"
            )
            return
        custom = self.custom_scripts(project)
        if custom and not forced:
            self.warn_once(
                f"{project}: {reason}, but kept because of customized scripts in {', '.join(custom)}"
            )
            return
        if common.rsync_lock_live(project):
            self.log.warning(f"{project}: rsync.sh is running, will retry")
            self.retry(project, forced)
            return
        if not self.dry_run and not common.take_rsync_lock(project):
            self.log.warning(f"{project}: cannot take rsync.lock, will retry")
            self.retry(project, forced)
            return
        if custom:
            self.log.warning(
                f"{project}: {reason}, removing it with its customized scripts in {', '.join(custom)}"
            )
        self.remove(project)

    def retry(self, project, forced):
        self.pending.append(project)
        if forced:
            self.forced.append(project)
        self.failed = True

    def stale_batches(self, project, deploy_pending):
        if project in deploy_pending:
            self.log.warning(
                f"{project}: not generated yet, its old batches are kept until it is"
            )
            return
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

    result = common.validate(log)
    if result is None:
        return 1
    patterns = result.patterns

    head = common.head()
    state = common.read_state(STATE)
    pending = set(state["pending"]) if state else set()
    forced = set(state.get("forced", [])) & pending if state else set()
    old = args.from_rev or (state["sha"] if state else None)
    old_patterns = {}
    deleted_patterns = {}
    disabled = set()
    if old is None:
        log.info("no state, unmatched project dirs are only reported")
    elif not common.commit_exists(old):
        log.warning(f"unknown commit {old}, unmatched project dirs are only reported")
    else:
        xml_changes = common.changed_xmls(common.changed_paths(old, head))
        old_patterns = common.old_patterns(old, [p for s, p in xml_changes if s != "A"])
        deleted = {p for s, p in xml_changes if s == "D"}
        deleted_patterns = {p: r for p, r in old_patterns.items() if p in deleted}
        old_enabled = common.old_enabled(
            old, [p for s, p in xml_changes if s not in ("A", "D")]
        )
        for xml, names in old_enabled.items():
            if os.path.normpath(xml) in result.enabled:
                disabled |= names - set(result.enabled[os.path.normpath(xml)])

    deploy_state = common.read_state(deploy_on_pull.STATE)
    deploy_pending = set(deploy_state["pending"]) if deploy_state else set()

    cleanup = Cleanup(args.dry_run, state.get("warned", []) if state else [], log)
    for project in common.project_dirs():
        matching = common.matching_xmls(project, patterns)
        if not matching:
            force = project in forced or any(
                validate_xml.full_match(r, project) for r in deleted_patterns.values()
            )
            removed = (
                force
                or project in pending
                or any(
                    validate_xml.full_match(r, project) for r in old_patterns.values()
                )
            )
            cleanup.orphan(project, removed, force)
        elif len(matching) > 1:
            cleanup.warn_once(
                f"{project}: matched by more than one XML ({', '.join(matching)}), skipped"
            )
        elif project not in result.enabled.get(matching[0], [project]):
            reason = f"not in <projects_enabled> of {matching[0]} any more"
            if project in disabled or project in pending:
                cleanup.orphan(project, True, reason=reason)
            else:
                cleanup.warn_once(
                    f"{project}: not in <projects_enabled> of {matching[0]}; "
                    "remove it by hand if it is not needed"
                )
                cleanup.stale_batches(project, deploy_pending)
        else:
            cleanup.stale_batches(project, deploy_pending)

    if not args.dry_run:
        common.write_state(
            STATE,
            {
                "sha": head,
                "pending": sorted(set(cleanup.pending)),
                "forced": sorted(set(cleanup.forced)),
                "warned": sorted(cleanup.new_warned),
            },
        )
    return 1 if cleanup.failed else 0


if __name__ == "__main__":
    sys.exit(main())
