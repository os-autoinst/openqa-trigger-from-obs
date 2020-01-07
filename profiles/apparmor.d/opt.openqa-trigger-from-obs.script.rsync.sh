#include <tunables/global>

/opt/openqa-trigger-from-obs/script/rsync.sh flags=(attach_disconnected) {
  #include <abstractions/base>

  # we don't want rsync.sh to overwrite project-specific files like
  # read_files.sh print_rsync*.sh print_openqa.sh
  # which are generated during deplyment
  # and log files
  # so rules below are quire pedantic
  /opt/openqa-trigger-from-obs/** r,
  /opt/openqa-trigger-from-obs/*:*/.run*/ rw,
  /opt/openqa-trigger-from-obs/*:*/.run*/* rw,
  /opt/openqa-trigger-from-obs/*:*/.run_last rw,
  /opt/openqa-trigger-from-obs/*:*/files*.lst rw,
  /opt/openqa-trigger-from-obs/*:*/*/.run*/ rw,
  /opt/openqa-trigger-from-obs/*:*/*/.run*/* rw,
  /opt/openqa-trigger-from-obs/*:*/*/.run_last rw,
  /opt/openqa-trigger-from-obs/*:*/*/files*.lst rw,
  /opt/openqa-trigger-from-obs/*:*/rsync.lock rw,
  /usr/bin/awk ix,
  /usr/bin/bsdtar ix,
  /usr/bin/cat ix,
  /usr/bin/cp ix,
  /usr/bin/date ix,
  /usr/bin/diff ix,
  /usr/bin/dirname ix,
  /usr/bin/gawk ix,
  /usr/bin/grep ix,
  /usr/bin/head ix,
  /usr/bin/ln ix,
  /usr/bin/ls ix,
  /usr/bin/mkdir ix,
  /usr/bin/rm ix,
  /usr/bin/rsync Px -> /opt/openqa-trigger-from-obs/script/rsync.sh//rsync,
  /usr/bin/sort ix,
  /usr/bin/tail ix,
  /usr/bin/tee ix,
  /usr/share/openqa/script/client rPx -> /opt/openqa-trigger-from-obs/script/rsync.sh//openqa_client,
  /var/lib/openqa/share/factory/repo/** rw, # need write permission because sometimes bsdtar iso here
  /var/lib/openqa/share/factory/{iso,other}/** r,
  /{usr/bin,bin}/bash mrix,

  profile openqa_client {
    #include <abstractions/base>
    #include <abstractions/nameservice>
    #include <abstractions/openssl>
    #include <abstractions/perl>
    #include <abstractions/ssl_certs>

    capability net_bind_service,

    network tcp,

    /etc/openqa/client.conf r,
    /opt/openqa-trigger-from-obs/*:*/.run*/openqa*.log w,
    /opt/openqa-trigger-from-obs/*:*/*/.run*/openqa*.log w,
    /usr/share/openqa/lib/** r,
    /usr/share/openqa/script/client rix,
    /var/lib/openqa/.config/openqa/client.conf r,
    /var/lib/openqa/share/factory/{iso,repo,other}/** r,

  }

  profile rsync flags=(attach_disconnected) {
    #include <abstractions/base>
    #include <abstractions/nameservice>

    capability net_bind_service,

    network tcp,

    link subset /var/lib/openqa/share/factory/iso/** -> /var/lib/openqa/share/factory/iso/**,
    link subset /var/lib/openqa/share/factory/repo/** -> /var/lib/openqa/share/factory/repo/**,

    /opt/openqa-trigger-from-obs/rsync.secret r,

    /opt/openqa-trigger-from-obs/*:*/.run*/rsync*.log w,
    /opt/openqa-trigger-from-obs/*:*/*/.run*/rsync*.log w,
    /usr/bin/rsync mrix,
    /var/lib/openqa/share/factory/{iso,repo,other}/** rw,

  }

  # Site-specific additions and overrides. See local/README for details.
  #include <local/opt.openqa-trigger-from-obs.script.rsync.sh>
}
