# thisdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
thisdir=$(dirname "${BASH_SOURCE[0]}")

cd "${thisdir}"/..

set -e

for dir in "${thisdir}"/*; do
    [ -d "$dir" ] || continue
    [ "$dir" != t/docker ] || continue

    # this checks whether files must be generated
    dir1="$thisdir/../$(basename $dir)"
    if [ ! -d "$dir1" ] || [ ! -f "$dir1"/print_rsync_iso.sh ] || [[ "$(head -n1 $dir1/print_rsync_iso.sh)" =~ GENERATED  ]]; then
        python3 script/scriptgen.py $dir
    else
        cp "$dir1"/print_* "$dir"
    fi

done
