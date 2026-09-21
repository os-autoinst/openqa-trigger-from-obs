# Contributing

This file is about *how* to work on this project. For what the XML attributes
do, see [FEATURES.md](FEATURES.md). For the steps to add a project or change an
existing one, see [README.md](README.md).

It is written for humans and for coding agents. The advice comes from real
changes made here, so follow it unless you have a reason not to.

## Understand the pipeline before you edit anything

Nothing in this project runs against OBS during development. Everything is text
generation, and every stage is on disk:

1. `xml/{obs,ibs,abs}/<Project>.xml` describes a project.
2. `script/scriptgen.py` reads it and prints shell scripts. The shell text
   itself lives in `script/cfg.py` as templates with uppercase placeholders
   (`PRODUCTPATH`, `FLAVORLIST`, `SHAEXT`, ...). `ActionBatch.p()` substitutes
   the placeholders and prints the line.
3. The generated scripts land in `t/<brand>/<Project>/*.sh`. These are
   gitignored.
4. The tests *run* those scripts against the recorded `*.lst` file listings and
   compare the output with the tracked `*.before` files.

So the tracked expectation is the **output of the generated script**, not the
script. A change that only moves text around inside a script, with the same
result, produces no diff in `t/`. That is a feature: use it.

Read the generated `.sh` for a project you care about before and after your
change. It is the fastest way to see what you did.

## Write the plan first

Before the first line of code, write down:

- the root cause, in terms of the pipeline above;
- which of the four stages you are changing;
- what the output should look like in each case;
- how you will prove it.

A plan is cheap and stops you from fixing the symptom in the wrong stage. For
example, a per-flavor value cannot be fixed in `p()` alone, because `p()` runs
once per template and the generated shell loops over all flavors of a batch at
run time. The fix has to move the decision into the generated script.

## Keep the change small and keep the output stable

- Change only the lines that the request needs. No drive-by refactors, no
  renames, no formatting sweeps. The diff in `t/` is how reviewers approve a
  change, and unrelated churn makes that impossible.
- Prefer a change that leaves the generated output byte-identical when the new
  feature is not in use. A useful trick: keep the old code path and only take
  the new one when the new attribute is present. When you remove a marker from
  a template, remove its trailing newline with it, otherwise every generated
  file gains a blank line.
- If you must change the output, you must be able to explain every affected
  project. See "Review the diff" below.

## Remember that the generated shell runs under `set -e`

`script/cfg.py` starts every script with `set -e`. That means:

- `[ cond ] && a || b` is a trap. When `a` is the last command of the script and
  the condition is false, the script exits non-zero. Write `[ ! cond ] || a`
  instead, and set the default before the test.
- Per-flavor data belongs in a bash associative array, declared once at the top
  and read inside the loop. The generator already does this for `flavor_filter`,
  `flavor_distri`, `iso_folder` and others. Follow that idiom instead of
  inventing a new one.
- Shell variables the generator introduces should be lowercase, so they cannot
  collide with the uppercase template placeholders.

## The fast loop

Regenerate one project and look at it:

```
python3 script/scriptgen.py t/obs/openSUSE:Factory:Staging:J
```

Then read `t/obs/openSUSE:Factory:Staging:J/print_rsync_iso.sh`. If you want the
actual commands rather than the script, run it: the three `print_*.sh` scripts
only `echo`, so they are safe to execute. `read_files.sh` is the exception, it
talks to the server.

Pick a project that really exercises your change. For anything about flavors,
`openSUSE:Factory:Staging:J` is a good one: it mixes plain flavors, image
flavors and flavors with their own attributes.

## Tests

Unit and integration tests live in `tests/` and run with `pytest`. The
`pythonpath = ["."]` setting in `pyproject.toml` lets them do
`from script.scriptgen import ...`.

- Unit tests should drive the smallest thing that holds the logic. Build an
  `ActionBatch`, feed it XML nodes with `ElementTree.fromstring`, and assert on
  its attributes or on what `p()` writes to a `StringIO`.
- Integration tests should write a small XML file to `tmp_path`, run
  `ActionGenerator.doFile()` on it, and assert on the generated text. Write one
  fixture with a `<batch>` and one without: the two paths through `doFile()` are
  different. `xml/abs/*.xml` are the smallest real examples to copy from.
- Always add a test that proves the *unchanged* case is still unchanged. It is
  the one that catches accidental churn.
- Some attributes are only set inside `doFile()`. If you construct an
  `ActionGenerator` by hand you may have to set `iso_path`, `repo_path` and
  `domain` yourself. Say so in a comment.

## Review the diff in `t/`

```
make test_update_before_files
git status --short t/
```

For every project that moved, be able to say why. The reliable way is to grep
the XML for the attribute you touched and compare the list against the projects
that changed. A project that uses the attribute but did *not* change is just as
much a result as one that did, and you should be able to explain that too.

If a project changed and you cannot explain it, you have a second bug.

## Checks to run before you open a pull request

```
make all          # test_update_before_files + test
make unit_tests
make ruff_check
make ruff_format
make ty_check
```

`ruff format --check` only reports; run `ruff format <file>` to fix. Do not run
`make test_docker` or `make update_files.lst` unless you mean to: the first
needs a container runtime, the second rewrites the recorded `.lst` listings from
the live server.

Note that `test_python_style` lists itself as one of its own prerequisites and
does not work. Run the three checks separately.

## The IBS plugin

`script/ibs.py` is a symlink to `../openqa-trigger-from-ibs-plugin/ibs.py`, a
separate git repository. It subclasses the generator and overrides some of the
templates from `script/cfg.py`.

If you change a template, grep the plugin for it. If the plugin overrides it,
you must make the same change there, on a branch with the same name, and say so
in your pull request. If it does not, say that too, and back it with the `t/ibs`
part of `make test` staying clean.

## Commits and attribution

- One logical change per commit: the fix, the regenerated expectations, the
  tests and the documentation are separate commits. It makes the `t/` diff
  reviewable on its own.
- Write commit messages that say what changed and why, not how.
- Work produced with the help of an LLM carries an `Assisted-by:` trailer, for
  example `Assisted-by: LLM claude-opus-5`. The assistant does not add
  `Signed-off-by` or `Co-Authored-By`; the human author signs off. The pull
  request description carries the generated-content disclosure. This follows the
  kernel attribution rules:
  <https://docs.kernel.org/_sources/process/coding-assistants.rst.txt> and
  <https://docs.kernel.org/_sources/process/generated-content.rst.txt>.

## Documentation

If you add or change an XML attribute, add a short section to `FEATURES.md`.
Describe what it does and how to use it, not how it is implemented. The code
and this file cover the implementation.
