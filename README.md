# openqa-trigger-from-obs

This project is aiming to simplify the integration between the Open
Build Service (OBS) and openqa.opensuse.de (o3).

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
1. Investigate the corresponding part in scriptgen.py and change according to
   new requirements.
2. Re-generate scripts in test folders with `make test_regen_all`
3. Update .before scripts in test folders with `make test_update_before_files`
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

1. Find a project with similar settings, create a copy of its xml file and
   tweak changes as needed.
2. Create folder t/obs/ProjectName and generate scripts using
   `make test_regen_all`
3. Examine the script for the first phase (read `Testability` section above)
   t/obs/ProjectName/read_files.sh
4. Use generated commands `rsync --list-only` to create files 
t/obs/ProjectName/*.lst
the same way they are created in read_files.sh
5. Generate rsync and openqa commands based on these new *.lst files
`make test_update_before_files`
6. Run consistency test `make test`
7. Review and test bash commands generated in, which will be executed in
   production:
t/obs/ProjectName/print_rsync_iso.before
t/obs/ProjectName/print_rsync_repo.before
t/obs/ProjectName/print_openqa.before
8. Add to a new git commit the xml file and t/obs/ProjectName folder
git checkout -b add_projectname
git add xml/obs/ProjectName.xml t/obs/ProjectName
git commit -m 'Add ProjectName'
git push origin add_projectname
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
python3 script/scriptgen.pl Leap:15.2:ToTest
```

3. Call rsync.sh to start the synchronization:

```
bash script/rsync.sh Leap:15.2:ToTest
```

## License

This project is licensed under the MIT license, see LICENSE file for details.
