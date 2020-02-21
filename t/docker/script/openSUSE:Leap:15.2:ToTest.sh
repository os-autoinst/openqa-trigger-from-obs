#!lib/test-in-container-systemd.sh

set -ex
source lib/common.sh

# mock OBS backend folder
mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Leap-15.2-NET-x86_64-Build519.3-Media.iso
echo "-----BEGIN PGP SIGNED MESSAGE-----" > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Leap-15.2-NET-x86_64-Build519.3-Media.iso.sha256
echo "Hash: SHA256"                      >> /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Leap-15.2-NET-x86_64-Build519.3-Media.iso.sha256
echo ""                                  >> /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Leap-15.2-NET-x86_64-Build519.3-Media.iso.sha256
echo 1 | sha256sum                       >> /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Leap-15.2-NET-x86_64-Build519.3-Media.iso.sha256
mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-dvd5-dvd-x86_64
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Leap-15.2-DVD-x86_64-Build519.3-Media.iso
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Leap-15.2-DVD-x86_64-Build519.3-Media.iso.sha256
mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-15.2-x86_64-Media1
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-15.2-x86_64-Media1/repo
mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-15.2-x86_64-Media2/x86_64
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-15.2-x86_64-Media2/x86_64/mraa-debug
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-15.2-x86_64-Media2/x86_64/other
mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-15.2-x86_64-Media3/src
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-15.2-x86_64-Media3/src/coreutils
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-15.2-x86_64-Media3/src/other
mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Leap-15.2-Addon-NonOss-FTP-x86_64-Media1
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Leap-15.2-Addon-NonOss-FTP-x86_64-Media1/repo
mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Leap-15.2-Addon-NonOss-FTP-x86_64-Media2
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Leap-15.2-Addon-NonOss-FTP-x86_64-Media2/debugfile
mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Leap-15.2-Addon-NonOss-FTP-x86_64-Media3
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Leap-15.2-Addon-NonOss-FTP-x86_64-Media3/sourcefile

chown -R "$dbuser" /mockOBS

prepare_project openSUSE:Leap:15.2:ToTest

mkdir -p /var/lib/openqa/osc-plugin-factory/factory-package-news/
touch /var/lib/openqa/osc-plugin-factory/factory-package-news/factory-package-news.py
chmod +x /var/lib/openqa/osc-plugin-factory/factory-package-news/factory-package-news.py
/var/lib/openqa/osc-plugin-factory/factory-package-news/factory-package-news.py

set -x
# make sure run did happen
test -f /var/lib/openqa/factory/iso/openSUSE-Leap-15.2-DVD-x86_64-Build519.3-Media.iso
test -f /var/lib/openqa/factory/iso/openSUSE-Leap-15.2-NET-x86_64-Build519.3-Media.iso
test -d /var/lib/openqa/factory/repo/openSUSE-15.2-oss-i586-x86_64-Build519.3
test -d /var/lib/openqa/factory/repo/openSUSE-15.2-oss-i586-x86_64-Build519.3-source
test -f /var/lib/openqa/factory/repo/openSUSE-15.2-oss-i586-x86_64-Build519.3-source/src/coreutils
test ! -f /var/lib/openqa/factory/repo/openSUSE-15.2-oss-i586-x86_64-Build519.3-source/src/other
test -d /var/lib/openqa/factory/repo/openSUSE-15.2-oss-i586-x86_64-Build519.3-debuginfo
test -d /var/lib/openqa/factory/repo/openSUSE-15.2-oss-i586-x86_64-Build519.3-debuginfo/x86_64
test -f /var/lib/openqa/factory/repo/openSUSE-15.2-oss-i586-x86_64-Build519.3-debuginfo/x86_64/mraa-debug
test ! -f /var/lib/openqa/factory/repo/openSUSE-15.2-oss-i586-x86_64-Build519.3-debuginfo/x86_64/other
test -z "$(ls -lRa /var/lib/openqa/factory/repo/ | grep other)"
test -d /var/lib/openqa/factory/repo/openSUSE-15.2-non-oss-i586-x86_64-Build519.3
test ! -d /var/lib/openqa/factory/repo/openSUSE-15.2-non-oss-i586-x86_64-Build519.3-source
test ! -d /var/lib/openqa/factory/repo/openSUSE-15.2-non-oss-i586-x86_64-Build519.3-debuginfo

test -f /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:ToTest/.run_last/openqa.cmd.log
grep -q 'scheduled_product_id => 1' /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:ToTest/.run_last/openqa.cmd.log
grep -q 'CHECKSUM_ISO=4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865' /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:ToTest/.run_last/openqa.cmd.log

[ "$METHOD" != rest ] || {
    state=$(echo "select state from minion_jobs where task='obs_rsync_run';" | su postgres -c "psql -t $dbname")
    test "$(echo $state)" == finished
}

echo PASS ${BASH_SOURCE[0]} $@ $METHOD
