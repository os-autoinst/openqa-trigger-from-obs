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

clear_lst = '''for f in __envsub/files_*.lst; do
    [ ! -f "$f" ] ||  : > "$f"
done

[ ! -f __envdir/../rsync.secret ] || rsync_pwd_option=--password-file=__envdir/../rsync.secret
'''

read_files_curl = '''curl -s PRODUCTPATH/ | grep -o 'ISOMASK' | head -n 1 >> __envsub/files_iso.lst'''

read_files_hdd = '''rsync --list-only $rsync_pwd_option PRODUCTPATH/FOLDER/ | grep -o 'ISOMASK' | awk '{ $1=$2=$3=$4=""; print substr($0,5); }' | head -n 1 >> __envsub/files_iso.lst
'''

read_files_iso = '''rsync --list-only $rsync_pwd_option PRODUCTISOPATH/FOLDER/*SRCISO* | grep -P 'Media1?.iso$' | awk '{ $1=$2=$3=$4=""; print substr($0,5); }' >> __envsub/files_iso.lst
'''

read_files_isos = '''rsync --list-only $rsync_pwd_option PRODUCTISOPATH/ | grep -P 'Media1?.iso$' | grep -E 'ARCHORS' | awk '{ $1=$2=$3=$4=""; print substr($0,5); }' >> __envsub/files_iso.lst
'''

read_files_repo = '''rsync --list-only $rsync_pwd_option PRODUCTREPOPATH/ | grep -P 'Media[1-3](.license)?$' | awk '{ $1=$2=$3=$4=""; print substr($0,5); } ' | grep -v IGNOREPATTERN | grep -E 'REPOORS' | grep -E 'ARCHORS'  >> __envsub/files_repo.lst
'''

read_files_repo_link = '''cp __envdir/REPOLINK/files_repo*.lst __envsub/
'''

read_files_repo_link2 = '''cp __envdir/REPOLINK/files_iso*.lst __envsub/
'''

def rsync_iso_staging(brand, version, staging):
    if not staging: return ''
    if brand == 'obs' and version != 'Factory' and len(staging) == 1: return '''dest=${dest//$flavor/Staging:__STAGING-Staging-$flavor}'''
    if brand == 'obs': return '''dest=${dest//$flavor/Staging:__STAGING-$flavor}'''

def rsync_iso_fix_src(brand, archs):
    if 'armv7hl' in archs and not 'armv7l' in archs:
        return '[ -n "$src" ] || [ "$arch" != armv7hl ] || src=$(grep "$filter" __envsub/files_iso.lst | grep armv7l | head -n 1)'
    return ''

rsync_iso = lambda brand, version, archs, staging : '''
archs=(ARCHITECTURS)

for flavor in {FLAVORLIST,}; do
    for arch in "${archs[@]}"; do
        filter=$flavor
        [[ ! -v flavor_filter[@] ]] || [ -z "${flavor_filter[$flavor]}" ] || filter=${flavor_filter[$flavor]}
        src=$(grep "$filter" __envsub/files_iso.lst | grep $arch | head -n 1)
        ''' + rsync_iso_fix_src(brand, archs) + '''
        [ ! -z "$src" ] || continue
        dest=$src
        ''' + rsync_iso_staging(brand, version, staging) + '''
        echo "rsync --timeout=3600 PRODUCTISOPATH/${iso_folder[$flavor]}*$src /var/lib/openqa/factory/iso/$dest"
        echo "rsync --timeout=3600 PRODUCTISOPATH/${iso_folder[$flavor]}*$src.sha256 /var/lib/openqa/factory/other/$dest.sha256"

        [ -z "FLAVORASREPOORS" ] || [ $( echo "$flavor" | grep -E -c "^(FLAVORASREPOORS)$" ) -eq 0 ] || echo "[ -d /var/lib/openqa/factory/repo/${dest%.iso} ] || {
    mkdir /var/lib/openqa/factory/repo/${dest%.iso}
    bsdtar xf /var/lib/openqa/factory/iso/$dest -C /var/lib/openqa/factory/repo/${dest%.iso}
}"
    done
done'''

