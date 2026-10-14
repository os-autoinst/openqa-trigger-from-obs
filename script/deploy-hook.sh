#!/bin/bash
# Regenerate scripts and remove stale dirs after the repository was updated:
# runs script/deploy_on_pull.py, then script/cleanup_on_deploy.py.
#
#   as git post-merge hook (make install_hooks): runs after every `git pull`
#   script/deploy-hook.sh tick: from openqa-trigger-from-obs-deploy.service
#
# In hook mode it always exits 0, because git ignores the hook's exit code.
set -u

mode=hook
case "${1:-}" in
    tick) mode=tick ;;
    # post-merge after `git merge --squash`: nothing was committed
    1) exit 0 ;;
esac

log() { echo "deploy-hook: $*" >&2; }

finish() {
    [ "$mode" = tick ] || exit 0
    exit "$1"
}

root="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)" || finish 1
cd "$root" || finish 1
# git exports these into hooks; they would point the scripts' git calls
# at the wrong place
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_OBJECT_DIRECTORY

if [ "$(id -u)" != "$(stat -c %u .)" ]; then
    log "not run as the owner of $root, nothing done; run it as $(stat -c %U .)"
    finish 1
fi

exec 9>.deploy.lock
if ! flock -n 9; then
    log "another deploy is running, nothing done"
    finish 0
fi

python3 script/deploy_on_pull.py
deploy_rc=$?
python3 script/cleanup_on_deploy.py
cleanup_rc=$?
[ "$deploy_rc" = 0 ] && [ "$cleanup_rc" = 0 ] || log "deploy_on_pull rc=$deploy_rc cleanup_on_deploy rc=$cleanup_rc"

[ "$deploy_rc" = 0 ] && [ "$cleanup_rc" = 0 ]
finish $?
