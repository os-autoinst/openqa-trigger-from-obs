#!lib/test-in-container-systemd.sh

set -ex
source lib/common.sh

# mock OBS backend folder
mkdir -p /mockOBS/Virtualization:WSL/openSUSE_Tumbleweed/x86_64/wsl-appx/
mkdir -p /mockOBS/Virtualization:WSL/openSUSE_Leap_15.2/x86_64/wsl-appx/
# create just empty files as at this point we are not interested about proper binaries
touch /mockOBS/Virtualization:WSL/openSUSE_Tumbleweed/x86_64/wsl-appx/openSUSE-Tumbleweed-x64-Build20191128.7.9.appx
touch /mockOBS/Virtualization:WSL/openSUSE_Tumbleweed/x86_64/wsl-appx/openSUSE-Tumbleweed-x64-Build20191128.7.9.appx.sha256
touch /mockOBS/Virtualization:WSL/openSUSE_Leap_15.2/x86_64/wsl-appx/openSUSE-x64-Build20191128.7.9.appx
touch /mockOBS/Virtualization:WSL/openSUSE_Leap_15.2/x86_64/wsl-appx/openSUSE-x64-Build20191128.7.9.appx.sha256
chown -R "$dbuser" /mockOBS

prepare_project Virtualization:WSL -other

# make sure run did happen
test -f /var/lib/openqa/factory/other/openSUSE-Tumbleweed-x64-Build20191128.7.9.appx
test -f /opt/openqa-trigger-from-obs/Virtualization:WSL/Tumbleweed/.run_last/openqa.cmd.log
grep -q 'scheduled_product_id => 1' /opt/openqa-trigger-from-obs/Virtualization:WSL/{Tumbleweed,Leap_15.2}/.run_last/openqa.cmd.log

[ "$METHOD" != rest ] || {
    state=$(echo "select state from minion_jobs where task='obs_rsync_run';" | su postgres -c "psql -t $dbname")
    test "$(echo $state)" == finished
}
echo PASS ${BASH_SOURCE[0]} $TESTCASE $METHOD
