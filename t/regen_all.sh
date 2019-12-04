thisdir=$(dirname "${BASH_SOURCE[0]}")

cd "${thisdir}"/..

set -e

for dir in "${thisdir}"/*; do
    [ -d "$dir" ] || continue
    [ "$dir" != t/docker ] || continue

    subdirs=""
    for subdir in $dir/*/; do
        [ -d "$subdir" ] || break
        subdirs=1
        python3 script/scriptgen.py $subdir
    done
    [ -z "$subdirs" ] || continue

    dir1="$thisdir/../$(basename $dir)"
    if [ ! -d "$dir1" ] || [ ! -f "$dir1"/print_rsync_iso.sh ] || [[ "$(head -n1 $dir1/print_rsync_iso.sh)" =~ GENERATED  ]]; then
        python3 script/scriptgen.py $dir
    else
        cp "$dir1"/print_* "$dir"
    fi

done