rsync_repo1 = '''
echo '# REPOLIST'
buildid=$(cat __envsub/files_iso.lst | grep -E 'FLAVORORS' | grep -o -E '(Build|Snapshot)[^-]*' | head -n 1)
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
    done < <(grep $repo-POOL __envsub/files_repo.lst)
done
'''

rsync_repodir1 = '''
archs=(ARCHITECTURREPO)
buildid=$(cat __envsub/files_iso.lst | grep -E 'FLAVORORS' | grep -o -E '(Build|Snapshot)[^-]*' | head -n 1)

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
    done < <(grep ${arch//i686/i586} __envsub/files_repo.lst | grep Media2)
done
'''

rsync_repodir1_dest = lambda dest: '''
archs=(ARCHITECTURREPO)
buildid=$(cat __envsub/files_iso.lst | grep -E 'FLAVORORS' | grep -o -E '(Build|Snapshot)[^-]*' | head -n 1)

for arch in "${archs[@]}"; do
    while read src; do
        [ ! -z "$src" ] || continue
        dest=''' + dest


def openqa_call_start_staging(brand, version, staging):
    if not staging:
        return ''
    if brand == 'obs' and (version == 'Factory' or len(staging)>1): return '''destiso=${iso//$flavor/Staging:__STAGING-$flavor}
        flavor=Staging-$flavor'''
    if brand == 'obs': return '''version=${version}:S:__STAGING
        destiso=${iso//$flavor/Staging:__STAGING-Staging-$flavor}
        flavor=Staging-$flavor'''

def openqa_call_start_fix_iso(brand, archs):
    if 'armv7hl' in archs and not 'armv7l' in archs:
        return '[ -n "$iso" ] || [ "$arch" != armv7hl ] || iso=$(grep "$filter" __envsub/files_iso.lst | grep armv7l | head -n 1)'
    return ''

openqa_call_start = lambda brand, version, archs, staging: '''
archs=(ARCHITECTURS)

for flavor in {FLAVORALIASLIST,}; do
    for arch in "${archs[@]}"; do
        filter=$flavor
        [[ ! -v flavor_filter[@] ]] || [ -z "${flavor_filter[$flavor]}" ] || filter=${flavor_filter[$flavor]}
        [ $filter != Appliance ] || filter="qcow2"
        iso=$(grep "$filter" __envsub/files_iso.lst | grep $arch | head -n 1)
        ''' + openqa_call_start_fix_iso(brand, archs) + '''
        build=$(echo $iso | grep -o -E '(Build|Snapshot)[^-]*' | grep -o -E '[0-9]+.?[0-9]+(\.[0-9]+)?') || continue
        buildex=$(echo $iso | grep -o -E '(Build|Snapshot)[^-]*')
        build1=$build
        destiso=$iso
        version=VERSIONVALUE
        [ -z "__STAGING" ] || build1=__STAGING.$build
        ''' + openqa_call_start_staging(brand, version, staging) + '''
        [ ! -z "$build"  ] || continue
        [ "$arch" != . ] || arch=x86_64

        echo "/usr/share/openqa/script/client isos post --host localhost \\\\\"
(
 echo \" _OBSOLETE=1
 DISTRI=DISTRIVALUE \\\\
 ARCH=$arch \\\\
 VERSION=$version \\\\
 BUILD=$build1 \\\\\"'''

openqa_call_legacy_builds_link=''' build1=$(grep -o -E '(Build|Snapshot)[^-]*' __envdir/REPOLINK/files_iso.lst | grep -o -E '[0-9]+.?[0-9]+(\.[0-9]+)?' | head -n1)
'''

openqa_call_legacy_builds=''' echo \" BUILD_HA=$build1 \\\\
 BUILD_SDK=$build1 \\\\
 BUILD_SES=$build1 \\\\
 BUILD_SLE=$build1 \\\\\"'''

