#!lib/test-in-container-systemd.sh

set -ex
source lib/common.sh

mkdir -p /mockOBS/openSUSE:Leap:15.2:Staging:A/images/x86_64/product/
# create just empty files as at this point we are not interested about proper binaries
touch /mockOBS/openSUSE\:Leap\:15.2\:Staging\:A/images/x86_64/product/openSUSE-Leap-15.2-DVD-x86_64-Build248.1-Media.iso
touch /mockOBS/openSUSE\:Leap\:15.2\:Staging\:A/images/x86_64/product/openSUSE-Leap-15.2-DVD-x86_64-Build248.1-Media.iso.sha256
chown -R "$dbuser" /mockOBS

prepare_project openSUSE:Leap:15.2:Staging:A -stage

set -x
# make sure run did happen
test -f /var/lib/openqa/factory/iso/openSUSE-Leap-15.2-Staging:A-Staging-DVD-x86_64-Build248.1-Media.iso
test -f /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:Staging:A/.run_last/openqa.cmd.log
grep -q 'scheduled_product_id => 1' /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:Staging:A/.run_last/openqa.cmd.log || cat /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:Staging:A/.run_last/*.cmd.log

grep -q 'scheduled_product_id => 1' /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:Staging:A/.run_last/openqa.cmd.log

[ "$METHOD" != rest ] || {
    state=$(echo "select state from minion_jobs where task='obs_rsync_run';" | su postgres -c "psql -t $dbname")
    test "$(echo $state)" == finished

    # run second time, make sure all is set
    echo "delete from minion_jobs where task='obs_rsync_run';" | su postgres -c "psql -t $dbname"

    mv /mockOBS/openSUSE\:Leap\:15.2\:Staging\:A/images/x86_64/product/openSUSE-Leap-15.2-DVD-x86_64-Build{248.1,248.2}-Media.iso
    mv /mockOBS/openSUSE\:Leap\:15.2\:Staging\:A/images/x86_64/product/openSUSE-Leap-15.2-DVD-x86_64-Build{248.1,248.2}-Media.iso.sha256

    # this shouldn't fail and files.iso must be different from .run_last
    su $dbuser -c 'bash /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:Staging:A/read_files.sh'
    (
    set +e
    diff -q /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:Staging:A/files_iso.lst /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:Staging:A/.run_last/files_iso.lst
    test $? -eq 1
    )

    openqa-client --host localhost /api/v1/obs_rsync/openSUSE:Leap:15.2:Staging:A/runs put || :
    sleep 10

    test -f /var/lib/openqa/factory/iso/openSUSE-Leap-15.2-Staging:A-Staging-DVD-x86_64-Build248.2-Media.iso
    test -f /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:Staging:A/.run_last/openqa.cmd.log
    grep -q 'scheduled_product_id => 2' /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:Staging:A/.run_last/openqa.cmd.log

    state=$(echo "select state from minion_jobs where task='obs_rsync_run';" | su postgres -c "psql -t $dbname")
    test "$(echo $state)" == finished

    test "$(ls -1q /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:Staging:A/.run* | wc -l)" -ge 3
}
echo PASS ${BASH_SOURCE[0]} $TESTCASE $METHOD
