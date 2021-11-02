export METHOD=rest
exit 0 # disabke post command because currently it shows strange error in CI:
# /usr/bin/perl: error while loading shared libraries: libm.so.6: cannot stat shared object: Permission denied
set -e
script/openSUSE:Leap:15.2:Staging:A.sh
script/openSUSE:Leap:15.2:WSL.sh
