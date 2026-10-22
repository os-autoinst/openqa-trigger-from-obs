.PHONY: help
help:
	@echo Call one of the available targets:
	@sed -n 's/\(^[^.#[:space:]A-Z]*\):.*$$/\1/p' Makefile | uniq

# projects_opensuse := $(shell echo openSUSE:Leap:15.2:Staging:{A..D})

RSYNC_USER ?=
RSYNC_USER_FLAG :=

ifneq ($(RSYNC_USER),)
    RSYNC_USER_FLAG := --rsync-user=$(RSYNC_USER)
endif

openSUSE%: FORCE
	@if [ -n "$(RSYNC_USER)" ]; then \
		echo "Regenerating all test scripts using $(RSYNC_USER)"; \
	fi
	mkdir -p $@ && python3 script/scriptgen.py $(RSYNC_USER_ARG) $@

.PHONY: FORCE
FORCE:

# Run script/deploy-hook.sh after every `git pull`
.PHONY: install_hooks
install_hooks:
	@hooks="$$(git rev-parse --git-path hooks)" && target="$$(pwd)/script/deploy-hook.sh" && \
	if [ -n "$$(git config core.hooksPath)" ]; then \
		echo "core.hooksPath is set, link $$target as post-merge hook there by hand" >&2; exit 1; \
	elif [ "$$(readlink -f "$$hooks/post-merge")" = "$$target" ]; then \
		echo "$$hooks/post-merge is already installed"; \
	elif [ -e "$$hooks/post-merge" ] || [ -L "$$hooks/post-merge" ]; then \
		echo "$$hooks/post-merge exists, refusing to overwrite it" >&2; exit 1; \
	else \
		mkdir -p "$$hooks" && ln -s "$$target" "$$hooks/post-merge" && echo "installed $$hooks/post-merge"; \
	fi

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
	@if [ -n "$(RSYNC_USER)" ]; then \
		echo "Regenerating all test scripts using $(RSYNC_USER)"; \
	fi
	(bash t/regen_all.sh $(RSYNC_USER_FLAG))

test_update_before_files: test_regen_all
	(cd t && bash test_before_after_diff.sh --update-before *bs/*)

# xml/ibs is a symlink into the plugin repository, checked only when present
XML_DIRS ?= xml/obs xml/abs $(shell test -d xml/ibs && echo xml/ibs)

.PHONY: validate_xml
validate_xml:
	find -H $(XML_DIRS) -name '*.xml' -exec xmllint --noout --quiet --relaxng xml/openQA.rng {} +
	python3 script/validate_xml.py $(XML_DIRS)

.PHONY: all
all: validate_xml test_update_before_files test test_python_style unit_tests

# Override to use uv, e.g. PYTHON_RUN="uv run"
PYTHON_RUN ?=

.PHONY: ruff_check ruff_format ty_check test_python_style
test_python_style: ruff_check ruff_format ty_check test_python_style
.PHONY: unit_tests
unit_tests:
	$(PYTHON_RUN) pytest -v

ruff_check:
	$(PYTHON_RUN) ruff check $(ARGS)

ruff_format:
	$(PYTHON_RUN) ruff format --check $(ARGS)

ty_check:
	$(PYTHON_RUN) ty check $(ARGS)
