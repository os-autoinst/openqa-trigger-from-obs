import sys
import os
import re
from subprocess import check_output, CalledProcessError, STDOUT
import argparse
from contextlib import suppress
from xml.etree import ElementTree

p = '''# GENERATED FILE - DO NOT EDIT 
set -e
'''

clear_iso = ''': > __envdir/files_iso.lst'''
clear_repo = '''
for f in __envdir/files_repo*.lst; do
    [ ! -f "$f" ] ||  : > "$f"
done
'''

read_files_curl = '''curl -s PRODUCTPATH/ | grep -o 'ISOMASK' | head -n 1 >> __envdir/files_iso.lst'''

read_files_hdd = '''rsync --list-only PRODUCTPATH/ | grep -o 'ISOMASK' | awk '{ $1=$2=$3=$4=""; print substr($0,5); }' | head -n 1 >> __envdir/files_iso.lst'''

read_files_iso = '''rsync --list-only PRODUCTISOPATH/ | grep -P 'Media1?.iso$' | awk '{ $1=$2=$3=$4=""; print substr($0,5); }' >> __envdir/files_iso.lst
( exit ${PIPESTATUS[0]} )'''

read_files_repo = '''rsync --list-only PRODUCTREPOPATH/ | grep -P 'Media[1-3]?(.license)?$' | awk '{ $1=$2=$3=$4=""; print substr($0,5); } ' | grep -v IGNOREPATTERN | grep -E 'REPOORS'  >> __envdir/files_repo.lst
( exit ${PIPESTATUS[0]} )'''

rsync_iso = '''
archs=(aarch64 ppc64le s390x x86_64)

for flavor in {FLAVORLIST,}; do
    for arch in "${archs[@]}"; do
        src=$(grep $flavor __envdir/files_iso.lst | grep $arch | head -n 1)
        [ ! -z "$src" ] || continue
        dest=$src
        [ -z "__STAGING" ] || dest=${dest//$flavor/Staging:__STAGING-Staging-$flavor}
        echo "rsync --timeout=3600 PRODUCTISOPATH/*$src /var/lib/openqa/factory/iso/$dest"
        echo "rsync --timeout=3600 PRODUCTISOPATH/*$src.sha256 /var/lib/openqa/factory/iso/$dest.sha256"
    done
done'''

rsync_repo1 = '''
archs=(aarch64 ppc64le s390x x86_64)
buildid=$(cat __envdir/files_iso.lst | grep -E 'FLAVORORS' | grep -o 'Build[^-]*' | head -n 1)

for arch in "${archs[@]}"; do
    while read src; do
        [ ! -z "$src" ] || continue
        dest=$src
        destPrefix=${dest%$arch*}
        destSuffix=${dest#$destPrefix}
        mid=''
        dest=$destPrefix$mid$destSuffix'''

rsync_repodir2 = '''
        dest=${dest//-Media2/}
        echo rsync --timeout=3600 -r RSYNCFILTER PRODUCTREPOPATH/*Media2/*  /var/lib/openqa/factory/repo/$dest-CURRENT-debuginfo/
        echo rsync --timeout=3600 -r --link-dest /var/lib/openqa/factory/repo/$dest-CURRENT-debuginfo/ /var/lib/openqa/factory/repo/$dest-CURRENT-debuginfo/ /var/lib/openqa/factory/repo/$dest-$buildid-debuginfo
    done < <(grep $arch __envdir/files_repo.lst | grep Media2)
done
'''

openqa_call_start = '''
archs=(aarch64 ppc64le s390x x86_64)

for flavor in {FLAVORLIST,}; do
    for arch in "${archs[@]}"; do
        filter=$flavor
        [ $filter != Appliance ] || filter="qcow2"
        iso=$(grep "$filter" __envdir/files_iso.lst | grep $arch | head -n 1)
        build=$(echo $iso | grep -o -E '(Build|Snapshot)[^-]*' | grep -o -E '[0-9]+.?[0-9]+') || continue
        build1=$build
        destiso=$iso
        version=VERSIONVALUE
        [ -z "__STAGING" ] || build1=__STAGING.$build 
        [ -z "__STAGING" ] || version=${version}:S:__STAGING
        [ -z "__STAGING" ] || destiso=${iso//$flavor/Staging:__STAGING-Staging-$flavor}
        [ -z "__STAGING" ] || flavor=Staging-$flavor'''

