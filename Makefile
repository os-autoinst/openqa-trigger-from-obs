
# projects_opensuse := $(shell echo openSUSE:Leap:15.2:Staging:{A..D})

openSUSE%: FORCE
	mkdir -p $@ && python3 script/scriptgen.py $@

.PONY: FORCE
FORCE:

install_apparmor:
	install -d -m 755 "$(DESTDIR)"/etc/apparmor.d
	install -d -m 755 "$(DESTDIR)"/etc/apparmor.d/local
	install -m 644 profiles/apparmor.d/opt.openqa-trigger-from-obs.script.rsync.sh "$(DESTDIR)"/etc/apparmor.d/
	install -m 644 profiles/apparmor.d/local/opt.openqa-trigger-from-obs.script.rsync.sh "$(DESTDIR)"/etc/apparmor.d/local/
	install -m 644 profiles/apparmor.d/local/usr.share.openqa.script.openqa "$(DESTDIR)"/etc/apparmor.d/local/

test:
	(cd t && bash run.sh)

test_regen_all:
	(bash t/regen_all.sh t/* )

test_update_before_files: test_regen_all
	( cd t && bash test_before_after_diff.sh --update-before * )

