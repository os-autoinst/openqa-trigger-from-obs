#!lib/test-in-container-systemd.sh

set -ex

su $dbuser -c 'set -ex
cd /opt/openqa-trigger-from-obs
mkdir -p openSUSE:Factory:ToTest
python3 script/scriptgen.py openSUSE:Factory:ToTest
[ ! -e openSUSE:Factory:ToTest/base/.run_last ] || rm openSUSE:Factory:ToTest/base/.run_last
echo geekotest > rsync.secret
chmod 600 rsync.secret'

echo '127.0.0.1 obspublish' >> /etc/hosts
systemctl enable --now postgresql

su postgres -c "createuser -D $dbuser"
su postgres -c "createdb -O $dbuser $dbname"

systemctl enable --now rsyncd

runs_before="$(ls -la /opt/openqa-trigger-from-obs/openSUSE:Factory:ToTest/base/.run_* | wc -l)"

su "$dbuser" -c 'bash -x /opt/openqa-trigger-from-obs/script/rsync.sh openSUSE:Factory:ToTest' || :

runs_after="$(ls -la /opt/openqa-trigger-from-obs/openSUSE:Factory:ToTest/base/.run_* | wc -l)"

# no runs should happend because inconsistent snapshots
test "$runs_before" -eq "$runs_after"

echo PASS ${BASH_SOURCE[0]}
