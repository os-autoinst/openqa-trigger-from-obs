# openqa-trigger-from-obs

This is work in progress project aiming to simplify integration between Open
Build Service (OBS) and openqa.opensuse.de (o3).

## Concepts

OBS projects have wide variety of content, types and configuration and keep
only latest version in published locations.
https://openbuildservice.org/help/manuals/obs-user-guide/cha.obs.prjconfig.html

OpenQA in most cases expects flat structure of iso files and repositories
http://open.qa/docs/#_adding_a_new_iso_to_test and most often needs to keep
several versions at the same time (e.g. to compare behavior).

It appears to be quite a challenge to have universal, automatic and flexible way
to deliver outcomes from OBS and run tests against them in OpenQA.
But both teams are working on making the systems closer.

The main focus of openqa-trigger-from-obs project is to provide a framework to
help in review and acknowledgement actions, which will be performed.

## Testability

The synchronisation process is split into phases:
1. Read list of files from remote location
2. Generate rsync commands and openQA client calls based on the lists of files
3. Run generated commands

The main complexity comes in phase 2, but it is easiest way for human to spot
any problem and aknowledge outcome by comparing generated commands before and
after any modifications in code.

## Which OBS Projects may be covered by synchronisation scripts

Synchronisation scripts may cover those OBS projects which have corresponding
folder listed in test directory `ls -d t/*/` or which follow rules identical
to one of those projects.

## Changes needed for existing projects

Typical steps will consist:
1. Investigate corresponding part in scriptgen.py and change according to new
requirements.
2. Re-generate scripts in test folders `make test_regen_all`
3. Update .before scripts in test folders `make test_update_before_files`
4. Run consistency tests `make test`
5. Review and acknowledge impact on projects e.g. `git difftool`
The commands will highlight all affected projects and exact changes and side
effects.
6. Create Merge Request and let affected stakeholders review and acknowledge
the changes.

## Adding new projects

TBD

## Deploy scripts, Rsync binaries from OBS, start OpenQA tests

Steps needed during deployment:
1. Make sure corresponding .xml file exists and project is covered in tests
2. Create folder with OBS project name, which will store generated scripts
and logs, then generate scripts

```
mkdir Leap:15.2:ToTest
python3 script/scriptgen.pl Leap:15.2:ToTest
```

3. Call rsync.sh to do start actual synchronization:

```
bash script/rsync.sh Leap:15.2:ToTest
```
