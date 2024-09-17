#!lib/test-in-container-systemd.sh

set -ex
source lib/common.sh

# mock OBS backend folder
mkdir -p /mockOBS/systemsmanagement:Agama:Devel/images/x86_64/agama-installer:openSUSE/
mkdir -p /mockOBS/systemsmanagement:Agama:Devel/images/s390x/agama-installer:openSUSE/
# create just empty files as at this point we are not interested about proper binaries
touch /mockOBS/systemsmanagement:Agama:Devel/images/x86_64/agama-installer:openSUSE/agama-installer.x86_64-9.0.0-openSUSE-Build19.23.iso
touch /mockOBS/systemsmanagement:Agama:Devel/images/x86_64/agama-installer:openSUSE/agama-installer.x86_64-9.0.0-openSUSE-Build19.23.iso.sha256
touch /mockOBS/systemsmanagement:Agama:Devel/images/s390x/agama-installer:openSUSE/agama-installer.s390x-9.0.0-openSUSE-Build19.23.iso
touch /mockOBS/systemsmanagement:Agama:Devel/images/s390x/agama-installer:openSUSE/agama-installer.s390x-9.0.0-openSUSE-Build19.23.iso.sha256

chown -R "$dbuser" /mockOBS

prepare_project systemsmanagement:Agama:Devel other

set -x

# make sure run did happen
test -f /var/lib/openqa/factory/iso/agama-installer.s390x-9.0.0-openSUSE-Build19.23.iso
test -f /var/lib/openqa/factory/repo/agama-installer.s390x-9.0.0-openSUSE-Build19.23.iso
test -f /opt/openqa-trigger-from-obs/systemsmanagement:Agama:Devel/base/.run_last/openqa.cmd.log
test -f /opt/openqa-trigger-from-obs/systemsmanagement:Agama:Devel/s390x/.run_last/openqa.cmd.log
grep -q '"scheduled_product_id":1' /opt/openqa-trigger-from-obs/systemsmanagement:Agama:Devel/base/.run_last/openqa.cmd.log

[ "$METHOD" != rest ] || {
    state=$(echo "select state from minion_jobs where task='obs_rsync_run';" | su postgres -c "psql -t $dbname")
    test "$(echo $state)" == finished
}

echo PASS ${BASH_SOURCE[0]} $TESTCASE $METHOD