openqa_call_start_iso = ''' echo \" ISO=${destiso} \\\\
 CHECKSUM_ISO=\$(head -c 113 /var/lib/openqa/factory/other/${destiso}.sha256 | tail -c 64) \\\\
 ASSET_ISO_SHA256=${destiso}.sha256 \\\\\"'''

openqa_call_start_ex = ''' if [[ $destiso =~ \.iso$ ]]; then
   echo \" ISO=${destiso} \\\\
 CHECKSUM_ISO=\$(head -c 113 /var/lib/openqa/factory/other/${destiso}.sha256 | tail -c 64) \\\\
 ASSET_ISO_SHA256=${destiso}.sha256 \\\\\"
 elif [[ $destiso =~ \.(hdd|qcow2|raw\.xz|raw\.gz)$ ]]; then
   echo \" HDD_1=${destiso} \\\\
 CHECKSUM_HDD_1=\$(head -c 113 /var/lib/openqa/factory/other/${destiso}.sha256 | tail -c 64) \\\\
 ASSET_HDD_1_SHA256=${destiso}.sha256 \\\\\"
 else
   echo \" ASSET_1=${destiso} \\\\
 CHECKSUM_ASSET_1=\$(head -c 113 /var/lib/openqa/factory/other/${destiso}.sha256 | tail -c 64) \\\\
 ASSET_1_SHA256=${destiso}.sha256 \\\\\"
 fi
'''

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
    return '''build2=$(grep $repot __envsub/files_iso_buildid.lst | grep $arch | grep -o -E '(Build|Snapshot)[^-]*' | grep -o -E '[0-9]+.?[0-9]+(\.[0-9]+)?' | head -n 1)
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
            done < <(grep $repot-POOL __envsub/files_repo.lst | grep REPOTYPE | grep $arch | sort)
        done'''

