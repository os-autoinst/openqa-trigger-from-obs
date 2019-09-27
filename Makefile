
# projects_opensuse := $(shell echo openSUSE:Leap:15.2:Staging:{A..D})

openSUSE%: FORCE
	mkdir -p $@ && python3 script/scriptgen.py $@

.PONY: FORCE
FORCE:

test:
	(cd t && bash run.sh)

test_regen_all:
	(bash t/regen_all.sh t/* )

test_update_before_files: test_regen_all
	( cd t && bash test_before_after_diff.sh --update-before * )

