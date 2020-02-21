export METHOD=rsync
set -e
script/openSUSE:Leap:15.2:Staging:A.sh
script/openSUSE:Leap:15.2:ToTest.sh
script/openSUSE:Factory:ToTest.sh
script/Virtualization:WSL.sh
