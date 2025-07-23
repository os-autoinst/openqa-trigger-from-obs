#include <tunables/global>

/opt/openqa-trigger-from-obs/script/rsync.sh flags=(attach_disconnected) {
  #include <abstractions/base>
  #include <local/opt.openqa-trigger-from-obs.script.rsync.sh>

  /dev/tty rw,
  # we don't want rsync.sh to overwrite project-specific files like
  # read_files.sh print_rsync*.sh print_openqa.sh
  # which are generated during deplyment
  # and log files
  # so rules below are quire pedantic
  /opt/openqa-trigger-from-obs/** r,
  /opt/openqa-trigger-from-obs/*:*/*/.run*/ rw,
  /opt/openqa-trigger-from-obs/*:*/*/.run*/* rw,
  /opt/openqa-trigger-from-obs/*:*/*/.run_last rw,
  /opt/openqa-trigger-from-obs/*:*/*/files*.lst rw,
  /opt/openqa-trigger-from-obs/*:*/*/Media*.lst rw,
  /opt/openqa-trigger-from-obs/*:*/*/.Media*.lst* rw,
  /opt/openqa-trigger-from-obs/*:*/*/products* rw,
  /opt/openqa-trigger-from-obs/*:*/*/.products* rw,

  /opt/openqa-trigger-from-obs/*:*/.run*/ rw,
  /opt/openqa-trigger-from-obs/*:*/.run*/* rw,
  /opt/openqa-trigger-from-obs/*:*/.run_last rw,
  /opt/openqa-trigger-from-obs/*:*/files*.lst rw,
  /opt/openqa-trigger-from-obs/*:*/Media*.lst rw,
  /opt/openqa-trigger-from-obs/*:*/.Media*.lst* rw,
  /opt/openqa-trigger-from-obs/*:*/products* rw,
  /opt/openqa-trigger-from-obs/*:*/.products* rw,
  /opt/openqa-trigger-from-obs/*:*/rsync.lock rw,
  /usr/bin/awk ix,
  /usr/bin/bsdtar ix,
  /usr/bin/cat ix,
  /usr/bin/cut ix,
  /usr/bin/cp ix,
  /usr/bin/date ix,
  /usr/bin/diff ix,
  /usr/bin/dirname ix,
  /usr/bin/gawk ix,
  /usr/bin/grep ix,
  /usr/bin/head rix,
  /usr/bin/ln ix,
  /usr/bin/ls ix,
  /usr/bin/mkdir ix,
  /usr/bin/rm ix,
  /usr/bin/rsync Px -> /opt/openqa-trigger-from-obs/script/rsync.sh//rsync,
  /usr/bin/sleep ix,
  /usr/bin/sort ix,
  /usr/bin/tail ix,
  /usr/bin/tee ix,
  /usr/bin/uniq ix,
  /usr/bin/wc ix,
  /var/lib/openqa/osc-plugin-factory/factory-package-news/factory-package-news.py rUx,
  /usr/share/openqa/script/openqa-cli rPx -> /opt/openqa-trigger-from-obs/script/rsync.sh//openqa_cli,
  /usr/bin/openqa-cli rPx -> /opt/openqa-trigger-from-obs/script/rsync.sh//openqa_cli,
  /var/lib/openqa/share/factory/repo/** rwl, # need write and link permissions, because bsdtar may extract iso here
  /var/lib/openqa/share/factory/{iso,hdd,other}/** r,
  /{usr/bin,bin}/bash mrix,
  owner /proc/*/fd/* w,


  profile openqa_cli {
    #include <abstractions/base>
    #include <abstractions/nameservice>
    #include <abstractions/openssl>
    #include <abstractions/perl>
    #include <abstractions/ssl_certs>

    capability net_bind_service,

    network tcp,

    /etc/openqa/client.conf r,
    /opt/openqa-trigger-from-obs/*:*/*/.run*/openqa*.log w,
    /opt/openqa-trigger-from-obs/*:*/.run*/openqa*.log w,
    /usr/bin/openqa-cli rix,
    /usr/share/openqa/** r,
    /usr/share/openqa/script/openqa-cli rix,
    /var/lib/openqa/.config/openqa/client.conf r,
    /var/lib/openqa/share/factory/{iso,hdd,repo,other}/** r,

  }

  profile rsync flags=(attach_disconnected) {
    #include <abstractions/base>
    #include <abstractions/nameservice>

    capability net_bind_service,

    network tcp,

    link subset /var/lib/openqa/share/factory/iso/** -> /var/lib/openqa/share/factory/iso/**,
    link subset /var/lib/openqa/share/factory/repo/** -> /var/lib/openqa/share/factory/repo/**,

    /opt/openqa-trigger-from-obs/rsync.secret r,

    /opt/openqa-trigger-from-obs/*:*/*/.run*/rsync*.log w,
    /opt/openqa-trigger-from-obs/*:*/.run*/rsync*.log w,

    /opt/openqa-trigger-from-obs/*:*/Media*.lst rw,
    /opt/openqa-trigger-from-obs/*:*/.Media*.lst* rw,
    /opt/openqa-trigger-from-obs/*:*/products* rw,
    /opt/openqa-trigger-from-obs/*:*/.products* rw,

    /opt/openqa-trigger-from-obs/*:*/*/Media*.lst rw,
    /opt/openqa-trigger-from-obs/*:*/*/.Media*.lst* rw,
    /opt/openqa-trigger-from-obs/*:*/*/products* rw,
    /opt/openqa-trigger-from-obs/*:*/*/.products* rw,

    /usr/bin/rsync mrix,
    /var/lib/openqa/share/factory/{iso,hdd,repo,other}/** rw,

  }
}
