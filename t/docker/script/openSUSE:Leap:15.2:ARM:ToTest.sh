#!lib/test-in-container-systemd.sh

set -ex
source lib/common.sh

# mock OBS backend folder
mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-cd-mini-aarch64 && \
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-cd-mini-aarch64/openSUSE-Leap-15.2-NET-aarch64-Build519.3-Media.iso && \
echo "-----BEGIN PGP SIGNED MESSAGE-----" > /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-cd-mini-aarch64/openSUSE-Leap-15.2-NET-aarch64-Build519.3-Media.iso.sha256 && \
echo "Hash: SHA256"                      >> /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-cd-mini-aarch64/openSUSE-Leap-15.2-NET-aarch64-Build519.3-Media.iso.sha256 && \
echo ""                                  >> /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-cd-mini-aarch64/openSUSE-Leap-15.2-NET-aarch64-Build519.3-Media.iso.sha256 && \
echo 1 | sha256sum                       >> /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-cd-mini-aarch64/openSUSE-Leap-15.2-NET-aarch64-Build519.3-Media.iso.sha256 && \
mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-dvd5-dvd-aarch64 && \
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-cd-mini-aarch64/openSUSE-Leap-15.2-DVD-aarch64-Build519.3-Media.iso && \
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-cd-mini-aarch64/openSUSE-Leap-15.2-DVD-aarch64-Build519.3-Media.iso.sha256 && \
mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-ftp-ftp-aarch64/openSUSE-15.2-aarch64-Media1/media.1 && \
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-ftp-ftp-aarch64/openSUSE-15.2-aarch64-Media1/repo && \
mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-ftp-ftp-aarch64/openSUSE-15.2-aarch64-Media1/media.1 && \
echo Build519.2 > /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-ftp-ftp-aarch64/openSUSE-15.2-aarch64-Media1/media.1/media && \
mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-ftp-ftp-aarch64/openSUSE-15.2-aarch64-Media2/aarch64 && \
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-ftp-ftp-aarch64/openSUSE-15.2-aarch64-Media2/aarch64/mraa-debug && \
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-ftp-ftp-aarch64/openSUSE-15.2-aarch64-Media2/aarch64/other && \
mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-ftp-ftp-aarch64/openSUSE-15.2-aarch64-Media3/src && \
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-ftp-ftp-aarch64/openSUSE-15.2-aarch64-Media3/src/coreutils && \
echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ARM\:ToTest/images/local/000product:openSUSE-ftp-ftp-aarch64/openSUSE-15.2-aarch64-Media3/src/other

chown -R "$dbuser" /mockOBS

prepare_project openSUSE:Leap:15.2:ARM:ToTest

set -x
# make sure run didn't happen, because repo had different version
test ! -f /var/lib/openqa/factory/iso/openSUSE-Leap-15.2-DVD-aarch64-Build519.3-Media.iso
test ! -f /var/lib/openqa/factory/iso/openSUSE-Leap-15.2-NET-aarch64-Build519.3-Media.iso
test ! -d /var/lib/openqa/factory/repo/openSUSE-15.2-oss-aarch64-Build519.3

echo PASS ${BASH_SOURCE[0]} $TESTCASE $METHOD
