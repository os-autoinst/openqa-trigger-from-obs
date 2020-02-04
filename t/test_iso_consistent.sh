set -e
scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

errs=0

for dir in "$@" ; do
    # check if functions are implemented
    [ -e "$dir"/print_rsync_iso.sh ] || continue
    [ -e "$dir"/print_openqa.sh ] || continue

    # exception
    [ "$dir" != SUSE:SLE-15-SP2:GA:TEST/migration/ ] || continue

    # Make sure that destination iso in print_rsync_iso.sh output
    # exactly matches ISO value in print_openqa.sh

    # this must capture all destination iso filenames
    known_destination_isos="$(bash $dir/print_rsync_iso.sh | grep -oE '[^/]+\.(iso|appx|raw.(x|g)z|qcow2)$')" || :
    if [ -z "$known_destination_isos" ] ; then
        [ "(bash $dir/print_openqa.sh | wc -l)" -gt 1 ] || { >&2 echo "SKIP $dir" && continue; }
        # if openqa request has HDD_URL, then skip this test
        ! (bash $dir/print_openqa.sh | grep -q "HDD_URL_1") || { >&2 echo "SKIP $dir" && continue; }

        >&2 echo "FAIL $dir: Cannot parse destination ISO - is print_rsync_iso.sh correct?"
               : $((++errs))
        continue 2;
    fi
    regex='ISO.*=(.*\.iso)|ASSET[^(SHA)]*=(.*\.appx)|HDD.*=(.*\.(raw.(x|g)z|qcow2))'
    checked=0

    while read -r line; do
        if [[ "$line" =~ $regex ]]; then
            if [ ! "$line" != GM-DVD1 ]; then # exception as it uses fixed iso which is not needed to be synced
                  echo "$known_destination_isos" | grep -q "${BASH_REMATCH[1]}$" || { >&2 echo "FAIL $dir: ISO file wasnt found in print_rsync_iso output {${BASH_REMATCH[1]}}"; : $((++errs)); continue 2; }
            fi
            checked=1
        fi
    done < <(bash $dir/print_openqa.sh | grep -E '\b(ISO|ASSET|HDD)[^(SHA)]*=')

    [ "$checked" == 1 ] || { >&2 echo "FAIL $dir: No ISO found in openqa request - is something wrong?"; : $((++errs)); continue; }
    >&2 echo "PASS $dir"
done

(exit $errs)