def openqa_call_repot1_debugsource(brand):
    if brand == 'obs': return '''[[ $src != *Media2* ]] || repoKey=${repoKey}_DEBUGINFO
            [[ $src != *Media2* ]] || dest=$dest-debuginfo
            [[ $src != *Media3* ]] || repoKey=${repoKey}_SOURCE
            [[ $src != *Media3* ]] || dest=$dest-source'''

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
            [[ $src =~ license ]] || echo " REPO_$repoKey=$dest \\\\"
            [[ ! $repoKey =~ _DEBUGINFO ]] || [ -z "DEBUG_PACKAGES" ] || echo " REPO_${{repoKey}}_PACKAGES='DEBUG_PACKAGES' \\\\"
            [[ ! $repoKey =~ _SOURCE ]] || [ -z "SOURCE_PACKAGES" ] || echo " REPO_${{repoKey}}_PACKAGES='SOURCE_PACKAGES' \\\\"
            : $((i++))
        done < <(grep ${{arch//i686/i586}} __envsub/files_repo.lst {} | sort)'''


openqa_call_repot1_dest = lambda brand, dest: '''
        while read src; do
            dest=''' + dest + '''-$buildex
            repoKey=REPOKEY
            ''' + openqa_call_repot1_debugsource(brand) + '''
            repoKey=${repoKey^^}
            repoKey=${repoKey//-/_}
'''

def openqa_call_end(brand, version):
    if version == 'Factory': return '''
        [ $flavor != MicroOS-DVD ] || flavor=DVD
        echo " FLAVOR=${flavor//Tumbleweed-/} \\\\"
) | LC_COLLATE=C sort
        echo ""
    done
done
'''
    if brand == 'obs': return '''
        echo " FLAVOR=$flavor \\\\"
) | LC_COLLATE=C sort
        echo ""
    done
done
'''

class ActionGenerator:
    def __init__(self, envdir, productpath, version, brand):
        self.brand = brand
        self.envdir = envdir
        self.productpath = productpath
        self.distri = ""
        self.version = version
        self.batches = []

    def staging(self):
        m = re.match(r'.*Staging:(?P<staging>[A-Z]).*', self.envdir)
        if m:
            return m.groupdict().get("staging","")
        m = re.match(r'.*Rings:(?P<ring>[0-9]).*', self.envdir)
        if m:
            return "Core"
        return ""

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

    def doFile(self, filename):
        tree = ElementTree.parse(filename)
        root = tree.getroot()
        self.iso_path = root.attrib.get("iso_path","")
        self.repo_path = root.attrib.get("repo_path","")
        self.domain = root.attrib.get("domain","")
        if root.attrib.get("distri", ""):
            self.distri = root.attrib["distri"]

        for t in root.findall(".//batch"):
            batch = self.doBatch(t)
            if batch:
                for flavor in t.findall(".//flavor"):
                    batch.doFlavor(flavor)

        if not len(self.batches):
            batches_string = root.attrib.get("batches","default")
            for b in batches_string.split('|'):
                batch = self.doBatch(root, b)
                if batch:
                    for flavor in root.findall(".//flavor"):
                        batch.doFlavor(flavor)
 
    def doBatch(self, node, name=None):
        if not name:
            name = node.attrib.get("name","")
        if not name:
            print('Batch node has no name attribute', file=sys.stderr)
            return
        batch = ActionBatch(name, self)
        if node.attrib.get("repos",""):
            batch.repolink = node.attrib["repos"]
        if node.attrib.get("folder",""):
            batch.folder = node.attrib["folder"]
        if node.attrib.get("archs",""):
            batch.archs = node.attrib["archs"]
        if node.attrib.get("mask",""):
            batch.mask = node.attrib["mask"]
        if node.attrib.get("distri",""):
            batch.distri = node.attrib["distri"]
        self.batches.append(batch)
        return batch

    def defaultBatch(self):
        batch = ActionBatch("default", self)
        self.batches.append(batch)
        return batch

    def batch_by_name(self, name):
        return next((x for x in self.batches if x.subfolder == name), None)

class ActionBatch:
    def __init__(self, name, actionGenerator):
        self.subfolder = name
        self.ag = actionGenerator
        self.archs = "aarch64 ppc64le s390x x86_64"
        self.archs_repo = ""
        self.flavors = []
        self.flavor_aliases = defaultdict(list)
        self.flavor_aliases_flavor = []
        self.hdds = []
        self.assets = []
        self.isos = []
        self.iso_folder = {}
        self.iso_5 = ""
        self.fixed_iso = ""
        self.mask = ""
        self.iso_extract_as_repo = {}
        self.mirror_repo = ""
        self.repos = []
        self.repolink = ""
        self.build_id_from_iso = 0
        self.repodirs = []
        self.renames = []
        self.distri = actionGenerator.distri
        self.iso_path = ""
        self.repo_path = ""
        self.folder = ""
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
        xtrapath = "";
        if self.folder:
            xtrapath = "/" + self.folder
        s=s.replace('PRODUCTPATH', self.ag.productpath + xtrapath)
        s=s.replace('PRODUCTISOPATH', self.ag.productisopath() + xtrapath)
        s=s.replace('PRODUCTREPOPATH', self.ag.productrepopath() + xtrapath)
        if self.subfolder and self.subfolder != 'default':
            s=s.replace('__envsub', self.ag.envdir +'/'+ self.subfolder)
        else:
            s=s.replace('__envsub', self.ag.envdir)
        s=s.replace('__envdir', self.ag.envdir)
        if self.ag.version.startswith("15.") and self.ag.staging() == 'Core':
            s=s.replace('VERSIONVALUE', self.ag.version + ":Core")
        elif self.subfolder and self.subfolder != 'default' and not self.ag.version:
            s=s.replace('VERSIONVALUE', self.subfolder.lstrip('Leap_'))
        elif self.ag.staging() and self.ag.version == 'Factory':
            s=s.replace('VERSIONVALUE', 'Staging:' + self.ag.staging())
        else:
            s=s.replace('VERSIONVALUE', self.ag.version.replace('Factory','Tumbleweed'))
        s=s.replace("DISTRIVALUE", self.distri)
        s=s.replace("__STAGING", self.ag.staging())
        s=s.replace("ARCHITECTURS", self.archs)
        if self.archs_repo:
            s=s.replace("ARCHITECTURREPO", self.archs_repo)
        else:
            s=s.replace("ARCHITECTURREPO", self.archs)
        s=s.replace("ARCHORS", self.archs.replace(" ","|"))
        s=s.replace("SUBFOLDER", self.subfolder)

        if self.flavors or self.flavor_aliases_flavor:
            s=s.replace("FLAVORLIST",','.join(self.flavors))
            aliases = copy.deepcopy(self.flavors)
            aliases.extend(self.flavor_aliases_flavor)
            s=s.replace("FLAVORORS", '|'.join(self.flavors))
            s=s.replace("FLAVORALIASLIST",','.join(aliases))
            s=s.replace("FLAVORASREPOORS", '|'.join([f for f in self.flavors if self.iso_extract_as_repo.get(f,0)]))


        if self.repos or self.repolink:
            repos = self.repos
            if not repos:
                repos = self.ag.batch_by_name(self.repolink).repos
            s=s.replace("REPOLIST",  ','.join([m.attrib["name"] if "name" in m.attrib else m.tag for m in repos]))
            s=s.replace("REPOORS",   '|'.join([m.attrib["name"] if "name" in m.attrib else m.tag for m in repos]))
        s=s.replace("MIRRORREPO", self.mirror_repo)
        if self.ag.domain:
            s=s.replace("opensuse.org",self.ag.domain)
        s=s.replace("REPOLINK", self.repolink)
        print(s, file=f)

    def doFlavor(self, node):
        if node.attrib.get("archs",""):
            self.archs = node.attrib["archs"]
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
                if node.attrib.get("folder",""):
                    self.iso_folder[iso] = node.attrib["folder"]
                if node.attrib["iso"] == "extract_as_repo":
                    self.iso_extract_as_repo[iso] = 1

        if node.attrib.get("name","") and node.attrib.get("folder",""):
            self.iso_folder[node.attrib["name"]] = node.attrib["folder"]

        for t in node.findall(".//isos/*"):
            self.isos.append(t.tag)

        if node.attrib.get("distri",""):
            self.distri = node.attrib["distri"]
        if node.attrib.get("legacy_builds",""):
            self.legacy_builds = node.attrib["legacy_builds"]


        for t in node.findall(".//repos"):
            if t.attrib.get("archs",""):
                self.archs_repo = t.attrib["archs"]

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
            suffix=suffix.replace("${version}", self.ag.version)
            name=t.attrib.get("name","")
            for p in prefix.split("|"):
                for n in name.split("|"):
                    for s in suffix.split("|"):
                        self.flavor_aliases[t.attrib.get("alias","")].append(p + n + s)
                        self.flavor_aliases_flavor.append(p + n + s)

        for t in node.findall(".//renames/*"):
            if "to" in t.attrib:
                self.renames.append([t.attrib.get("from",t.tag), t.attrib["to"]])

        for t in node.findall(".//*"):
            if t.tag == "hdd":
                self.hdds.append(t.attrib["filemask"])
                if node.attrib.get("folder",""):
                    self.iso_folder[t.attrib["filemask"]] = node.attrib["folder"]
            if t.tag == "asset":
                self.assets.append(t.attrib["filemask"])
            if t.tag == "repos" and t.attrib.get("build_id_from_iso",""):
                self.build_id_from_iso = 1

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
        if self.ag.brand == 'obs':
            return 'debug'

    def media3_name(self):
        if self.ag.brand == 'obs':
            return 'source'

    def gen_read_files(self,f):
        self.p(header, f, "set -e", "set -eo pipefail")
        self.p(clear_lst, f)
        for hdd in self.hdds:
            if self.ag.productpath.startswith('http'):
                self.p(read_files_curl, f, "ISOMASK", hdd)
            else:
                if ' ' in self.archs:
                    self.p(read_files_hdd, f, "FOLDER", self.iso_folder.get(hdd,""), "ISOMASK", hdd, '| head -n 1', '')
                else:
                    self.p(read_files_hdd, f, "FOLDER", self.iso_folder.get(hdd,""), "ISOMASK", hdd)
        for asset in self.assets:
            self.p(read_files_hdd, f, "FOLDER", "", "ISOMASK", asset)
        if self.isos:
            # if isos don't belong to custom folder - just read them all with single command
            if not self.iso_folder:
                self.p(read_files_isos, f)
            else:
                for iso in self.isos:
                    self.p(read_files_iso, f, "FOLDER", self.iso_folder.get(iso,""), "SRCISO", iso)

        if self.repolink:
            self.p(read_files_repo_link, f)
        if self.repolink and not self.isos and not self.assets and not self.hdds:
            self.p(read_files_repo_link2, f)
        if self.repos:
            self.p(read_files_repo, f)
            if self.build_id_from_iso:
                self.p(read_files_repo, f, "PRODUCTREPOPATH/", "PRODUCTREPOPATH/../iso/", "files_repo.lst", "files_iso_buildid.lst","Media1(.license)?$","Media1?.iso$")
            if any(repo.attrib.get(self.media2_name(),"") for repo in self.repos):
                self.p(read_files_repo, f, "Media1", "Media2", "REPOORS", '|'.join([m.attrib["name"] if "name" in m.attrib else m.tag for m in filter(lambda x: x.attrib.get(self.media2_name(),""), self.repos)]))
            if any(repo.attrib.get(self.media3_name(),"") for repo in self.repos):
                self.p(read_files_repo, f, "Media1", "Media3", "REPOORS", '|'.join([m.attrib["name"] if "name" in m.attrib else m.tag for m in filter(lambda x: x.attrib.get(self.media3_name(),""), self.repos)]))
        for repodir in self.repodirs:
            self.p(read_files_repo, f, "PRODUCTREPOPATH", self.ag.productpath + "/" + self.folder + "/*" + repodir.attrib["folder"] + "*", "REPOORS", "", "files_repo.lst", "files_repo_{}.lst".format(repodir.attrib["folder"]) )

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

    def gen_print_array_iso_folder(self,f):
        if len(self.iso_folder):
            self.p('declare -A iso_folder',f)
        for k, v in self.iso_folder.items():
            self.p("iso_folder[{}]='{}/'".format(k, v), f)

    def gen_print_rsync_iso(self,f):
        print(header, file=f)
        if self.isos or (self.hdds and not self.ag.productpath.startswith('http')):
            self.gen_print_array_flavor_filter(f)
            self.gen_print_array_iso_folder(f)
            if self.mask:
                self.p(rsync_iso(self.ag.brand, self.ag.version, self.archs, self.ag.staging()), f, '| head -n 1', '| grep {} | head -n 1'.format(self.mask))
            else:
                self.p(rsync_iso(self.ag.brand, self.ag.version, self.archs, self.ag.staging()), f)
        if self.assets:
            self.gen_print_array_flavor_filter(f)
            self.p(rsync_iso(self.ag.brand, self.ag.version, self.archs, self.ag.staging()), f, "factory/iso", "factory/other")

    def gen_print_rsync_repo(self,f):
        print(header, file=f)
        if self.repos:
            self.p(rsync_repo1, f)
            for ren in self.renames:
                self.p("        dest=${{dest//{}/{}}}".format(ren[0],ren[1]), f)
            if self.build_id_from_iso:
                self.p('''        buildid1=$(grep $repo __envsub/files_iso_buildid.lst | grep -o -E '(Build|Snapshot)[^-]*' | head -n 1)
         [ -z "$buildid1" ] || buildid=$buildid1''', f)

            self.p(rsync_repo2, f)

        xtrapath = ""
        if self.folder:
            xtrapath = "/" + self.folder
        for r in self.repodirs:
            if not r.attrib.get("dest", ""):
                self.p(rsync_repodir1, f, "mid=''", "mid='{}'".format(r.attrib.get("mid","")))
            else:
                self.p(rsync_repodir1_dest(r.attrib["dest"]), f)

            for ren in self.renames:
                self.p("        dest=${{dest//{}/{}}}".format(ren[0],ren[1]), f)
            self.p(rsync_repodir2(self.ag.brand), f,"PRODUCTREPOPATH", self.ag.productpath + xtrapath + "/*" + r.attrib["folder"] + "*$arch*", "files_repo.lst", "files_repo_{}.lst".format(r.attrib["folder"]),"Media2","Media1","-debuginfo","","RSYNCFILTER","")
            if r.attrib.get("debug",""):
                if not r.attrib.get("dest", ""):
                    self.p(rsync_repodir1, f, "mid=''", "mid='{}'".format(r.attrib.get("mid","")))
                else:
                    self.p(rsync_repodir1_dest(r.attrib["dest"]), f)
                for ren in self.renames:
                    self.p("        dest=${{dest//{}/{}}}".format(ren[0],ren[1]), f)
                self.p(rsync_repodir2(self.ag.brand), f, "PRODUCTREPOPATH", self.ag.productpath + xtrapath + "/*" + r.attrib["folder"] + "*$arch*", "files_repo.lst", "files_repo_{}.lst".format(r.attrib["folder"]),"RSYNCFILTER", " --include=PACKAGES --exclude={aarch64,i586,i686,noarch,nosrc,ppc64le,s390x,src,x86_64}/*".replace("PACKAGES",r.attrib["debug"]))
            if r.attrib.get("source",""):
                if not r.attrib.get("dest", ""):
                    self.p(rsync_repodir1, f, "mid=''", "mid='{}'".format(r.attrib.get("mid","")))
                else:
                    self.p(rsync_repodir1_dest(r.attrib["dest"]), f)
                for ren in self.renames:
                    self.p("        dest=${{dest//{}/{}}}".format(ren[0],ren[1]), f)
                if self.ag.brand == 'obs':
                    self.p(rsync_repodir2(self.ag.brand), f, "PRODUCTREPOPATH", self.ag.productpath + xtrapath + "/*" + r.attrib["folder"] + "*$arch*", "files_repo.lst", "files_repo_{}.lst".format(r.attrib["folder"]),"RSYNCFILTER", " --include=PACKAGES --exclude={aarch64,i586,i686,noarch,nosrc,ppc64le,s390x,src,x86_64}/*".replace("PACKAGES",r.attrib["source"]),"Media2","Media3","-debuginfo","-source")

    def gen_print_openqa(self,f):
        print(header, file=f)
        self.gen_print_array_flavor_filter(f)
        if self.mask:
            self.p(openqa_call_start(self.ag.brand, self.ag.version, self.archs, self.ag.staging()), f, '| grep $arch | head -n 1', '| grep {} | grep $arch | head -n 1'.format(self.mask))
        else:
            self.p(openqa_call_start(self.ag.brand, self.ag.version, self.archs, self.ag.staging()), f)
        if self.repolink:
            self.p(openqa_call_legacy_builds_link, f)
        if self.legacy_builds:
            self.p(openqa_call_legacy_builds, f)

        i=0
        if self.hdds or self.assets:
            if self.hdds and self.ag.productpath.startswith('http'):
                self.p(" echo \" HDD_URL_1=PRODUCTPATH/$destiso \\\\\"", f)
            else:
                self.p(openqa_call_start_ex, f)
        else:
            if self.iso_5:
                if self.fixed_iso:
                    self.p(" echo \" ISO={} \\\\\"".format(self.fixed_iso), f)
                self.p(openqa_call_start_iso, f, "ISO", "ISO_5")
            else:
                self.p(openqa_call_start_iso, f)

            for iso in self.isos:
                if self.iso_extract_as_repo.get(iso,0):
                    destiso = "${destiso%.iso}"
                    i += 1
                    if not self.fixed_iso:
                        self.p(openqa_call_repo0(self.ag.brand), f, "REPO0_ISO", destiso, f)
                    else:
                        destiso = self.fixed_iso[:-4]
                    self.p(openqa_call_repo0a, f, "REPO0_ISO", destiso, f)
                    if self.iso_5:
                        self.p(openqa_call_repo0a, f, "REPO0_ISO", "${destiso%.iso}", "REPO_0=", "REPO_5=", f)
                        self.p(openqa_call_repo0a, f, "REPO0_ISO", "${destiso%.iso}", "REPO_0=", "REPO_{}=".format(self.iso_5.replace("-","_"), f))
                    break # for now only REPO_0
        self.p(" i={}".format(i), f)

        if self.repos or self.repolink:
            # self.p(" i=9", f) # temporary to simplify diff with old rsync scripts, may be removed later
            self.p(openqa_call_repot(self.ag.brand, self.build_id_from_iso), f, "REPOTYPE", "''", "REPOPREFIX", "SLE_")

        repodirs = self.repodirs
        if not repodirs and self.repolink:
            repodirs = self.ag.batch_by_name(self.repolink).repodirs

        for r in repodirs:
            if r.attrib.get("dest","") == "":
                self.p(openqa_call_repot1(self.ag.brand), f, "REPOKEY", r.attrib.get("rename",r.tag),"mid=''", "mid='{}'".format(r.attrib.get("mid","")))
            else:
                self.p(openqa_call_repot1_dest(self.ag.brand, r.attrib["dest"]), f, "REPOKEY", r.attrib.get("rename",r.tag))

            for ren in self.renames:
                self.p("            dest=${{dest//{}/{}}}".format(ren[0],ren[1]), f)
            if i==0:
                self.p("            [ $i != 0 ] || {{ {};  }}".format(openqa_call_repo0(self.ag.brand)), f, "REPO0_ISO", "$dest", f)
            media_filter = ""
            if r.attrib.get("debug","") == "" or r.attrib.get("source","") == "":
                if r.attrib.get("debug","") == "" and r.attrib.get("source","") == "":
                    media_filter = "| grep Media1 "
                elif r.attrib.get("debug","") == "":
                    media_filter = "| grep -E '(Media1|Media3)' "
                else:
                    media_filter = "| grep -E '(Media1|Media2)' "
            self.p(openqa_call_repot2.format(media_filter), f, "files_repo.lst", "files_repo_{}.lst".format(r.attrib["folder"]),"DEBUG_PACKAGES",r.attrib.get("debug","").strip('{}'),"SOURCE_PACKAGES",r.attrib.get("source","").strip('{}'))

        if self.ag.staging():
            self.p("echo ' STAGING=__STAGING \\'", f)

        self.p(openqa_call_end(self.ag.brand, self.ag.version), f)

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
    project = project.rstrip('/')
    xmlfile=""

    for root, _, files in os.walk("xml/obs"):
        (xmlfile, dist_path, version) = parse_dir(root, project, files)

    if not xmlfile:
        print('Cannot find xml file for {} ...'.format(project), file=sys.stderr)
        return 1

    a = ActionGenerator(os.getcwd() +"/"+ project, dist_path, version, 'obs')
    if a is None:
        print('Couldnt initialize', file=sys.stderr)
        sys.exit(1)

    a.doFile(xmlfile)

    for batch in a.batches:
        path = project
        if batch.subfolder != "default":
            path = project +"/"+ batch.subfolder
            if not os.path.exists(path):
                os.mkdir(path)
        batch.gen_if_not_customized(path, "read_files.sh")
        batch.gen_if_not_customized(path, "print_rsync_iso.sh")
        batch.gen_if_not_customized(path, "print_rsync_repo.sh")
        batch.gen_if_not_customized(path, "print_openqa.sh")

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