openqa_call_calc_isobuild = '''
        buildREPOID=$(grep REPOTYPE __envdir/files_iso.lst | grep $arch | grep -o -E '(Build|Snapshot)[^-]*' | grep -o -E '[0-9]+.?[0-9]+' | head -n 1) || :'''

openqa_call_start2 = '''
        [ ! -z "$build"  ] || continue
        
        echo "/usr/share/openqa/script/client isos post --host http://openqa.opensuse.org \\\\
 _OBSOLETE=1 \\\\
 DISTRI=DISTRIVALUE \\\\
 ARCH=$arch \\\\
 VERSION=$version \\\\
 BUILD=$build1 \\\\'''

openqa_call_legacy_builds=''' BUILD_HA=$build1 \\\\
 BUILD_SDK=$build1 \\\\
 BUILD_SES=$build1 \\\\
 BUILD_SLE=$build1 \\\\'''

openqa_call_calc_isobuild = '''
        buildREPOID=$(grep REPOTYPE __envdir/files_iso.lst | grep $arch | grep -o -E '(Build|Snapshot)[^-]*' | grep -o -E '[0-9]+.?[0-9]+' | head -n 1) || :'''

openqa_call_start_iso = ''' ISO=${destiso} \\\\"'''

openqa_call_repo0 = ''' echo " MIRROR_PREFIX=http://openqa.opensuse.org/assets/repo \\\\
 SUSEMIRROR=http://openqa.opensuse.org/assets/repo/REPO0_ISO \\\\
 MIRROR_HTTP=http://openqa.opensuse.org/assets/repo/REPO0_ISO \\\\
 MIRROR_HTTPS=https://openqa.opensuse.org/assets/repo/REPO0_ISO \\\\
 FULLURL=1 \\\\"'''

openqa_call_repo0a = ''' echo " REPO_0=${destiso%.iso} \\\\"'''

openqa_call_repot = '''
        for repot in {REPOLIST,}; do
            while read repo; do
                [ -z "__STAGING" ] || repo=${repo//Module/Staging:__STAGING-Module}
                [ -z "__STAGING" ] || repo=${repo//Product/Staging:__STAGING-Product}
                repoPrefix=${repo%-Media*}
                repoSuffix=${repo#$repoPrefix}
                repoDest=$repoPrefix-Build$build$repoSuffix
                repoKey=REPOPREFIX${repot}
                repoKey=${repoKey^^}
                repoKey=${repoKey//-/_}
                echo " REPO_$i=$repoDest \\\\"
                [[ $repoDest != *Media2* ]] || repoKey=${repoKey}_DEBUG
                [[ $repoDest != *Media3* ]] || repoKey=${repoKey}_SOURCE
                [[ $repo =~ license ]] || echo " REPO_$repoKey=$repoDest \\\\"
                : $((i++))
            done < <(grep $repot-POOL __envdir/files_repo.lst | grep REPOTYPE | grep $arch | sort)
        done'''

openqa_call_repot1 = '''
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
            [[ $dest != *Media2* ]] || repoKey=${repoKey}_DEBUGINFO
            [[ $dest != *Media2* ]] || dest=$dest-debuginfo
            [[ $dest != *Media3* ]] || repoKey=${repoKey}_SOURCE
            [[ $dest != *Media3* ]] || dest=$dest-source
            dest=${dest//-Media1/}
            dest=${dest//-Media2/}
            dest=${dest//-Media3/}
'''

openqa_call_repot2 = '''
            echo " REPO_$i=$dest \\\\"
            [[ $dest =~ license ]] || echo " REPO_$repoKey=$dest \\\\"
            [[ ! $repoKey =~ _DEBUGINFO ]] || [ -z "DEBUG_PACKAGES" ] || echo " REPO_${repoKey}_PACKAGES='DEBUG_PACKAGES' \\\\"
            [[ ! $repoKey =~ _SOURCE ]] || [ -z "SOURCE_PACKAGES" ] || echo " REPO_${repoKey}_PACKAGES='SOURCE_PACKAGES' \\\\"
            : $((i++))
        done < <(grep $arch __envdir/files_repo.lst | sort)'''

openqa_call_end = '''
        echo " FLAVOR=$flavor"
        echo ""
    done
done
'''

