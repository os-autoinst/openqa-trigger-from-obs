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

thisdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
basename=$(basename "$testcase")
basename=${basename,,}
basename=${basename//:/_}
containername="localtest.${basename,,}"

test "${PRIVILEGED_TESTS}" == 1 || ( echo PRIVILEGED_TESTS is not set to 1 ; exit 1)

docker info >/dev/null 2>&1 || (echo Docker doesnt seem to be running ; exit 1)

map_port=""
[ -z "$EXPOSE_PORT" ] || map_port="-p $EXPOSE_PORT:80"
docker run --privileged $map_port -v"$thisdir/../../..":/opt/openqa-trigger-from-obs --env METHOD=$METHOD --rm --name "$containername" -d -v /sys/fs/cgroup:/sys/fs/cgroup:ro -- registry.opensuse.org/devel/openqa/ci/containers/serviced

in_cleanup=0

function cleanup {
    [ "$in_cleanup" != 1 ] || return
    in_cleanup=1
    if [ "$ret" != 0 ] && [ -n "$PAUSE_ON_FAILURE" ]; then
        read -rsn1 -p"Test failed, press any key to finish";echo
    fi
    [ "$ret" == 0 ] || echo FAIL $basename
    docker stop -t 0 "$containername" >&/dev/null || :
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

docker exec "$containername" bash /opt/init-trigger-from-obs.sh

[ -z "$CIRCLE_JOB" ] || echo 'aa-complain /usr/share/openqa/script/openqa' | docker exec "$containername" bash -x
set +e
docker cp lib/common.sh "$containername":/lib
docker exec -e TESTCASE="$testcase" "$containername" bash -xe /opt/openqa-trigger-from-obs/t/docker/$testcase
ret=$?
( exit $ret )
