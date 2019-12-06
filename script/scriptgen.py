import sys
import os
import re
from subprocess import check_output, CalledProcessError, STDOUT
import argparse
import copy
from contextlib import suppress
from xml.etree import ElementTree
from collections import defaultdict

header = '''# GENERATED FILE - DO NOT EDIT
set -e
'''

clear_lst = '''for f in __envdir/files_*.lst; do
    [ ! -f "$f" ] ||  : > "$f"
done
'''

read_files_curl = '''curl -s PRODUCTPATH/ | grep -o 'ISOMASK' | head -n 1 >> __envdir/files_iso.lst'''

read_files_hdd = '''rsync --list-only PRODUCTPATH/ | grep -o 'ISOMASK' | awk '{ $1=$2=$3=$4=""; print substr($0,5); }' | head -n 1 >> __envdir/files_iso.lst'''

read_files_iso = '''rsync --list-only PRODUCTISOPATH/ | grep -P 'Media1?.iso$' | grep -E 'ARCHORS' | awk '{ $1=$2=$3=$4=""; print substr($0,5); }' >> __envdir/files_iso.lst
'''

read_files_repo = '''rsync --list-only PRODUCTREPOPATH/ | grep -P 'Media[1-3](.license)?$' | awk '{ $1=$2=$3=$4=""; print substr($0,5); } ' | grep -v IGNOREPATTERN | grep -E 'REPOORS' | grep -E 'ARCHORS'  >> __envdir/files_repo.lst
'''

def rsync_iso_staging(brand):
    if brand == 'obs': return '''[ -z "__STAGING" ] || dest=${dest//$flavor/Staging:__STAGING-Staging-$flavor}'''

rsync_iso = lambda brand : '''
archs=(ARCHITECTURS)

for flavor in {FLAVORLIST,}; do
    for arch in "${archs[@]}"; do
        filter=$flavor
        [[ ! -v flavor_filter[@] ]] || [ -z "${flavor_filter[$flavor]}" ] || filter=${flavor_filter[$flavor]}
        src=$(grep "$filter" __envdir/files_iso.lst | grep $arch | head -n 1)
        [ ! -z "$src" ] || continue
        dest=$src
        ''' + rsync_iso_staging(brand) + '''
        echo "rsync --timeout=3600 PRODUCTISOPATH/*$src /var/lib/openqa/factory/iso/$dest"
        echo "rsync --timeout=3600 PRODUCTISOPATH/*$src.sha256 /var/lib/openqa/factory/other/$dest.sha256"

        [ -z "FLAVORASREPOORS" ] || [ $( echo "$flavor" | grep -E -c "^(FLAVORASREPOORS)$" ) -eq 0 ] || echo "[ -d /var/lib/openqa/factory/repo/${dest%.iso} ] || {
    mkdir /var/lib/openqa/factory/repo/${dest%.iso}
    bsdtar xf /var/lib/openqa/factory/iso/$dest -C /var/lib/openqa/factory/repo/${dest%.iso}
}"
    done
done'''

rsync_repo1 = '''
echo '# REPOLIST'
buildid=$(cat __envdir/files_iso.lst | grep -E 'FLAVORORS' | grep -o 'Build[^-]*' | head -n 1)
[ -z "__STAGING" ] || buildid=${buildid//Build/Build__STAGING.}

for repo in {REPOLIST,}; do
    while read src; do
        [ ! -z "$src" ] || continue
        dest=$src
        destPrefix=${dest%-Media*}
        destSuffix=${dest#$destPrefix}
        dest=$destPrefix
'''

rsync_repo2 = '''
        destPrefix=$dest
        repoDest=$destPrefix-$buildid$destSuffix
        repoCur=$destPrefix-CURRENT$destSuffix
        [ -z "__STAGING" ] || repoCur=$destPrefix-__STAGING-CURRENT$destSuffix
        echo "rsync --timeout=3600 -r PRODUCTREPOPATH/$src/ /var/lib/openqa/factory/repo/$repoCur"
        echo "rsync --timeout=3600 -r --link-dest /var/lib/openqa/factory/repo/$repoCur/ /var/lib/openqa/factory/repo/$repoCur/ /var/lib/openqa/factory/repo/$repoDest/"
    done < <(grep $repo-POOL __envdir/files_repo.lst)
done
'''

