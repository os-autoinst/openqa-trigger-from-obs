METHOD=${METHOD:-rsync}

prepare_project() {

prj=$1
suff=$2

(
cd /opt/openqa-trigger-from-obs
mkdir -p $prj
chown $dbuser $prj
echo geekotest > rsync.secret
chmod 600 rsync.secret
chown $dbuser rsync.secret
)

su $dbuser -c "set -ex
cd /opt/openqa-trigger-from-obs
python3 script/scriptgen.py $prj
for l in $prj/*/.run_last ; do
    [ ! -e \$l ] || rm \$l
done
[ ! -e $prj/.run_last ] || rm $prj/.run_last
"

echo "[production]
dsn = DBI:Pg:dbname=openqa;host=/tmp" > /usr/share/openqa/etc/openqa/database.ini

echo "127.0.0.1 obspublish$suff" >> /etc/hosts

mkdir -p /var/lib/openqa/osc-plugin-factory/factory-package-news/
touch /var/lib/openqa/osc-plugin-factory/factory-package-news/factory-package-news.py
chmod +x /var/lib/openqa/osc-plugin-factory/factory-package-news/factory-package-news.py
/var/lib/openqa/osc-plugin-factory/factory-package-news/factory-package-news.py

systemctl start postgresql

systemctl restart apache2
systemctl restart openqa-webui.service
systemctl restart openqa-websockets.service
systemctl restart rsyncd

[ "$METHOD" != rest ] || systemctl restart openqa-gru.service

# wait for webui to become available
sleep 2
attempts_left=25 # sometimes it takes 1 min for starting service (when assets download is slow?)
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


if [ "$METHOD" == rest ]; then
    openqa-cli api -X put obs_rsync/$prj/runs
else
    echo 111 > /opt/openqa-trigger-from-obs/$prj/.job_id
    su "$dbuser" -c "bash -x /opt/openqa-trigger-from-obs/script/rsync.sh $prj"
fi

sleep 10

}
