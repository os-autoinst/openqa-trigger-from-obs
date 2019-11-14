#!/bin/bash
#
# Copyright (C) 2019 SUSE LLC
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.

testcase=$1
set -eo pipefail

[ -n "$testcase" ] || (echo No testcase provided; exit 1) >&2
[ -f "$testcase" ] || (echo Cannot find file "$testcase"; exit 1 ) >&2
[ -n "$OSHT_LOCATION" ] || OSHT_LOCATION=/usr/share/osht.sh
[ -f "$OSHT_LOCATION" ] || { echo "1..0 # osht.sh not found, skipped"; exit 0; }
# shellcheck source=/dev/null
source "$OSHT_LOCATION"

thisdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
basename=$(basename "$testcase")
basename=${basename,,}
basename=${basename//:/_}
containername="localtest.${basename,,}"

SKIP test "${PRIVILEGED_TESTS}" != 1 # PRIVILEGED_TESTS is not set to 1
docker_info="$(docker info >/dev/null 2>&1)" || SKIP test 1 # Docker doesn't seem to be running
testsetup=${testcase%.*}.setup.sh
dockerfile=${testcase%.*}.Dockerfile
echo TESTSETUP=$testsetup
if [ -f "$testsetup" ] ; then
    PLAN 2
else
    PLAN 1
fi

# let's use `docker build` here to utilize docker cache
( 
# shellcheck disable=SC2046 disable=SC2005
echo "FROM opensuse/leap:15.1
ENV container docker
RUN useradd -r -d /usr/lib/openqa -g users --uid=$(id -u) geekotest

RUN zypper -n install systemd

RUN systemctl mask dev-mqueue.mount dev-hugepages.mount \
    systemd-remount-fs.service sys-kernel-config.mount \
    sys-kernel-debug.mount sys-fs-fuse-connections.mount \
    display-manager.service graphical.target systemd-logind.service

ADD dbus.service /etc/systemd/system/dbus.service
RUN systemctl enable dbus.service

ENV LANG en_US.UTF-8

RUN zypper -n addrepo -p 90 obs://devel:openQA devel:openQA
RUN zypper -n addrepo -p 91 obs://devel:openQA:Leap:15.1 devel:openQA:Leap:15.1
RUN zypper -n --gpg-auto-import-keys --no-gpg-checks refresh

RUN zypper -n install --no-recommends perl-Mojo-SQLite
RUN zypper -n install --no-recommends perl-CommonMark
RUN zypper -n install --no-recommends perl-Mojolicious-Plugin-AssetPack
RUN zypper -n install --no-recommends openQA-local-db apache2

RUN zypper -n install apparmor-profiles apparmor-utils
RUN zypper -n install curl hostname iputils vim command-not-found bsdtar zip

RUN zypper -n install make

VOLUME ['/sys/fs/cgroup']
VOLUME ['/run']"

[ ! -f "$dockerfile" ] || cat "$dockerfile"

[ -z "$EXPOSE_PORT" ] || echo EXPOSE 80

echo "CMD  ['/usr/lib/systemd/systemd']"

) | docker build -t "$containername" -f- "$thisdir"

map_port=""
[ -z "$EXPOSE_PORT" ] || map_port="-p $EXPOSE_PORT:80"
docker run --privileged --security-opt=seccomp:unconfined --security-opt=apparmor:unconfined $map_port -v"$thisdir/../../..":/opt/openqa-trigger-from-obs --rm --name "$containername" -d -v /sys/fs/cgroup:/sys/fs/cgroup:ro -- "$containername" /usr/lib/systemd/systemd &

in_cleanup=0

function cleanup {
    [ "$in_cleanup" != 1 ] || return 
    in_cleanup=1
    if [ "$ret" != 0 ] && [ -n "$PAUSE_ON_FAILURE" ]; then
        read -rsn1 -p"Test failed, press any key to finish";echo
    fi
    docker stop -t 0 "$containername" >&/dev/null || :
    _osht_cleanup >&/dev/null
}

trap cleanup INT TERM EXIT
counter=0

# wait container start
until [ $counter -gt 10 ]; do
  sleep 0.5
  docker exec "$containername" pwd >& /dev/null && break
  ((counter++))
done

docker exec "$containername" pwd >& /dev/null || (echo Cannot start container; exit 1 ) >&2

# starting services in container does enable apparmor profile
# on host, so we must disable the profile again
# so it doesn't interfere with the test
# (feel free to remove this line if it is not needed)

echo 'cd /opt/openqa-trigger-from-obs && make install_apparmor' | docker exec -i "$containername" bash -x
echo 'sed -i "s,/usr/share/openqa/script/openqa {,/usr/share/openqa/script/openqa flags=(attach_disconnected) {," /etc/apparmor.d/usr.share.openqa.script.openqa' | docker exec -i "$containername" bash -x
echo 'echo " /var/lib/docker/** r," >> /etc/apparmor.d/local/usr.share.openqa.script.openqa && rcapparmor restart' | docker exec -i "$containername" bash -x


set +e
docker exec -i "$containername" bash < "$testcase"
ret=$?
IS $ret == 0 # test execution