rsync_repodir1 = '''
archs=(ARCHITECTURS)
buildid=$(cat __envdir/files_iso.lst | grep -E 'FLAVORORS' | grep -o 'Build[^-]*' | head -n 1)

for arch in "${archs[@]}"; do
    while read src; do
        [ ! -z "$src" ] || continue
        dest=$src
        destPrefix=${dest%$arch*}
        destSuffix=${dest#$destPrefix}
        mid=''
        dest=$destPrefix$mid$destSuffix'''

def rsync_repodir2(brand):
    if brand == 'obs': return '''
        dest=${dest//-Media2/}
        echo rsync --timeout=3600 -r RSYNCFILTER PRODUCTREPOPATH/*Media2/*  /var/lib/openqa/factory/repo/$dest-CURRENT-debuginfo/
        echo rsync --timeout=3600 -r --link-dest /var/lib/openqa/factory/repo/$dest-CURRENT-debuginfo/ /var/lib/openqa/factory/repo/$dest-CURRENT-debuginfo/ /var/lib/openqa/factory/repo/$dest-$buildid-debuginfo
    done < <(grep $arch __envdir/files_repo.lst | grep Media2)
done
'''

def openqa_call_start_staging(brand):
    if brand == 'obs': return '''[ -z "__STAGING" ] || version=${version}:S:__STAGING
        [ -z "__STAGING" ] || destiso=${iso//$flavor/Staging:__STAGING-Staging-$flavor}
        [ -z "__STAGING" ] || flavor=Staging-$flavor'''


openqa_call_start = lambda brand: '''
archs=(ARCHITECTURS)

for flavor in {FLAVORALIASLIST,}; do
    for arch in "${archs[@]}"; do
        filter=$flavor
        [[ ! -v flavor_filter[@] ]] || [ -z "${flavor_filter[$flavor]}" ] || filter=${flavor_filter[$flavor]}
        [ $filter != Appliance ] || filter="qcow2"
        iso=$(grep "$filter" __envdir/files_iso.lst | grep $arch | head -n 1)
        build=$(echo $iso | grep -o -E '(Build|Snapshot)[^-]*' | grep -o -E '[0-9]+.?[0-9]+(\.[0-9]+)?') || continue
        build1=$build
        destiso=$iso
        version=VERSIONVALUE
        [ -z "__STAGING" ] || build1=__STAGING.$build
        ''' + openqa_call_start_staging(brand) + '''
        [ ! -z "$build"  ] || continue
        [ "$arch" != . ] || arch=x86_64

        echo "/usr/share/openqa/script/client isos post --host localhost \\\\\"
(
 echo \" _OBSOLETE=1
 DISTRI=DISTRIVALUE \\\\
 ARCH=$arch \\\\
 VERSION=$version \\\\
 BUILD=$build1 \\\\'''

openqa_call_legacy_builds=''' BUILD_HA=$build1 \\\\
 BUILD_SDK=$build1 \\\\
 BUILD_SES=$build1 \\\\
 BUILD_SLE=$build1 \\\\'''

openqa_call_start_iso = ''' ISO=${destiso} \\\\
 CHECKSUM_ISO=\$(head -c 113 /var/lib/openqa/factory/other/${destiso}.sha256 | tail -c 64) \\\\
 ASSET_ISO_SHA256=${destiso}.sha256 \\\\"'''

# if MIRROREPO is set - expressions for FLAVORASREPOORS will elaluate to false
def openqa_call_repo0(brand):
    if brand == 'obs': return ''' [ -z "FLAVORASREPOORSMIRRORREPO" ] || [ $( echo "$flavor" | grep -E -c "^(FLAVORASREPOORS)$" ) == 0"MIRRORREPO" ] || {
    echo " MIRROR_PREFIX=http://openqa.opensuse.org/assets/repo \\\\
 SUSEMIRROR=http://openqa.opensuse.org/assets/repo/REPO0_ISO \\\\
 MIRROR_HTTP=http://openqa.opensuse.org/assets/repo/REPO0_ISO \\\\
 MIRROR_HTTPS=https://openqa.opensuse.org/assets/repo/REPO0_ISO \\\\
 FULLURL=1 \\\\"
    }'''

