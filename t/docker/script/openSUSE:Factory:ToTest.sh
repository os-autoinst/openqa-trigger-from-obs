#!lib/test-in-container-systemd.sh

set -ex
source lib/common.sh

mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Tumbleweed-NET-x86_64-Snapshot200210-Media.iso
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Tumbleweed-NET-x86_64-Snapshot200210-Media.iso.sha256
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-dvd5-dvd-x86_64
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Tumbleweed-DVD-x86_64-Snapshot200209-Media.iso
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Tumbleweed-DVD-x86_64-Snapshot200209-Media.iso.sha256
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-x86_64-Media1
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-x86_64-Media1/repo
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-x86_64-Media2/x86_64
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-x86_64-Media2/x86_64/mraa-debug
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-x86_64-Media2/x86_64/other
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-x86_64-Media3/src
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-x86_64-Media3/src/coreutils
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-x86_64-Media3/src/other
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Addon-NonOss-FTP-x86_64-Media1
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Addon-NonOss-FTP-x86_64-Media1/repo
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Addon-NonOss-FTP-x86_64-Media2
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Addon-NonOss-FTP-x86_64-Media2/debugfile
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Addon-NonOss-FTP-x86_64-Media3
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Addon-NonOss-FTP-x86_64-Media3/sourcefile

# create just empty files as at this point we are not interested about proper binaries
chown -R "$dbuser" /mockOBS
 
su $dbuser -c 'set -ex
cd /opt/openqa-trigger-from-obs
mkdir -p openSUSE:Factory:ToTest
python3 script/scriptgen.py openSUSE:Factory:ToTest
[ ! -e openSUSE:Factory:ToTest/base/.run_last ] || rm openSUSE:Factory:ToTest/base/.run_last
echo geekotest > rsync.secret
chmod 600 rsync.secret'

echo '127.0.0.1 obspublish' >> /etc/hosts
systemctl enable --now postgresql
systemctl enable --now rsyncd

runs_before="$(ls -lda /opt/openqa-trigger-from-obs/openSUSE:Factory:ToTest/base/.run_*/ 2>/dev/null | wc -l)"

out=$(su "$dbuser" -c 'bash -x /opt/openqa-trigger-from-obs/script/rsync.sh openSUSE:Factory:ToTest' 2>&1) || :

runs_after="$(ls -lda /opt/openqa-trigger-from-obs/openSUSE:Factory:ToTest/base/.run_*/ 2>/dev/null | wc -l)"

# no runs should happend because inconsistent snapshots
test "$runs_before" -eq "$runs_after"
[[ "$out" == *Conflicting* ]]

echo PASS ${BASH_SOURCE[0]} $@ $METHOD
