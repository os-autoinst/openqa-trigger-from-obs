"""Regenerate the scripts of the projects whose XML changed (#402).

Runs after `git pull` (see script/deploy-hook.sh). Compares the commit it
processed last (stored in .deploy-state/deploy.json) with HEAD and runs
scriptgen.py for:

- every project dir, if scriptgen.py, cfg.py or the brand plugin changed;
- every project dir mapped to a changed XML, or matched by the old pattern of
  a changed or deleted XML;
- the missing project dirs listed by <projects_enabled> of an added or
  changed XML (or of every XML, without state or with --all), which are
  created first;
- the project dirs of a newly added XML without <projects_enabled>, which are
  created first: its literal project_pattern, or the t/<brand> test dirs that
  match it (validate_xml.project_names()).

Projects that fail are retried on the next run.
"""

import argparse
import os
import subprocess
import sys

try:
    from . import deploy_common as common
    from . import validate_xml
except ImportError:
    import deploy_common as common
    import validate_xml

STATE = "deploy"


def is_project_name(name):
    return ":" in name and validate_xml.is_safe_name(name)


def plan(old, head, result, pending, log):
    """Return (targets, create, errors, failed_xmls).

    result is the validate_xml.Result of the XMLs. targets: project dirs to
    generate, create: the ones to mkdir first.
    """
    patterns = result.patterns
    dirs = common.project_dirs()
    mapped = {d: common.mapped_xml(d) for d in dirs}
    targets = set()
    create = set()
    errors = []
    failed_xmls = []

    added = []
    changed = set()
    if old is None:
        full = True
    else:
        changes = common.changed_paths(old, head)
        generator = common.generator_files()
        full = any(p in generator for _, p in changes)
        xml_changes = common.changed_xmls(changes)
        changed = {os.path.normpath(p) for _, p in xml_changes}
        added = [os.path.normpath(p) for s, p in xml_changes if s == "A"]
        old_patterns = common.old_patterns(old, [p for s, p in xml_changes if s != "A"])
        for d in dirs:
            if not mapped[d]:
                continue
            if mapped[d] in changed or any(
                validate_xml.full_match(r, d) for r in old_patterns.values()
            ):
                targets.add(d)

    if full:
        targets.update(d for d in dirs if mapped[d])

    for p in pending:
        if p.endswith(".xml"):
            added.append(p)
        elif mapped.get(p):
            targets.add(p)

    test_dirs = validate_xml.tracked_test_dirs(common.brand())
    added = set(added)
    for xml in sorted(added - set(patterns)):
        log.info(f"{xml}: no longer exists, skipped")
    for xml in sorted(patterns):
        existing = {d for d in dirs if mapped[d] == xml}
        if xml in result.enabled:
            # the dirs of <projects_enabled> are created whenever the XML changes
            if not (full or xml in added or xml in changed):
                continue
            names = set(result.enabled[xml]) - existing
        elif xml in added:
            names = (
                set(validate_xml.project_names(patterns[xml].pattern, test_dirs))
                - existing
            )
        else:
            continue
        ok = True
        for name in sorted(names):
            if not is_project_name(name):
                errors.append(f"{xml}: {name!r} is not a valid project dir name")
                ok = False
            elif common.mapped_xml(name) != xml:
                errors.append(
                    f"{xml}: project {name} would be generated from "
                    f"{common.mapped_xml(name) or 'no XML'}; fix the project_pattern"
                )
                ok = False
            else:
                create.add(name)
        if xml not in result.enabled and not existing and not names:
            errors.append(
                f"{xml}: added, but no project name can be derived from its "
                "project_pattern; make the pattern literal, add <projects_enabled> "
                f"or add a t/{common.brand()}/<Project> test dir"
            )
            ok = False
        targets.update(n for n in names if n in create)
        if xml in added:
            targets.update(existing)
        if not ok:
            failed_xmls.append(xml)
    return sorted(targets), create, errors, failed_xmls


def generate(project, log):
    proc = subprocess.run(
        [sys.executable, "script/scriptgen.py", project],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in (proc.stdout + proc.stderr).splitlines():
        log.info(f"{project}: scriptgen: {line}")
    return proc.returncode == 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--from", dest="from_rev", metavar="REV", help="process changes since REV"
    )
    group.add_argument("--all", action="store_true", help="regenerate all project dirs")
    parser.add_argument(
        "--dry-run", action="store_true", help="only print what would be done"
    )
    args = parser.parse_args(argv)

    log = common.Logger("deploy_on_pull")
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    result = common.validate(log)
    if result is None:
        return 1

    head = common.head()
    state = common.read_state(STATE)
    pending = state["pending"] if state else []
    old = args.from_rev or (state["sha"] if state else None)
    if args.all:
        old = None
    elif old is None:
        log.info("no state, regenerating all project dirs (new XMLs need --from REV)")
    elif not common.commit_exists(old):
        log.warning(f"unknown commit {old}, regenerating all project dirs")
        old = None
    elif old != head:
        log.info(f"processing {old[:12]}..{head[:12]}")

    targets, create, errors, failed = plan(old, head, result, pending, log)
    new_pending = list(failed)
    for e in errors:
        log.error(e)

    for project in targets:
        if args.dry_run:
            log.info(
                f"{project}: would {'create and ' if project in create else ''}generate"
            )
            continue
        if project in create:
            log.info(f"{project}: creating project dir")
            os.makedirs(project, exist_ok=True)
        log.info(f"{project}: generating")
        if not generate(project, log):
            log.error(f"{project}: scriptgen failed, will retry")
            new_pending.append(project)

    if not targets:
        log.info("nothing to generate")
    if not args.dry_run:
        common.write_state(STATE, {"sha": head, "pending": sorted(set(new_pending))})
    return 1 if errors or new_pending else 0


if __name__ == "__main__":
    sys.exit(main())
