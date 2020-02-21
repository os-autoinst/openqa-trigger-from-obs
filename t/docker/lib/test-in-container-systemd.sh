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
PLAN 1

map_port=""
[ -z "$EXPOSE_PORT" ] || map_port="-p $EXPOSE_PORT:80"
# docker run --privileged $map_port -v"$thisdir/../../..":/opt/openqa-trigger-from-obs --env METHOD=$METHOD --rm --name "$containername" -d -v /sys/fs/cgroup:/sys/fs/cgroup:ro -- registry.opensuse.org/devel/openqa/ci/containers/serviced &
docker run --privileged $map_port -v"$thisdir/../../..":/opt/openqa-trigger-from-obs --env METHOD=$METHOD --rm --name "$containername" -d -v /sys/fs/cgroup:/sys/fs/cgroup:ro -- 5467a81e9e28 &

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
counter=1

# wait container start
until [ $counter -gt 10 ]; do
  sleep 0.5
  docker exec "$containername" pwd >& /dev/null && break
  ((counter++))
done

docker exec "$containername" pwd >& /dev/null || (echo Cannot start container; exit 1 ) >&2

echo 'bash /opt/init-trigger-from-obs.sh' | docker exec -i "$containername" bash -x

set +e
docker cp lib/common.sh "$containername":/lib
docker exec -i "$containername" bash < "$testcase"
ret=$?
IS $ret == 0 # test execution
