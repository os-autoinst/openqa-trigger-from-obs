set -e
scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

errs=0

for dir in "$@" ; do
    [ -d "$dir" ] || continue
    [ "$dir" != docker ] || continue

    sudirs=""
    for subdir in $dir/*/; do
        # if no subdir - execute body only once
        [ -d "$subdir" ] || subdir=$dir

        d=$subdir
        bash $d/read_files.sh || : $((errs++))
        # if no subdir - execute body only once
        [ "$subdir" != "$dir" ] || break
    done
done

[ "$errs" == 0 ] || echo "FAIL ($errs)"
[ "$errs" != 0 ] || echo "PASS"

(exit $errs)
