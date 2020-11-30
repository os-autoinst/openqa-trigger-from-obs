set -e
scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

errs=0

for dir in "$@" ; do
	# check if functions are implemented
	[ -e "$dir"/print_rsync_repo.sh ] || continue
	[ -e "$dir"/print_openqa.sh ] || continue
	[ "$(bash $dir/print_openqa.sh | wc -l)" -gt 1 ] || { >&2 echo "SKIP $dir" && continue; }

    # repo_from_iso is a special case when iso is extracted as repo
    repos_from_iso="$(bash "$dir"/print_rsync_iso.sh | grep bsdtar | grep -oE '[^ /]+$')" || :

	lines=$(bash "$dir"/print_rsync_repo.sh | grep -v '^#' | grep -v 'set -e' | grep -v '^[[:space:]]*$' | wc -l)
    [ "$lines$repos_from_iso" != "0" ] || { >&2 echo "SKIP $dir"; continue; }

	# Make sure that destination repo in print_rsync_repo.sh output
	# exactly matches one of REPO values in print_openqa.sh

	# this must capture all destination file filenames
	known_destination_repos="$(bash $dir/print_rsync_repo.sh | grep -oE '[^/]+(-Media.?(.license)?/?|-(Snapshot|Build)[0-9]+(.[0-9]+)?)(-debuginfo|-source)?$')"  || :
    [ -n "$known_destination_repos" ] || [ -z  "$repos_from_iso" ] || { >&2 echo 'print_openqa.sh must have {REPO_0='$(echo "$repos_from_iso"| head -n 1)'}'; : $((++errs)); continue; }
    [ -n "$known_destination_repos" ] || { >&2 echo "Cannot parse destination REPOs - is print_rsync_repo.sh correct?"; : $((++errs)); continue; }

	# remove trailing /
	known_destination_repos=$(echo "$known_destination_repos" | grep -o '.*[^/]')

	regex='REPO_[0-9]+=([^[:space:]]+)'
	checked=0

    isos_post_repos="$(bash $dir/print_openqa.sh | grep REPO_ )"

	while read -r line; do
	    if [[ "$line" =~ $regex ]]; then
            problem_repo="${BASH_REMATCH[1]}"
            line="${line%% *}"
            line="${line##*=}"
            if ! echo "$known_destination_repos" | grep -q "$problem_repo"; then
                [[ "$problem_repo" =~ GM-DVD1 ]] || \
                echo "$repos_from_iso" | grep -q "$line" || \
                ( [[ $dir =~ Update.*RT ]] && [[ ! "$problem_repo" =~ RT  ]] ) || \
                { >&2 echo "Destination REPO file wasnt found in print_rsync_repo output {$problem_repo}   {$known_destination_repos}"; : $((++errs)); continue 2; }
            fi
            checked=1
	    fi
	done < <(echo "$isos_post_repos" | grep -v 'REPO_5=' | grep -v PACKAGES )

	[ "$checked" == 1 ] || { >&2 echo "No REPO found in openqa request - is something wrong?";  : $((++errs)); continue; }

    for created_repo in $repos_from_iso $known_destination_repos; do
        [[ ! $created_repo =~ CURRENT ]] || continue
        created_repo=${created_repo##*=}
        echo "$isos_post_repos" | grep -q -E "\b$created_repo\b" || { >&2 echo "Synced REPO {$created_repo} wasnt found in print_openqa output {$isos_post_repos}"; : $((++errs)); continue 2; }
    done

	>&2 echo "PASS $dir"
done

(exit $errs)
