#!lib/test-in-container-systemd.sh

set -ex
source lib/common.sh

mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Tumbleweed-NET-x86_64-Snapshot20200210-Media.iso
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Tumbleweed-NET-x86_64-Snapshot20200210-Media.iso.sha256
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-dvd5-dvd-x86_64
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Tumbleweed-DVD-x86_64-Snapshot20200209-Media.iso
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Tumbleweed-DVD-x86_64-Snapshot20200209-Media.iso.sha256
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-x86_64-Media1/media.1
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-x86_64-Media1/repo
echo Snapshot20200209 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-x86_64-Media1/media.1/products
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-x86_64-Media2/x86_64
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-x86_64-Media2/x86_64/mraa-debug
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-x86_64-Media2/x86_64/other
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-x86_64-Media3/src
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-x86_64-Media3/src/coreutils
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-x86_64-Media3/src/other
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Addon-NonOss-FTP-x86_64-Media1/media.1
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Addon-NonOss-FTP-x86_64-Media1/repo
echo Snapshot20200209 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Addon-NonOss-FTP-x86_64-Media1/media.1/media
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Addon-NonOss-FTP-x86_64-Media2
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Addon-NonOss-FTP-x86_64-Media2/debugfile
mkdir -p /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Addon-NonOss-FTP-x86_64-Media3
echo 1 > /mockOBS/openSUSE\:Factory\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Addon-NonOss-FTP-x86_64-Media3/sourcefile

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