openqa_call_repo0a = ''' [ -z "FLAVORASREPOORS" ] || [ $( echo "$flavor" | grep -E -c "^(FLAVORASREPOORS)$" ) -eq 0 ] || echo " REPO_0=REPO0_ISO \\\\"'''

def openqa_call_repot_part1(brand):
    if brand == 'obs': return '''[ -z "__STAGING" ] || repo=${repo//Module/Staging:__STAGING-Module}
                [ -z "__STAGING" ] || repo=${repo//Product/Staging:__STAGING-Product}'''

def openqa_call_repot_part2(brand):
    if brand == 'obs': return 'repoDest=$repoPrefix-Build$build$repoSuffix'

def openqa_call_repot_part3(brand):
    if brand == 'obs': return '''[[ $repoDest != *Media2* ]] || repoKey=${repoKey}_DEBUG
                [[ $repoDest != *Media3* ]] || repoKey=${repoKey}_SOURCE'''

def openqa_call_build_id_from_iso1(build_id_from_iso):
    if not build_id_from_iso:
        return ""
    return '''build2=$(grep $repot __envdir/files_iso_buildid.lst | grep $arch | grep -o -E '(Build|Snapshot)[^-]*' | grep -o -E '[0-9]+.?[0-9]+(\.[0-9]+)?' | head -n 1)
                [ -z "$build2" ] || build1=$build2'''

def openqa_call_build_id_from_iso2(build_id_from_iso):
    if not build_id_from_iso:
        return ""
    return '''[ "$repoKey" != LIVE_PATCHING ] || repoKey=LIVE
                [[ $repoDest != *Media1* ]] || [[ $repo =~ license ]] || [ -z "$build2" ] || echo " BUILD_$repoKey=$build2 \\\\"'''

openqa_call_repot = lambda brand, build_id_from_iso: '''
        for repot in {REPOLIST,}; do
            while read repo; do
                ''' + openqa_call_repot_part1(brand) + '''
                repoPrefix=${repo%-Media*}
                repoSuffix=${repo#$repoPrefix}
                ''' + openqa_call_build_id_from_iso1(build_id_from_iso) + '''
                ''' + openqa_call_repot_part2(brand) + '''
                repoKey=${repot}
                repoKey=${repoKey^^}
                repoKey=${repoKey//-/_}
                echo " REPO_$i=$repoDest \\\\"
                ''' + openqa_call_repot_part3(brand) + '''
                [[ $repo =~ license ]] || echo " REPO_REPOPREFIX$repoKey=$repoDest \\\\"
                ''' + openqa_call_build_id_from_iso2(build_id_from_iso) + '''
                : $((i++))
            done < <(grep $repot-POOL __envdir/files_repo.lst | grep REPOTYPE | grep $arch | sort)
        done'''

def openqa_call_repot1_debugsource(brand):
    if brand == 'obs': return '''[[ $dest != *Media2* ]] || repoKey=${repoKey}_DEBUGINFO
            [[ $dest != *Media2* ]] || dest=$dest-debuginfo
            [[ $dest != *Media3* ]] || repoKey=${repoKey}_SOURCE
            [[ $dest != *Media3* ]] || dest=$dest-source'''

openqa_call_repot1 = lambda brand: '''
        while read src; do
            dest=$src
            destPrefix=${dest%$arch*}
            destSuffix=${dest#$destPrefix}
            mid=''
            dest=$destPrefix$mid$destSuffix
            repoPrefix=${dest%-Media*}
            repoSuffix=${dest#$repoPrefix}
            dest=$repoPrefix-Build$build$repoSuffix
            repoKey=REPOKEY
            repoKey=${repoKey^^}
            repoKey=${repoKey//-/_}
            ''' + openqa_call_repot1_debugsource(brand) + '''
            dest=${dest//-Media1/}
            dest=${dest//-Media2/}
            dest=${dest//-Media3/}
'''

