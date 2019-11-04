thisdir=$(dirname "${BASH_SOURCE[0]}")

cd "${thisdir}"/..

set -e

for dir in "${thisdir}"/*; do
    [ -d "$dir" ] || continue
    [ "$dir" != t/docker ] || continue
    python3 script/scriptgen.py $dir
done
