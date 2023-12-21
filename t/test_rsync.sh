#!/bin/bash
set -eo pipefail
scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

errs=0

function rsync() {
    [ $successful -eq 1 ] && return 0
    echo "[sender] change_dir $3 (in repos) failed: No such file or directory (2)" >&2
    echo "rsync error: some files/attrs were not transferred" >&2
    echo "read_files.sh failed for  in $dir" >&2
    return 256
}
function curl() {
    return 0
}
export -f rsync curl

successful=0
export successful

for dir in "$@"; do
    for expected in $(seq 0 1); do
        successful=$expected
        out=$(bash -e "$@/read_files.sh" $dir)
        [ $? -eq 0 ] || echo "FAIL $dir : $out" $((++errs))
    done
done
(exit $errs)
