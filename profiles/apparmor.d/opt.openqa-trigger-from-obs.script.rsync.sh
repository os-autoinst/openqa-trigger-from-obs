#include <tunables/global>

/opt/openqa-trigger-from-obs/script/rsync.sh {
  #include <abstractions/base>

  /usr/bin/awk ix,
  /usr/bin/gawk ix,
  /{usr/bin,bin}/bash mrix,
  /usr/bin/bsdtar ix,
  /usr/bin/cat ix,
  /usr/bin/cp ix,
  /usr/bin/head ix,
  /usr/bin/date ix,
  /usr/bin/dirname ix,
  /usr/bin/grep ix,
  /usr/bin/ln ix,
  /usr/bin/ls ix,
  /usr/bin/mkdir ix,
  /usr/bin/rm ix,
  /usr/bin/rsync Px -> /opt/openqa-trigger-from-obs/script/rsync.sh//rsync,
  /usr/bin/sort ix,
  /usr/bin/tee ix,

  /usr/share/openqa/script/client rPx -> /opt/openqa-trigger-from-obs/script/rsync.sh//openqa_client,

  /opt/openqa-trigger-from-obs/** r,
  /opt/openqa-trigger-from-obs/openSUSE*/files*.lst rw,
  /opt/openqa-trigger-from-obs/openSUSE*/rsync.lock rw,
  /opt/openqa-trigger-from-obs/openSUSE*/.run_last rw,
  /opt/openqa-trigger-from-obs/openSUSE*/.run*/ rw,
  /opt/openqa-trigger-from-obs/openSUSE*/.run*/* rw,
  /var/lib/openqa/share/factory/iso/** r,
  /var/lib/openqa/share/factory/repo/** rw, # need write permission because sometimes bsdtar iso here

  profile rsync {
    #include <abstractions/base>
    #include <abstractions/nameservice>

    capability net_bind_service,
    network tcp,

    /usr/bin/rsync mrix,

    /var/lib/openqa/share/factory/{iso,repo}/** rw,
    link subset /var/lib/openqa/share/factory/iso/** -> /var/lib/openqa/share/factory/iso/**,
    link subset /var/lib/openqa/share/factory/repo/** -> /var/lib/openqa/share/factory/repo/**,

    /opt/openqa-trigger-from-obs/openSUSE*/.run*/rsync*.log w,
  }

  profile openqa_client {
    #include <abstractions/base>
    #include <abstractions/nameservice>
    #include <abstractions/openssl>
    #include <abstractions/ssl_certs>
    #include <abstractions/perl>

    capability net_bind_service,
    network tcp,

    /usr/share/openqa/script/client rix,
    /usr/share/openqa/lib/** r,
    /etc/openqa/client.conf r,

    /var/lib/openqa/share/factory/iso/** r,
    /var/lib/openqa/share/factory/repo/** r,

    /opt/openqa-trigger-from-obs/openSUSE*/.run*/openqa*.log w,
  }
}
