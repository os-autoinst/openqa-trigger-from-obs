# openqa-trigger-from-obs
[![CircleCI](https://dl.circleci.com/status-badge/img/gh/os-autoinst/openqa-trigger-from-obs/tree/master.svg?style=svg)](https://dl.circleci.com/status-badge/redirect/gh/os-autoinst/openqa-trigger-from-obs/tree/master)

This project is aiming to simplify the integration between the Open
Build Service (OBS) and openqa.opensuse.org (o3).

See [FEATURES.md](FEATURES.md) for what the XML attributes do and how the
generated scripts behave.

## Concepts

OBS projects have a wide variety of content, types and configuration and keep
only the latest version in published locations.
https://openbuildservice.org/help/manuals/obs-user-guide/cha.obs.prjconfig.html

OpenQA in most cases expects a flat structure of iso files and repositories
http://open.qa/docs/#_adding_a_new_iso_to_test and most often needs to keep
several versions at the same time (e.g. to compare behavior).

It appears to be quite a challenge to have a universal, automatic and flexible
way to deliver outcomes from OBS and run tests against them in OpenQA. But
both teams are working on making the systems closer.

The main focus of the openqa-trigger-from-obs project is to provide a
framework to help in review and acknowledgement actions, which will be
performed.

## Testability

The synchronisation process is split into phases:
1. Read list of files from remote location
2. Generate rsync commands and openQA client calls based on the lists of files
3. Run generated commands

The main complexity comes in phase 2, but it is the easiest way for a human to
spot any problem and aknowledge the outcome by comparing the generated
commands before and after any modifications in code.

## Which OBS Projects may be covered by synchronisation scripts

Synchronisation scripts may cover those OBS projects which have corresponding
folder listed in test directory `ls -d t/*/` or which follow rules identical
to one of those projects.

## Changes needed for existing projects

Typical steps:
1. Investigate the corresponding part in *scriptgen.py* and change according to
   new requirements.
2. Re-generate scripts in test folders with `make test_regen_all`
3. Update *.before* scripts in test folders with `make test_update_before_files`
4. Run consistency tests with `make test`
5. Review and acknowledge impact on projects e.g. `git difftool`
The commands will highlight all affected projects and exact changes and side
effects.
6. Create Merge Request and let affected stakeholders review and acknowledge
the changes.

## Adding new projects

The goal here is to add a new project to the test framework, so it will be
possible to preview exact commands and limit the chance that an occasional
commit affects them in the future.

Note: For convenience, `script/scriptgen.py` supports `--rsync-user` to specify
the rsync user, so the generation of `.lst` files can be done without modifying
the `read_files.sh` scripts or sudoing as the user that owns the `rsync.secret`
file. This is also baked into the Makefile so `RSYNC_USER=alice make test_regen_all`
will generate the scripts using the `alice` rsync user.

1. Find a project with similar settings, create a copy of its xml file and
   tweak changes as needed.
2. Create folder *t/obs/ProjectName* and generate scripts using
   `make test_regen_all`
3. Examine the script for the first phase (read `Testability` section above)
   *t/obs/ProjectName/read_files.sh*
4. Use generated commands `rsync --list-only` to create files 
   *t/obs/ProjectName/\*.lst* 
   the same way they are created in *read_files.sh*
5. Generate rsync and openqa commands based on these new *.lst files
   `make test_update_before_files`
6. Run consistency test `make test` and `make validate_xml`. CI rejects an XML
   that `make validate_xml` rejects, e.g. one whose `project_pattern` is a regex
   without `<projects_enabled>` (see below) that no *t/obs/ProjectName* folder
   matches: the automatic deployment could not tell which project folder to
   create for it.
   `make validate_xml` also checks every XML against the schema
   *xml/openQA.rng*, which needs `xmllint` (package `libxml2-tools`). The
   schema allows only the elements and attributes that `script/scriptgen.py`
   reads, so it catches misspelt attributes. If you teach `scriptgen.py` a new
   attribute, add it to the schema as well.
7. Review and test bash commands generated in, which will be executed in
   production:
   * t/obs/ProjectName/print_rsync_iso.before
   * t/obs/ProjectName/print_rsync_repo.before
   * t/obs/ProjectName/print_openqa.before
8. Add to a new git commit the xml file and *t/obs/ProjectName* folder
```
git checkout -b add_projectname
git add xml/obs/ProjectName.xml t/obs/ProjectName
git commit -m 'Add ProjectName'
git push origin add_projectname
```
9. Create a pull request from add_projectname branch and make sure CI shows
   green outcome

## Deploy scripts, Rsync binaries from OBS, start OpenQA tests

Steps needed during deployment:
1. Make sure the corresponding .xml file exists and the project is covered in
   tests
2. Create a folder with the OBS project name, which will store generated
   scripts and logs, then generate scripts

```
mkdir Leap:15.2:ToTest
python3 script/scriptgen.py Leap:15.2:ToTest
```

3. Call rsync.sh to start the synchronization:

```
bash script/rsync.sh Leap:15.2:ToTest
```

### Automatic deployment

There is now the posibility to enable automated deployment (cleanup and generation)
by calling `script/deploy-hook.sh [--force] [tick|hook]`, by default it runs in `hook` mode;
`--force` regenerates all project folders (`deploy_on_pull.py --all`)

1. `script/deploy_on_pull.py`: runs `scriptgen.py` for the projects whose XML
   changed, for all projects if `scriptgen.py`, `cfg.py` or the brand plugin
   changed, and creates and generates the project folders of a newly added XML.
   
   The project folders of an XML are listed by its `<projects_enabled>`
   elements ([see below](#project_pattern)). Without them, the folder name is the
   `project_pattern` if it is a literal name, otherwise the `t/obs/ProjectName`
    folders that match it; these are created only when the XML is added.
2. `script/cleanup_on_deploy.py`: deletes batch folders whose batch is no
   longer in the XML, project folders whose XML no longer matches them, and
   project folders dropped from `<projects_enabled>`. Folders with customized
   scripts (no `GENERATED` header) are kept and reported. Project folders of
   a deleted (or archived) XML are deleted even if they have customized
   scripts. Batch folders of a project whose generation failed are kept
   until it succeeds.

Both skip the projects that `rsync.sh` is syncing (live `rsync.lock`) and
retry them on the next run; they hold the lock while they change a project.
A project folder matched by more than one XML is not generated.

Running the deploy hooks will store the last commit and projects on a succesful
run and tracks them in `.deploy-state`. 

First-time setup (as the user that owns the checkout, e.g. `geekotest`):

```
python3 script/deploy_on_pull.py --dry-run
python3 script/cleanup_on_deploy.py --dry-run
script/deploy-hook.sh tick   # regenerates all project folders, stores the state
make install_hooks           # runs script/deploy-hook.sh as git post-merge hook
```

The *post-merge* hook only runs when a pull brings new commits, so with the
hook alone, work left for retry (a failed `scriptgen.py`, a project that
`rsync.sh` was syncing) waits for the next commit. To retry it on every
update, call the script from `OnSuccess=` line as well in the systemd unit
in `tick` mode so it runs after every pull. Nothing happens if nothing changed

A `git pull --rebase` that has to rebase local commits does not run the 
*post-merge* hook; the next update catches up.

To run the scripts by hand while the hook may run, hold the same lock:
`flock .deploy.lock python3 script/deploy_on_pull.py`.

### Automatic deployment via systemd:

Enable `systemd/openqa-trigger-from-obs-update.service` to run `script/deploy-hook.sh tick`
after each update. The service holds the same lock as the hook, so they can run together. 

#### Enabled projects {#project_pattern}

A `project_pattern` with a character class, such as
`openSUSE:(?P<version>Factory):(Staging:[A-Z]|Rings:1-MinimalX)`, states which
projects the deployment creates with `<projects_enabled>`:

```xml
<projects_enabled range="A..O" project="Z"/>
```

`range="X..Y"` is inclusive; both ends are single letters or both numbers.
`project` adds comma-separated values of the same kind (letters or numbers)
or literal alternatives of the pattern, such as `Rings:1-MinimalX`.
Several elements can be given; values are deduplicated. Each value replaces
the one character class of the pattern (with its quantifier, e.g. `[0-9]+`)
and must match it; the rest of the pattern must be literal or literal
alternatives. The example enables `openSUSE:Factory:Staging:A` to `O`, `Z`
and `openSUSE:Factory:Rings:1-MinimalX`. `make validate_xml` rejects an
invalid element, and warns about *t/obs/ProjectName* folders that are not
enabled. `scriptgen.py` ignores the element.

`deploy_on_pull.py` creates the missing enabled folders whenever the XML
changes (or with `--all`). `cleanup_on_deploy.py` deletes the folders that a
change removed from the enabled set; folders that were not enabled before
(e.g. when `<projects_enabled>` is first added) are only reported.

#### Archiving an XML

XMLs of projects that are gone can be moved to *xml/archive/obs/*, outside
*xml/obs*, so that neither `scriptgen.py` nor the checks see them. For the
deployment this is a deletion: the next run deletes the project folders that
the XML matched, including customized ones.


## Further information

Find some presentation slides on
https://slides.com/andriinikitin/obs-to-openqa

## License

This project is licensed under the MIT license, see LICENSE file for details.