class ActionGenerator:
    def __init__(self, envdir, productpath, version):
        self.flavors = []
        self.hdds = []
        self.isos = []
        self.iso_extract_as_repo = {}
        self.repos = []
        self.repodirs = []
        self.renames = []
        self.envdir = envdir
        self.productpath = productpath
        self.version = version
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
        s=s.replace('VERSIONVALUE', self.version)
        s=s.replace("DISTRIVALUE", self.distri)
        s=s.replace("__STAGING", self.staging())

        if self.flavors:
            s=s.replace("FLAVORLIST",','.join(self.flavors))
            s=s.replace("FLAVORORS", '|'.join(self.flavors))
            s=s.replace("FLAVORASREPOORS", '|'.join([f for f in self.flavors if self.iso_extract_as_repo.get(f,0)]))

        if self.repos:
            s=s.replace("REPOLIST",  ','.join([m.attrib["name"] if "name" in m.attrib else m.tag for m in self.repos]))
            s=s.replace("REPOORS",   '|'.join([m.attrib["name"] if "name" in m.attrib else m.tag for m in self.repos]))
        if self.domain:
            s=s.replace("opensuse.org",self.domain)
        print(s, file=f)

    def staging(self):
        m = re.match(r'.*Staging:(?P<staging>[A-Z]).*', self.envdir)
        if not m:
            return ""
        return m.groupdict().get("staging","")

    def productisopath(self):
        if self.iso_path:
            return self.productpath + "/" + self.iso_path
        return self.productpath

    def productrepopath(self):
        if self.repo_path:
            return self.productpath + "/" + self.repo_path
        return self.productpath

    def doFlavor(self, node):
        if node.attrib.get("name",""):
            for f in node.attrib["name"].split("|"):
                self.flavors.append(f)
        if node.attrib.get("iso","") and node.attrib.get("name",""):
            for iso in node.attrib["name"].split("|"):
                self.isos.append(iso)
                if node.attrib["iso"] == "extract_as_repo":
                    self.iso_extract_as_repo[iso] = 1

        if node.attrib.get("distri",""):
            self.distri = node.attrib["distri"]
        if node.attrib.get("legacy_builds",""):
            self.legacy_builds = node.attrib["legacy_builds"]

        for t in node.findall(".//repos/*"):
            if "folder" in t.attrib:
                self.repodirs.append(t)
            else:
                self.repos.append(t)
        for t in node.findall(".//renames/*"):
            if "to" in t.attrib:
                self.renames.append([t.attrib.get("from",t.tag), t.attrib["to"]])

        for t in node.findall(".//*"):
            if t.tag == "hdd":
                self.hdds.append(t.attrib["filemask"])

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


    def gen_read_files(self,f):
        print(p, file=f)
        self.p(clear_iso, f)
        self.p(clear_repo, f)
        for hdd in self.hdds:
            if self.productpath.startswith('http'):
                self.p(read_files_curl, f, "ISOMASK", hdd)
            else:
                self.p(read_files_hdd, f, "ISOMASK", hdd)
        if self.isos:
            self.p(read_files_iso, f)
        if self.repos:
            self.p(read_files_repo, f)
            if any(repo.attrib.get("debug","") for repo in self.repos):
                self.p(read_files_repo, f, "Media1", "Media2", "REPOORS", '|'.join([m.attrib["name"] if "name" in m.attrib else m.tag for m in filter(lambda x: x.attrib.get("debug",""), self.repos)]))
            if any(repo.attrib.get("source","") for repo in self.repos):
                self.p(read_files_repo, f, "Media1", "Media3", "REPOORS", '|'.join([m.attrib["name"] if "name" in m.attrib else m.tag for m in filter(lambda x: x.attrib.get("source",""), self.repos)]))
        for repodir in self.repodirs:
            self.p(read_files_repo, f, "PRODUCTREPOPATH", self.productpath + "/*" + repodir.attrib["folder"] + "*", "REPOORS", "", "files_repo.lst", "files_repo_{}.lst".format(repodir.attrib["folder"]) )

    def gen_print_array_flavor_filter(self,f):
        if not self.hdds:
            return
        self.p('declare -A flavor_filter',f)
        # this assumes every flavor has hdd_url - we must store relation if that is not the case
        for fl, h in zip(self.flavors, self.hdds):
            self.p("flavor_filter[{}]='{}'".format(fl, h), f)
        

    def gen_print_rsync_iso(self,f):
        print(p, file=f)
        if self.isos or (self.hdds and not self.productpath.startswith('http')):
            self.gen_print_array_flavor_filter(f)
            self.p(rsync_iso, f)

    def gen_print_rsync_repo(self,f):
        print(p, file=f)
        for r in self.repodirs:
            self.p(rsync_repo1, f, "mid=''", "mid='{}'".format(r.attrib.get("mid","")))
            for ren in self.renames:
                self.p("        dest=${{dest//{}/{}}}".format(ren[0],ren[1]), f)
            self.p(rsync_repodir2, f,"PRODUCTREPOPATH", self.productpath + "/*" + r.attrib["folder"] + "*$arch*", "files_repo.lst", "files_repo_{}.lst".format(r.attrib["folder"]),"Media2","Media1","-debuginfo","","RSYNCFILTER","")
            if r.attrib.get("debug",""):
                self.p(rsync_repo1, f, "mid=''", "mid='{}'".format(r.attrib.get("mid","")))
                for ren in self.renames:
                    self.p("        dest=${{dest//{}/{}}}".format(ren[0],ren[1]), f)
                self.p(rsync_repodir2, f, "PRODUCTREPOPATH", self.productpath + "/*" + r.attrib["folder"] + "*$arch*", "files_repo.lst", "files_repo_{}.lst".format(r.attrib["folder"]),"RSYNCFILTER", " --include=PACKAGES --exclude={aarch64,i586,i686,noarch,nosrc,ppc64le,s390x,src,x86_64}/*".replace("PACKAGES",r.attrib["debug"]))
            if r.attrib.get("source",""):
                self.p(rsync_repo1, f, "mid=''", "mid='{}'".format(r.attrib.get("mid","")))
                for ren in self.renames:
                    self.p("        dest=${{dest//{}/{}}}".format(ren[0],ren[1]), f)
                self.p(rsync_repodir2, f, "PRODUCTREPOPATH", self.productpath + "/*" + r.attrib["folder"] + "*$arch*", "files_repo.lst", "files_repo_{}.lst".format(r.attrib["folder"]),"RSYNCFILTER", " --include=PACKAGES --exclude={aarch64,i586,i686,noarch,nosrc,ppc64le,s390x,src,x86_64}/*".replace("PACKAGES",r.attrib["source"]),"Media2","Media3","-debuginfo","-source")


    def gen_print_openqa(self,f):
        print(p, file=f)
        self.gen_print_array_flavor_filter(f)
        self.p(openqa_call_start, f)
        if self.legacy_builds:
            self.p(openqa_call_legacy_builds, f)
        self.p(openqa_call_start2, f)
        i=0
        if self.hdds:
            if self.productpath.startswith('http'):
                self.p(" HDD_URL_1=PRODUCTPATH/$destiso \\\\\"", f)
            else:
                self.p(" HDD_1=$destiso \\\\\"", f)
        else:
            self.p(openqa_call_start_iso, f)
            for iso in self.isos:
                if self.iso_extract_as_repo.get(iso,0):
                    i += 1
                    self.p(openqa_call_repo0, f, "REPO0_ISO","${destiso%.iso}", f)
                    self.p(openqa_call_repo0a, f, "REPO0_ISO","${destiso%.iso}", f)
                    break # for now only REPO_0
        self.p(" i={}".format(i), f)

        if self.repos:
            self.p(" i=9", f) # temporary to simplify diff with old rsync scripts, may be removed later
            self.p(openqa_call_repot, f, "REPOTYPE", "''", "REPOPREFIX", "SLE_")
        for r in self.repodirs:
            self.p(openqa_call_repot1, f, "REPOKEY", r.attrib.get("rename",r.tag),"mid=''", "mid='{}'".format(r.attrib.get("mid","")))
            for ren in self.renames:
                self.p("            dest=${{dest//{}/{}}}".format(ren[0],ren[1]), f)
            if i==0:
                self.p("            [ $i != 0 ] || {{ {};  }}".format(openqa_call_repo0), f, "REPO0_ISO", "$dest", f)
            self.p(openqa_call_repot2, f, "files_repo.lst", "files_repo_{}.lst".format(r.attrib["folder"]),"DEBUG_PACKAGES",r.attrib.get("debug",""),"SOURCE_PACKAGES",r.attrib.get("source",""))

        if self.staging():
            self.p("echo ' STAGING=__STAGING \\'", f)

        self.p(openqa_call_end, f)

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
            if v.find("'") == -1:
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
    for root, _, files in os.walk("xml/build.opensuse.org"):
        (xmlfile, dist_path, version) = parse_dir(root, project, files)
    if not xmlfile:
        print('Cannot find xml file for {} ...'.format(project), file=sys.stderr)
        return 1

    a = ActionGenerator(os.getcwd() +"/"+ project, dist_path, version)
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
