#!lib/test-in-container-systemd.sh

set -ex
source lib/common.sh

mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Tumbleweed-NET-x86_64-Snapshot20200210-Media.iso
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Tumbleweed-NET-x86_64-Snapshot20200210-Media.iso.sha256
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-dvd5-dvd-x86_64
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Tumbleweed-DVD-x86_64-Snapshot20200209-Media.iso
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Tumbleweed-DVD-x86_64-Snapshot20200209-Media.iso.sha256
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/0openSUSE/openSUSE-20200209-x86_64/
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/0openSUSE/openSUSE-20200209-x86_64/repo
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/0openSUSE/openSUSE-20200209-x86_64-Debug/x86_64
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/0openSUSE/openSUSE-20200209-x86_64-Debug/x86_64/mraa-debug
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/0openSUSE/openSUSE-20200209-x86_64-Debug/x86_64/other
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/0openSUSE/openSUSE-20200209-x86_64-Source/src
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/0openSUSE/openSUSE-20200209-x86_64-Source/src/coreutils
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/0openSUSE/openSUSE-20200209-x86_64-Source/src/other
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/0NonFree/openSUSE-NonOss-20200209-x86_64
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/0NonFree/openSUSE-NonOss-20200209-x86_64/repo

mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/appliances/x86_64/vagrantlibvirt
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/appliances/x86_64/vagrantlibvirt/Tumbleweed.x86_64-1.0-libvirt-Snapshot20200209.vagrant.libvirt.box
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/appliances/x86_64/vagrantvirtualbox
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/appliances/x86_64/vagrantvirtualbox/Tumbleweed.x86_64-1.0-virtualbox-Snapshot20200209.vagrant.virtualbox.box

chown -R "$dbuser" /mockOBS
(
cd /opt/openqa-trigger-from-obs
mkdir -p openSUSE:Factory:ToTest
chown geekotest openSUSE:Factory:ToTest
echo geekotest > rsync.secret
chmod 600 rsync.secret
chown geekotest rsync.secret
)

su $dbuser -c 'set -ex
cd /opt/openqa-trigger-from-obs
python3 script/scriptgen.py openSUSE:Factory:ToTest
[ ! -e openSUSE:Factory:ToTest/base/.run_last ] || rm openSUSE:Factory:ToTest/base/.run_last'

echo '127.0.0.1 obspublish' >> /etc/hosts
systemctl enable --now postgresql
systemctl restart rsyncd
sleep 1 # is it a bug that rsyncd needs sleep to work properly?

runs_before="$(ls -lda /opt/openqa-trigger-from-obs/openSUSE:Factory:ToTest/base/.run_*/ 2>/dev/null | wc -l)"

out=$(su "$dbuser" -c 'bash -x /opt/openqa-trigger-from-obs/script/rsync.sh openSUSE:Factory:ToTest' 2>&1) || :

runs_after="$(ls -lda /opt/openqa-trigger-from-obs/openSUSE:Factory:ToTest/base/.run_*/ 2>/dev/null | wc -l)"

# no runs should happend because inconsistent snapshots
test "$runs_before" -eq "$runs_after"
[[ "$out" == *Conflicting* ]]

echo PASS ${BASH_SOURCE[0]} $TESTCASE $METHOD
