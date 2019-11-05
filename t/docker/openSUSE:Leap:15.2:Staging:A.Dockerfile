
ENV dbname openqa
ENV dbuser geekotest

# setup webserver and fake-auth
RUN curl -s https://raw.githubusercontent.com/os-autoinst/openQA/master/script/configure-web-proxy | bash -ex
RUN sed -i -e 's/#*.*method.*=.*$/method = Fake/' /etc/openqa/openqa.ini

# setup plugin
RUN printf '[obs_rsync]\nhome=/opt/openqa-trigger-from-obs' >> /etc/openqa/openqa.ini
RUN gawk -i inplace '1;/plugins =/{print "plugins = ObsRsync"}' /etc/openqa/openqa.ini

RUN chown "$dbuser":users /etc/openqa/database.ini
RUN chown -R "$dbuser":users /usr/share/openqa

# mock OBS backend folder
RUN mkdir -p /mockOBS/openSUSE:Leap:15.2:Staging:A/images/x86_64/product/
# create just empty files as at this point we are not interested about proper binaries 
RUN touch /mockOBS/openSUSE\:Leap\:15.2\:Staging\:A/images/x86_64/product/openSUSE-Leap-15.2-DVD-x86_64-Build248.1-Media.iso
RUN touch /mockOBS/openSUSE\:Leap\:15.2\:Staging\:A/images/x86_64/product/openSUSE-Leap-15.2-DVD-x86_64-Build248.1-Media.iso.sha256
RUN chown -R "$dbuser" /mockOBS

# mock OBS backend host and rsync modules
RUN echo "$dbuser:$dbuser" >> /etc/rsyncd.secrets

RUN printf "\n[openqa]\npath = /mockOBS\nauth users = $dbuser\nsecrets file = /etc/rsyncd.secrets\nhosts allow = 127.0.0.1" >> /etc/rsyncd.conf

