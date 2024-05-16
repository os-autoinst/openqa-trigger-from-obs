#!lib/test-in-container-systemd.sh

set -ex
source lib/common.sh

# mock OBS backend folder
mkdir -p /mockOBS/openSUSE:Leap:15.4:WSL/images/x86_64/kiwi-images-wsl/
# create just empty files as at this point we are not interested about proper binaries
touch /mockOBS/openSUSE:Leap:15.4:WSL/images/x86_64/kiwi-images-wsl/openSUSE-Leap-15.4-WSL.x86_64-154.1.3.0-Build1.3.appx
touch /mockOBS/openSUSE:Leap:15.4:WSL/images/x86_64/kiwi-images-wsl/openSUSE-Leap-15.4-WSL.x86_64-154.1.3.0-Build1.3.appx.sha256
chown -R "$dbuser" /mockOBS

prepare_project openSUSE:Leap:15.4:WSL 

set -x

# make sure run did happen
test -f /var/lib/openqa/factory/other/openSUSE-Leap-15.4-WSL.x86_64-154.1.3.0-Build1.3.appx
test -f /opt/openqa-trigger-from-obs/openSUSE:Leap:15.4:WSL/.run_last/openqa.cmd.log
grep -q '"scheduled_product_id":1' /opt/openqa-trigger-from-obs/openSUSE:Leap:15.4:WSL/.run_last/openqa.cmd.log

[ "$METHOD" != rest ] || {
    state=$(echo "select state from minion_jobs where task='obs_rsync_run';" | su postgres -c "psql -t $dbname")
    test "$(echo $state)" == finished
}
echo PASS ${BASH_SOURCE[0]} $TESTCASE $METHOD