openqa_call_repot2 = '''
            echo " REPO_$i=$dest \\\\"
            [[ $dest =~ license ]] || echo " REPO_$repoKey=$dest \\\\"
            [[ ! $repoKey =~ _DEBUGINFO ]] || [ -z "DEBUG_PACKAGES" ] || echo " REPO_${{repoKey}}_PACKAGES='DEBUG_PACKAGES' \\\\"
            [[ ! $repoKey =~ _SOURCE ]] || [ -z "SOURCE_PACKAGES" ] || echo " REPO_${{repoKey}}_PACKAGES='SOURCE_PACKAGES' \\\\"
            : $((i++))
        done < <(grep $arch __envdir/files_repo.lst {} | sort)'''


def openqa_call_end(brand):
    if brand == 'obs': return '''
        echo " FLAVOR=$flavor \\\\"
) | LC_COLLATE=C sort
    done
done
'''

class ActionGenerator:
    def __init__(self, envdir, productpath, version, brand, subfolder):
        self.archs = "aarch64 ppc64le s390x x86_64"
        self.flavors = []
        self.flavor_aliases = defaultdict(list)
        self.flavor_aliases_flavor = []
        self.hdds = []
        self.assets = []
        self.isos = []
        self.iso_5 = ""
        self.fixed_iso = ""
        self.iso_extract_as_repo = {}
        self.mirror_repo = ""
        self.repos = []
        self.build_id_from_iso = 0
        self.repodirs = []
        self.renames = []
        self.brand = brand
        self.envdir = envdir
        self.productpath = productpath
        self.version = version
        self.subfolder = subfolder
        self.distri = ""
        self.iso_path = ""
        self.repo_path = ""
        self.legacy_builds = 0

    def p(self,s, f, extra1=None, extra2=None, extra3=None, extra4=None, extra5=None, extra6=None, extra7=None, extra8=None, extra9=None, extra10=None):
        if extra1 != None and extra2 != None:
            s=s.replace(extra1,extra2)
            if extra3 != None and extra4 != None:
                s=s.replace(extra3,extra4)
                if extra5 != None and extra6 != None:
                    s=s.replace(extra5,extra6)
                    if extra7 != None and extra8 != None:
                        s=s.replace(extra7,extra8)
                        if extra9 != None and extra10 != None:
                            s=s.replace(extra9,extra10)
        s=s.replace('PRODUCTPATH',self.productpath)
        s=s.replace('PRODUCTISOPATH',self.productisopath())
        s=s.replace('PRODUCTREPOPATH',self.productrepopath())
        s=s.replace('__envdir',self.envdir)
        if self.subfolder:
            s=s.replace('VERSIONVALUE', self.subfolder.lstrip('Leap_'))
        else:
            s=s.replace('VERSIONVALUE', self.version)
        s=s.replace("DISTRIVALUE", self.distri)
        s=s.replace("__STAGING", self.staging())
        s=s.replace("ARCHITECTURS", self.archs)
        s=s.replace("ARCHORS", self.archs.replace(" ","|"))
        s=s.replace("SUBFOLDER", self.subfolder)

        if self.flavors:
            s=s.replace("FLAVORLIST",','.join(self.flavors))
            aliases = copy.deepcopy(self.flavors)
            aliases.extend(self.flavor_aliases_flavor)
            s=s.replace("FLAVORALIASLIST",','.join(aliases))
            s=s.replace("FLAVORORS", '|'.join(self.flavors))
            s=s.replace("FLAVORASREPOORS", '|'.join([f for f in self.flavors if self.iso_extract_as_repo.get(f,0)]))

        if self.repos:
            s=s.replace("REPOLIST",  ','.join([m.attrib["name"] if "name" in m.attrib else m.tag for m in self.repos]))
            s=s.replace("REPOORS",   '|'.join([m.attrib["name"] if "name" in m.attrib else m.tag for m in self.repos]))
        s=s.replace("MIRRORREPO", self.mirror_repo)
        if self.domain:
            s=s.replace("opensuse.org",self.domain)
        print(s, file=f)

    def staging(self):
        m = re.match(r'.*Staging:(?P<staging>[A-Z]).*', self.envdir)
        if not m:
            return ""
        return m.groupdict().get("staging","")

    def productisopath(self):
        if self.iso_path and self.productpath:
            return self.productpath + "/" + self.iso_path
        if self.iso_path:
            return self.iso_path
        return self.productpath

    def productrepopath(self):
        if self.repo_path and self.productpath:
            return self.productpath + "/" + self.repo_path
        if self.repo_path:
            return self.repo_path
        return self.productpath

    def doFlavor(self, node):
        if node.attrib.get("arch",""):
            self.archs = node.attrib["arch"]
        if node.attrib.get("name",""):
            for f in node.attrib["name"].split("|"):
                self.flavors.append(f)
                if node.attrib.get("iso_5",""):
                    self.flavor_aliases[node.attrib.get("iso_5")].append(f)
                    self.iso_5 = node.attrib.get("iso_5")
                if node.attrib.get("fixed_iso",""):
                    self.fixed_iso = node.attrib["fixed_iso"]

        if node.attrib.get("iso","") and node.attrib.get("name",""):
            for iso in node.attrib["name"].split("|"):
                self.isos.append(iso)
                if node.attrib["iso"] == "extract_as_repo":
                    self.iso_extract_as_repo[iso] = 1
        for t in node.findall(".//isos/*"):
            self.isos.append(t)

        if node.attrib.get("distri",""):
            self.distri = node.attrib["distri"]
        if node.attrib.get("legacy_builds",""):
            self.legacy_builds = node.attrib["legacy_builds"]

        for t in node.findall(".//repos/*"):
            if "folder" in t.attrib:
                self.repodirs.append(t)
            else:
                self.repos.append(t)
            if t.attrib.get("mirror",""):
                self.mirror_repo = t.tag
        for t in node.findall("./alias"):
            prefix=t.attrib.get("prefix","")
            suffix=t.attrib.get("suffix","")
            suffix=suffix.replace("${version}", self.version)
            name=t.attrib.get("name","")
            for p in prefix.split("|"):
                for n in name.split("|"):
                    for s in suffix.split("|"):
                        self.flavor_aliases[node.attrib.get("name","")].append(p + n + s)
                        self.flavor_aliases_flavor.append(p + n + s)

        for t in node.findall(".//renames/*"):
            if "to" in t.attrib:
                self.renames.append([t.attrib.get("from",t.tag), t.attrib["to"]])

        for t in node.findall(".//*"):
            if t.tag == "hdd":
                self.hdds.append(t.attrib["filemask"])
            if t.tag == "asset":
                self.assets.append(t.attrib["filemask"])
            if t.tag == "repos" and t.attrib.get("build_id_from_iso",""):
                self.build_id_from_iso = 1

    def doFile(self, filename):
        tree = ElementTree.parse(filename)
        root = tree.getroot()
        self.iso_path = root.attrib.get("iso_path","")
        self.repo_path = root.attrib.get("repo_path","")
        self.domain = root.attrib.get("domain","")
        for t in root.findall(".//flavor"):
            self.doFlavor(t)

    def gen_if_not_customized(self, folder, fname):
        filename = folder + "/" + fname
        line1=""
        line2=""
        custom=0
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                line1=f.readline()
                line2=f.readline()
                if line1 and not "GENERATED" in line1:
                    if not line1.lstrip().startswith("#"):
                        custom=1
                    elif line2 and not "GENERATED" in line2:
                            custom=1
        if custom:
            print('Will not overwrite custom file: ' + filename, file=sys.stderr)
            return
        with open(filename, 'w') as f:
            if fname == "read_files.sh":
                self.gen_read_files(f)
            elif fname == "print_rsync_iso.sh":
                self.gen_print_rsync_iso(f)
            elif fname == "print_rsync_repo.sh":
                self.gen_print_rsync_repo(f)
            elif fname == "print_openqa.sh":
                self.gen_print_openqa(f)

    def media2_name(self):
        if self.brand == 'obs':
            return 'debug'

    def media3_name(self):
        if self.brand == 'obs':
            return 'source'

    def gen_read_files(self,f):
        self.p(header, f, "set -e", "set -eo pipefail")
        self.p(clear_lst, f)
        for hdd in self.hdds:
            if self.productpath.startswith('http'):
                self.p(read_files_curl, f, "ISOMASK", hdd)
            else:
                self.p(read_files_hdd, f, "ISOMASK", hdd)
        for asset in self.assets:
            self.p(read_files_hdd, f, "ISOMASK", asset)
        if self.isos:
            self.p(read_files_iso, f)
        if self.repos:
            self.p(read_files_repo, f)
            if self.build_id_from_iso:
                self.p(read_files_repo, f, "PRODUCTREPOPATH/", "PRODUCTREPOPATH/../iso/", "files_repo.lst", "files_iso_buildid.lst","Media1(.license)?$","Media1?.iso$")
            if any(repo.attrib.get(self.media2_name(),"") for repo in self.repos):
                self.p(read_files_repo, f, "Media1", "Media2", "REPOORS", '|'.join([m.attrib["name"] if "name" in m.attrib else m.tag for m in filter(lambda x: x.attrib.get(self.media2_name(),""), self.repos)]))
            if any(repo.attrib.get(self.media3_name(),"") for repo in self.repos):
                self.p(read_files_repo, f, "Media1", "Media3", "REPOORS", '|'.join([m.attrib["name"] if "name" in m.attrib else m.tag for m in filter(lambda x: x.attrib.get(self.media3_name(),""), self.repos)]))
        for repodir in self.repodirs:
            self.p(read_files_repo, f, "PRODUCTREPOPATH", self.productpath + "/*" + repodir.attrib["folder"] + "*", "REPOORS", "", "files_repo.lst", "files_repo_{}.lst".format(repodir.attrib["folder"]) )

    def gen_print_array_flavor_filter(self,f):
        if len(self.hdds) or len(self.assets) or len(self.flavor_aliases):
            self.p('declare -A flavor_filter',f)
        # this assumes every flavor has hdd_url - we must store relation if that is not the case
        for fl, h in zip(self.flavors, self.hdds):
            self.p("flavor_filter[{}]='{}'".format(fl, h), f)
        for fl, h in zip(self.flavors, self.assets):
            self.p("flavor_filter[{}]='{}'".format(fl, h), f)
        for fl, alias_list in self.flavor_aliases.items():
            for alias in alias_list:
                self.p("flavor_filter[{}]='{}'".format(alias, fl), f)

    def gen_print_rsync_iso(self,f):
        print(header, file=f)
        if self.isos or (self.hdds and not self.productpath.startswith('http')):
            self.gen_print_array_flavor_filter(f)
            self.p(rsync_iso(self.brand), f)
        if self.assets:
            self.gen_print_array_flavor_filter(f)
            self.p(rsync_iso(self.brand), f, "factory/iso", "factory/other")

    def gen_print_rsync_repo(self,f):
        print(header, file=f)
        if self.repos:
            self.p(rsync_repo1, f)
            for ren in self.renames:
                self.p("        dest=${{dest//{}/{}}}".format(ren[0],ren[1]), f)
            if self.build_id_from_iso:
                self.p('''        buildid1=$(grep $repo __envdir/files_iso_buildid.lst | grep -o 'Build[^-]*' | head -n 1)
         [ -z "$buildid1" ] || buildid=$buildid1''', f)

            self.p(rsync_repo2, f)

        for r in self.repodirs:
            self.p(rsync_repodir1, f, "mid=''", "mid='{}'".format(r.attrib.get("mid","")))
            for ren in self.renames:
                self.p("        dest=${{dest//{}/{}}}".format(ren[0],ren[1]), f)
            self.p(rsync_repodir2(self.brand), f,"PRODUCTREPOPATH", self.productpath + "/*" + r.attrib["folder"] + "*$arch*", "files_repo.lst", "files_repo_{}.lst".format(r.attrib["folder"]),"Media2","Media1","-debuginfo","","RSYNCFILTER","")
            if r.attrib.get("debug",""):
                self.p(rsync_repodir1, f, "mid=''", "mid='{}'".format(r.attrib.get("mid","")))
                for ren in self.renames:
                    self.p("        dest=${{dest//{}/{}}}".format(ren[0],ren[1]), f)
                self.p(rsync_repodir2(self.brand), f, "PRODUCTREPOPATH", self.productpath + "/*" + r.attrib["folder"] + "*$arch*", "files_repo.lst", "files_repo_{}.lst".format(r.attrib["folder"]),"RSYNCFILTER", " --include=PACKAGES --exclude={aarch64,i586,i686,noarch,nosrc,ppc64le,s390x,src,x86_64}/*".replace("PACKAGES",r.attrib["debug"]))
            if r.attrib.get("source",""):
                self.p(rsync_repodir1, f, "mid=''", "mid='{}'".format(r.attrib.get("mid","")))
                for ren in self.renames:
                    self.p("        dest=${{dest//{}/{}}}".format(ren[0],ren[1]), f)
                self.p(rsync_repodir2(self.brand), f, "PRODUCTREPOPATH", self.productpath + "/*" + r.attrib["folder"] + "*$arch*", "files_repo.lst", "files_repo_{}.lst".format(r.attrib["folder"]),"RSYNCFILTER", " --include=PACKAGES --exclude={aarch64,i586,i686,noarch,nosrc,ppc64le,s390x,src,x86_64}/*".replace("PACKAGES",r.attrib["source"]),"Media2","Media3","-debuginfo","-source")

    def gen_print_openqa(self,f):
        print(header, file=f)
        self.gen_print_array_flavor_filter(f)
        self.p(openqa_call_start(self.brand), f)
        if self.legacy_builds:
            self.p(openqa_call_legacy_builds, f)
        i=0
        if self.hdds:
            if self.productpath.startswith('http'):
                self.p(" HDD_URL_1=PRODUCTPATH/$destiso \\\\\"", f)
            else:
                self.p(" HDD_1=$destiso \\\\", f)
                self.p(" ASSET_HDD_1_SHA256=$destiso.sha256 \\\\\"", f)
        elif self.assets:
                self.p(" ASSET_1=$destiso \\\\", f)
                self.p(" ASSET_1_SHA256=$destiso.sha256 \\\\\"", f)
        else:
            if self.iso_5:
                if self.fixed_iso:
                    self.p(" ISO={} \\\\".format(self.fixed_iso), f)
                self.p(openqa_call_start_iso, f, "ISO", "ISO_5")
            else:
                self.p(openqa_call_start_iso, f)

            for iso in self.isos:
                if self.iso_extract_as_repo.get(iso,0):
                    destiso = "${destiso%.iso}"
                    i += 1
                    if not self.fixed_iso:
                        self.p(openqa_call_repo0(self.brand), f, "REPO0_ISO", destiso, f)
                    else:
                        destiso = self.fixed_iso[:-4]
                    self.p(openqa_call_repo0a, f, "REPO0_ISO", destiso, f)
                    if self.iso_5:
                        self.p(openqa_call_repo0a, f, "REPO0_ISO", "${destiso%.iso}", "REPO_0=", "REPO_5=", f)
                        self.p(openqa_call_repo0a, f, "REPO0_ISO", "${destiso%.iso}", "REPO_0=", "REPO_{}=".format(self.iso_5.replace("-","_"), f))
                    break # for now only REPO_0
        self.p(" i={}".format(i), f)

        if self.repos:
            self.p(" i=9", f) # temporary to simplify diff with old rsync scripts, may be removed later
            self.p(openqa_call_repot(self.brand, self.build_id_from_iso), f, "REPOTYPE", "''", "REPOPREFIX", "SLE_")

        for r in self.repodirs:
            self.p(openqa_call_repot1(self.brand), f, "REPOKEY", r.attrib.get("rename",r.tag),"mid=''", "mid='{}'".format(r.attrib.get("mid","")))
            for ren in self.renames:
                self.p("            dest=${{dest//{}/{}}}".format(ren[0],ren[1]), f)
            if i==0:
                self.p("            [ $i != 0 ] || {{ {};  }}".format(openqa_call_repo0(self.brand)), f, "REPO0_ISO", "$dest", f)
            media_filter = ""
            if r.attrib.get("debug","") == "" or r.attrib.get("source","") == "":
                if r.attrib.get("debug","") == "" and r.attrib.get("source","") == "":
                    media_filter = "| grep Media1 "
                elif r.attrib.get("debug","") == "":
                    media_filter = "| grep -E '(Media1|Media3)' "
                else:
                    media_filter = "| grep -E '(Media1|Media2)' "
            self.p(openqa_call_repot2.format(media_filter), f, "files_repo.lst", "files_repo_{}.lst".format(r.attrib["folder"]),"DEBUG_PACKAGES",r.attrib.get("debug","").strip('{}'),"SOURCE_PACKAGES",r.attrib.get("source","").strip('{}'))

        if self.staging():
            self.p("echo ' STAGING=__STAGING \\'", f)

        self.p(openqa_call_end(self.brand), f)

