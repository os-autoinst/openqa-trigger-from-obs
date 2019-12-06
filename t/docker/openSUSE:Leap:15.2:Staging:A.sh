#!lib/test-in-container-systemd.sh

set -ex

su $dbuser -c 'set -ex
cd /opt/openqa-trigger-from-obs
mkdir -p openSUSE:Leap:15.2:Staging:A
python3 script/scriptgen.py openSUSE:Leap:15.2:Staging:A
[ ! -e openSUSE:Leap:15.2:Staging:A/.run_last ] || rm openSUSE:Leap:15.2:Staging:A/.run_last
echo geekotest > rsync.secret'

echo '127.0.0.1 obspublish-stage' >> /etc/hosts
systemctl enable --now postgresql

su postgres -c "createuser -D $dbuser"
su postgres -c "createdb -O $dbuser $dbname"


systemctl enable --now apache2.service
systemctl enable --now openqa-webui.service
systemctl enable --now openqa-websockets.service
# scheduler and livehandler are not needed in this test
# systemctl enable --now openqa-scheduler.service
# systemctl enable --now openqa-livehandler.service
systemctl enable --now openqa-gru.service

# wait for webui to become available
sleep 2
attempts_left=10
while ! curl -sI http://localhost/ | grep 200 ; do
    sleep 3
    : $((attempts_left--))
    [ "$attempts_left" -gt 0 ] || {
        service openqa-webui status
        exit 1
    }
done

# this must create default user
curl -sI http://localhost/login

# create api key - the table will be available after webui service startup
API_KEY=$(hexdump -n 8 -e '2/4 "%08X" 1 "\n"' /dev/urandom)
API_SECRET=$(hexdump -n 8 -e '2/4 "%08X" 1 "\n"' /dev/urandom)
echo "INSERT INTO api_keys (key, secret, user_id, t_created, t_updated) VALUES ('${API_KEY}', '${API_SECRET}', 2, NOW(), NOW());" | su postgres -c "psql $dbname"

cat >> /etc/openqa/client.conf <<EOF
[localhost]
key = ${API_KEY}
secret = ${API_SECRET}
EOF

mkdir -p /root/.config/openqa
cp /etc/openqa/client.conf /root/.config/openqa/
mkdir -p /var/lib/openqa/.config/openqa/
cp /etc/openqa/client.conf /var/lib/openqa/.config/openqa/
chown "$dbuser" /var/lib/openqa/.config/openqa/client.conf

systemctl enable --now rsyncd
openqa-client --host localhost /api/v1/obs_rsync/openSUSE:Leap:15.2:Staging:A/runs put || :

sleep 10
set -x
# make sure run did happen
test -f /var/lib/openqa/factory/iso/openSUSE-Leap-15.2-Staging:A-Staging-DVD-x86_64-Build248.1-Media.iso
test -f /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:Staging:A/.run_last/openqa.cmd.log
grep -q 'scheduled_product_id => 1' /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:Staging:A/.run_last/openqa.cmd.log

state=$(echo "select state from minion_jobs where task='obs_rsync_run';" | su postgres -c "psql -t $dbname")
test "$(echo $state)" == finished

# run second time, make sure all is set
# rm /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:Staging:A/.run_last
echo "delete from minion_jobs where task='obs_rsync_run';" | su postgres -c "psql -t $dbname"


mv /mockOBS/openSUSE\:Leap\:15.2\:Staging\:A/images/x86_64/product/openSUSE-Leap-15.2-DVD-x86_64-Build{248.1,248.2}-Media.iso
mv /mockOBS/openSUSE\:Leap\:15.2\:Staging\:A/images/x86_64/product/openSUSE-Leap-15.2-DVD-x86_64-Build{248.1,248.2}-Media.iso.sha256

openqa-client --host localhost /api/v1/obs_rsync/openSUSE:Leap:15.2:Staging:A/runs put || :
sleep 10

test -f /var/lib/openqa/factory/iso/openSUSE-Leap-15.2-Staging:A-Staging-DVD-x86_64-Build248.2-Media.iso
test -f /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:Staging:A/.run_last/openqa.cmd.log
grep -q 'scheduled_product_id => 2' /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:Staging:A/.run_last/openqa.cmd.log

state=$(echo "select state from minion_jobs where task='obs_rsync_run';" | su postgres -c "psql -t $dbname")
test "$(echo $state)" == finished
test "$(ls -1q /opt/openqa-trigger-from-obs/openSUSE:Leap:15.2:Staging:A/.run* | wc -l)" -ge 3
echo PASS ${BASH_SOURCE[0]}
