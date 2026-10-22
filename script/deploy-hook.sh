#!/bin/bash
# Regenerate scripts and remove stale dirs after the repository was updated:
# runs script/deploy_on_pull.py, then script/cleanup_on_deploy.py.
#
#   as git post-merge hook (make install_hooks): runs after every `git pull`
#   script/deploy-hook.sh tick: from openqa-trigger-from-obs-deploy.service
#   --force: regenerate all project dirs (deploy_on_pull.py --all)
#
# In hook mode it always exits 0, because git ignores the hook's exit code.
set -u

log() { echo "deploy-hook: $*" >&2; }

mode=hook
deploy_args=()
while [ $# -gt 0 ]; do
    case "$1" in
        --help|-h) echo "Usage: $0 [--force|-f] [hook|tick]" >&2; exit 0 ;;
        # regenerate all project dirs and create the missing enabled ones
        --force|-f) deploy_args=(--all) ;;
        hook|tick) mode="$1" ;;
        # post-merge: 0 after a merge, 1 after `git merge --squash` (nothing committed)
        0) ;;
        1) exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
    shift
done
[ ${#deploy_args[@]} = 0 ] || log "forcing regeneration of all projects"

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

python3 script/deploy_on_pull.py "${deploy_args[@]}"
deploy_rc=$?
python3 script/cleanup_on_deploy.py
cleanup_rc=$?
[ "$deploy_rc" = 0 ] && [ "$cleanup_rc" = 0 ] || log "deploy_on_pull rc=$deploy_rc cleanup_on_deploy rc=$cleanup_rc"

[ "$deploy_rc" = 0 ] && [ "$cleanup_rc" = 0 ]
finish $?