def parse_dir(root, d, files):
    for f in files:
        if not f.endswith(".xml"):
            continue

        rootXml = ElementTree.parse(root + "/" + f).getroot()
        if not rootXml:
            print("Ignoring [" + f + "]: Cannot parse xml", file=sys.stderr)
            continue

        pattern = rootXml.attrib.get("project_pattern","")
        if not pattern:
            print("Ignoring [" + f + "]: Cannot find attribute project_pattern", file=sys.stderr)
            continue

        try:
            r = re.compile(pattern)
        except Exception as e:
            print("Ignoring [" + f + "]: Regexp error: " + str(e), file=sys.stderr)
            continue

        found_match = r.match(os.path.basename(d))
        if not found_match or found_match.group(0) != os.path.basename(d):
            # if found_match and found_match.group(0):
            #    print("OBS: no match [" + found_match.group(0) , file=sys.stderr)
            # print("OBS: no match [" + d + "] for " + r.pattern,file=sys.stderr)
            continue
        version = found_match.groupdict().get("version","")
        if version.find("'") != -1:
            print("OBS: Ignoring [" + d + "]: Version cannot contain quote characters; got: " + version, file=sys.stderr)
            continue

        dist_path = rootXml.attrib.get("dist_path","")
        if dist_path.find('"') != -1:
            print("OBS: Ignoring [" + d + "]: dist_path cannot contain quote characters; got: " + dist_path, file=sys.stderr)
            continue
        if dist_path.find('`') != -1:
            print("OBS: Ignoring [" + d + "]: dist_path cannot contain backtick characters; got: " + dist_path, file=sys.stderr)
            continue
        if dist_path.find("$(") != -1:
            print("OBS: Ignoring [" + d + "]: dist_path cannot contain '$(' characters; got: " + dist_path, file=sys.stderr)
            continue

        myenv = os.environ.copy()
        for k, v in found_match.groupdict().items():
            if v and v.find("'") == -1:
                myenv[k] = v
        try:
            output = check_output(["echo " + dist_path], shell=True, executable="/bin/bash", env=myenv).decode()
            success = True
        except CalledProcessError as e:
            output = e.output.decode()
            success = False

        if not success:
            print("OBS: Ignoring [" + d + "]: Error trying to determine dist_path")
            continue

        dist_path = output.rstrip("\r\n")

        return (root + "/" + f, dist_path, version)

    return ("", "", "")

