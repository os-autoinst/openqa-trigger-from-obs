#!lib/test-in-container-systemd.sh

set -ex

su $dbuser -c 'set -ex
cd /opt/openqa-trigger-from-obs
mkdir -p Virtualization:WSL/Tumbleweed
python3 script/scriptgen.py Virtualization:WSL
[ ! -e Virtualization:WSL/Tumbleweed/.run_last ] || rm Virtualization:WSL/Tumbleweed/.run_last
echo geekotest > rsync.secret
chmod 600 rsync.secret'

echo '127.0.0.1 obspublish-other' >> /etc/hosts
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
openqa-client --host localhost /api/v1/obs_rsync/Virtualization:WSL/runs put || :

sleep 10
set -x
# make sure run did happen
test -f /var/lib/openqa/factory/other/openSUSE-Tumbleweed-x64-Build20191128.7.9.appx
test -f /opt/openqa-trigger-from-obs/Virtualization:WSL/Tumbleweed/.run_last/openqa.cmd.log
grep -q 'scheduled_product_id => 1' /opt/openqa-trigger-from-obs/Virtualization:WSL/Tumbleweed/.run_last/openqa.cmd.log

state=$(echo "select state from minion_jobs where task='obs_rsync_run';" | su postgres -c "psql -t $dbname")
test "$(echo $state)" == finished
echo PASS ${BASH_SOURCE[0]}
