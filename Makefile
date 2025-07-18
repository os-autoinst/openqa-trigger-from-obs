.PHONY: help
help:
	@echo Call one of the available targets:
	@sed -n 's/\(^[^.#[:space:]A-Z]*\):.*$$/\1/p' Makefile | uniq

# projects_opensuse := $(shell echo openSUSE:Leap:15.2:Staging:{A..D})

openSUSE%: FORCE
	mkdir -p $@ && python3 script/scriptgen.py $@

.PHONY: FORCE
FORCE:

install_apparmor:
	install -d -m 755 "$(DESTDIR)"/etc/apparmor.d
	install -d -m 755 "$(DESTDIR)"/etc/apparmor.d/local
	install -m 644 profiles/apparmor.d/opt.openqa-trigger-from-obs.script.rsync.sh "$(DESTDIR)"/etc/apparmor.d/
	install -m 644 profiles/apparmor.d/local/opt.openqa-trigger-from-obs.script.rsync.sh "$(DESTDIR)"/etc/apparmor.d/local/
	install -m 644 profiles/apparmor.d/local/usr.share.openqa.script.openqa "$(DESTDIR)"/etc/apparmor.d/local/

update_files.lst:
	(cd t && bash update_read_files.sh *bs/*)

revert_update_files.lst:
	git checkout -- t/*bs/*/*.lst
	git checkout -- t/*bs/*/*/*.lst

test:
	(cd t && bash run.sh)

test_docker:
	(cd t && bash run_docker.sh)

test_regen_all:
	(bash t/regen_all.sh)

test_update_before_files: test_regen_all
	(cd t && bash test_before_after_diff.sh --update-before *bs/*)

test_python_style:
	black --check --fast --diff script/scriptgen.py 