def gen_files(project):
    xmlfile=""
    folder = project
    subfolder = ""

    folders = project.rstrip('/').split('/')

    # a hack for tests, don't have better solution for now
    if len(folders)>1 and folders[0] == "t":
        folders.pop(0)

    if len(folders) > 2:
        print('Only one level is allowed in path', file=sys.stderr)
        return 1

    if len(folders)>0:
        folder = folders[0]
    if len(folders)>1:
        subfolder = folders[1]

    for root, _, files in os.walk("xml/obs"):
        (xmlfile, dist_path, version) = parse_dir(root, folder, files)
    if not xmlfile:
        print('Cannot find xml file for {} ...'.format(folder), file=sys.stderr)
        return 1

    a = ActionGenerator(os.getcwd() +"/"+ project, dist_path, version, 'obs', subfolder)
    if a is None:
        print('Couldnt initialize', file=sys.stderr)
        sys.exit(1)

    a.doFile(xmlfile)

    a.gen_if_not_customized(project, "read_files.sh")
    a.gen_if_not_customized(project, "print_rsync_iso.sh")
    a.gen_if_not_customized(project, "print_rsync_repo.sh")
    a.gen_if_not_customized(project, "print_openqa.sh")

    return 0

if __name__ == '__main__':
    # execute only if run as the entry point into the program
    parser = argparse.ArgumentParser(description='Generate scripts for OBS project synchronization according to XML definition.')
    parser.add_argument('project', nargs='?', help='Folder matching OBS project')

    class Args:
        pass

    args = Args()
    parser.parse_args(namespace=args)

    ret=1

    if args.project:
        print("Generating scripts for " + args.project)
        ret=gen_files(args.project)
        if ret == 0:
            print("OK")

    sys.exit(ret)
