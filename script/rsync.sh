#!/bin/bash

set -e
environ=$1

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR/.."

[ -d "$environ" ] || { >&2 echo "No directory found: {$environ}"; exit 1; }

[ -e "$environ/read_files.sh" ] || { >&2 echo "No file found: {$environ/read_files.sh}"; exit 1; }
if [ ! -e "$environ/print_rsync_iso.sh" ] && [ ! -e "$environ/print_rsync_repo.sh" ]; then
   >&2 echo "Neither of files found: {$environ/print_rsync_iso.sh} nor {$environ/print_rsync_repo.sh}"
   exit 1
fi

[ -e "$environ/print_openqa.sh" ] || { >&2 echo "No file found: {$environ/print_openqa.sh}"; exit 1; }

# if lock file exists
if [ -e "$environ/rsync.lock" ] && kill -0 $(cat "$environ/rsync.lock"); then
    >&2 echo "Lock file already exists: {$environ/rsync.lock}"
    (exit 1)
fi

trap "rm -f $environ/rsync.lock; exit" INT TERM EXIT
echo $$ > $environ/rsync.lock

[ ! -f rsync.secret ] || export RSYNC_PASSWORD="$(cat rsync.secret)"
bash -e "$environ/read_files.sh"

[ ! -e $environ/.run_last ] || [ ! -z "$(diff --brief $environ $environ/.run_last | grep '.lst')" ] || { >&2 echo "No changes found since last run, skipping {$environ}"; exit 0; }

logdir=$environ/.run_$(date +%y%m%d_%H%M%S)
mkdir $logdir

[ ! -e "$environ/print_rsync_iso.sh" ] || bash -e "$environ/print_rsync_iso.sh" > $logdir/rsync_iso.cmd 2> >(tee $logdir/generate_rsync_iso.err)

[ ! -e "$environ/print_rsync_repo.sh" ] || bash -e "$environ/print_rsync_repo.sh" > $logdir/rsync_repo.cmd 2> >(tee $logdir/generate_rsync_repo.err)

# store state of files for eventual troubleshooting and avoid indefinite openqa retry
cp $environ/*.lst $logdir/
cp $environ/*.sh $logdir/

ln -fs -T "$(pwd)/$logdir" $environ/.run_last

[ ! -e "$environ/print_openqa.sh" ] || bash -e "$environ/print_openqa.sh" 2>$logdir/generate_openqa.err > $logdir/openqa.cmd

for f in {rsync_iso.cmd,rsync_repo.cmd,openqa.cmd}; do
  bash -x "$environ/.run_last/$f" > "$logdir/$f".log 2>&1
done
