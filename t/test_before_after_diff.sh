set -e
scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

update_before=0

errs=0

for d in "$@" ; do
	[ "$d" != "--update-before" ] || update_before=1
	[ -d "$d" ] || continue
	d=$(basename $d)
	if [ $update_before == 1 ] ; then 
		for sh in {print_rsync_iso,print_rsync_repo,print_openqa}; do
			bash $d/${sh}.sh > $d/$sh.before
		done
	else 
		for sh in {print_rsync_iso,print_rsync_repo,print_openqa}; do
			bash $d/${sh}.sh > $d/$sh.after
			diff -u $d/$sh.before $d/$sh.after > $d/$sh.diff || echo "FAIL $d $sh : $(cat $d/$sh.diff)"  $((++errs))
		done
	fi
done

(exit $errs)	
