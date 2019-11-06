
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
RUN mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64 && \
  echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Leap-15.2-NET-x86_64-Build519.3-Media.iso && \
  echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Leap-15.2-NET-x86_64-Build519.3-Media.iso.sha256 && \
  mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-dvd5-dvd-x86_64 && \
  echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Leap-15.2-DVD-x86_64-Build519.3-Media.iso && \
  echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-cd-mini-x86_64/openSUSE-Leap-15.2-DVD-x86_64-Build519.3-Media.iso.sha256 && \
  mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-15.2-x86_64-Media1 && \
  echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-15.2-x86_64-Media1/repo && \
  mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-15.2-x86_64-Media2/x86_64 && \
  echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-15.2-x86_64-Media2/x86_64/mraa-debug && \
  echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-15.2-x86_64-Media2/x86_64/other && \
  mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-15.2-x86_64-Media3/src && \
  echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-15.2-x86_64-Media3/src/coreutils && \
  echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-ftp-ftp-x86_64/openSUSE-15.2-x86_64-Media3/src/other && \
  mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Leap-15.2-Addon-NonOss-FTP-x86_64-Media1 && \
  echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Leap-15.2-Addon-NonOss-FTP-x86_64-Media1/repo && \
  mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Leap-15.2-Addon-NonOss-FTP-x86_64-Media2 && \
  echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Leap-15.2-Addon-NonOss-FTP-x86_64-Media2/debugfile && \
  mkdir -p /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Leap-15.2-Addon-NonOss-FTP-x86_64-Media3 && \
  echo 1 > /mockOBS/openSUSE\:Leap\:15.2\:ToTest/images/local/000product:openSUSE-Addon-NonOss-ftp-ftp-x86_64/openSUSE-Leap-15.2-Addon-NonOss-FTP-x86_64-Media3/sourcefile

# create just empty files as at this point we are not interested about proper binaries 
RUN chown -R "$dbuser" /mockOBS

# mock OBS backend host and rsync modules
RUN echo "$dbuser:$dbuser" >> /etc/rsyncd.secrets

RUN printf "\n[openqa]\npath = /mockOBS\nauth users = $dbuser\nsecrets file = /etc/rsyncd.secrets\nhosts allow = 127.0.0.1" >> /etc/rsyncd.conf

