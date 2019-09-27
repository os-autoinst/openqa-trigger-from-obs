set -e
scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

errs=0

for dir in "$@" ; do
	# check if functions are implemented
	[ -e "$dir"/print_rsync_repo.sh ] || continue
	[ -e "$dir"/print_openqa.sh ] || continue

	lines=$(grep -v '^#' "$dir"/print_rsync_repo.sh | grep -v 'set -e' | grep -v '^[[:space:]]*$' | wc -l)
       	[ "$lines" != "0" ] || { >&2 echo "SKIP $dir"; continue; }

	# Make sure that destination repo in print_rsync_repo.sh output
	# exactly matches one of REPO values in print_openqa.sh

	# this must capture all destination file filenames
	known_destination_repos="$(bash $dir/print_rsync_repo.sh | grep -oE '[^/]+(-Media.?(.license)?/?|-(Snapshot|Build)[0-9]+(.[0-9]+)?)(-debuginfo|-source)?$')" || { >&2 echo "Cannot parse destination REPOs - is print_rsync_repo.sh correct?"; : $((++errs)); continue; }

	# remove trailing /
	known_destination_repos=$(echo "$known_destination_repos" | grep -o '.*[^/]')

	regex='REPO_[^=]+=([^[:space:]]*)'
	checked=0

	while read -r line; do
	    if [[ "$line" =~ $regex ]]; then
	        echo "$known_destination_repos" | grep -q "${BASH_REMATCH[1]}\$" || { >&2 echo "Destination REPO file wasnt found in print_rsync_repo output {${BASH_REMATCH[1]}}   {$known_destination_repos}"; : $((++errs)); continue 2; }
		checked=1
	    fi
	done < <(bash $dir/print_openqa.sh | grep 'REPO_' | grep -v 'REPO_0' | grep -v PACKAGES )

	[ "$checked" == 1 ] || { >&2 echo "No REPO found in openqa request - is something wrong?";  : $((++errs)); continue; }
	>&2 echo "PASS $dir"
done

(exit $errs)
