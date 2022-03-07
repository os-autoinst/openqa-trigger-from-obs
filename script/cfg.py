header = '''# GENERATED FILE - DO NOT EDIT
set -e
'''

clear_lst = '''for f in __envsub/{files_,Media}*.lst; do
    [ ! -f "$f" ] ||  : > "$f"
done

[ ! -f __envdir/../rsync.secret ] || rsync_pwd_option=--password-file=__envdir/../rsync.secret
'''

read_files_curl = '''curl -s PRODUCTPATH/ | grep -o 'ISOMASK' | head -n 1 >> __envsub/files_iso.lst'''

read_files_hdd = '''rsync -4 --list-only $rsync_pwd_option PRODUCTPATH/FOLDER/ | grep -o 'ISOMASK' | awk '{ $1=$2=$3=$4=""; print substr($0,5); }' | grep -E 'ARCHORS' >> __envsub/files_iso.lst
'''

read_files_iso = '''rsync -4 --list-only $rsync_pwd_option PRODUCTISOPATH/FOLDER/*SRCISO* | grep -P 'Media1?.iso$' | awk '{ $1=$2=$3=$4=""; print substr($0,5); }' >> __envsub/files_iso.lst
'''

read_files_isos = '''rsync -4 --list-only $rsync_pwd_option PRODUCTISOPATH/ | grep -P 'Media1?.iso$' | grep -E 'ARCHORS' | awk '{ $1=$2=$3=$4=""; print substr($0,5); }' >> __envsub/files_iso.lst
'''

read_files_repo = '''rsync -4 --list-only $rsync_pwd_option PRODUCTREPOPATH/ | grep -P 'Media[1-3](.license)?$' | awk '{ $1=$2=$3=$4=""; print substr($0,5); } ' | grep -v IGNOREPATTERN | grep -E 'REPOORS' | grep -E 'ARCHORS'  >> __envsub/files_repo.lst
'''

read_files_repo_media = '''rsync -4 $rsync_pwd_option PRODUCTREPOPATH/*Media1/media.1/media __envsub/Media1.lst'''
read_files_repo_media_convert = ''' && echo "Snapshot$(grep -oP '[\d]{8}' __envsub/products)" >> __envsub/destlst'''

read_files_repo_link = '''cp __envdir/REPOLINK/files_repo*.lst __envsub/
'''

read_files_repo_link2 = '''cp __envdir/REPOLINK/files_iso_buildid.lst __envsub/
'''

read_files_repo_link3 = '''cp __envdir/REPOLINK/files_iso*.lst __envsub/
'''

def rsync_fix_dest(distri, version, staging, use_staging_patterns ):
    if not staging: return ''
    if use_staging_patterns: return '''
    staging_pattern=$flavor
    [ -z "${flavor_staging[$staging_pattern]}" ] || staging_pattern="${flavor_staging[$staging_pattern]}"
    dest=${dest//$staging_pattern/Staging:__STAGING-$staging_pattern}'''
    if version != 'Factory' and len(staging) == 1: return '''dest=${dest//$flavor/Staging:__STAGING-Staging-$flavor}'''
    return '''dest=${dest//$flavor/Staging:__STAGING-$flavor}'''

def rsync_iso_fix_src(archs):
    if 'armv7hl' in archs and not 'armv7l' in archs:
        return '[ -n "$src" ] || [ "$arch" != armv7hl ] || src=$(grep "$filter" __envsub/files_iso.lst | grep armv7l | head -n 1)'
    return ''

def rsync_commands(checksum):
    res = '''echo "rsync --timeout=3600 -tlp4 --specials PRODUCTISOPATH/${iso_folder[$flavor]}*$src /var/lib/openqa/factory/$asset_folder/$dest"'''
    if checksum:
        res = res + '''
        echo "rsync --timeout=3600 -tlp4 --specials PRODUCTISOPATH/${iso_folder[$flavor]}*$src.sha256 /var/lib/openqa/factory/other/$dest.sha256"'''
    return res

rsync_iso = lambda distri, version, archs, staging, checksum, repo0folder, use_staging_patterns : '''
archs=(ARCHITECTURS)

for flavor in {FLAVORLIST,}; do
    for arch in "${archs[@]}"; do
        filter=$flavor
        [[ ! -v flavor_filter[@] ]] || [ -z "${flavor_filter[$flavor]}" ] || filter=${flavor_filter[$flavor]}
        [[ ${norsync_filter[$filter]} != 1 ]] || continue
        src=$(grep "$filter" __envsub/files_iso.lst | grep $arch | head -n 1)
        ''' + rsync_iso_fix_src(archs) + '''
        [ ! -z "$src" ] || continue
        dest=$src
        ''' + rsync_fix_dest(distri, version, staging, use_staging_patterns) + '''
        asset_folder=other
        [[ ! $dest =~ \.iso$  ]] || asset_folder=iso
        [[ ! $dest =~ \.(qcow2|raw|vhd|vhdx|xz)$ ]] || asset_folder=hdd
        ''' + rsync_commands(checksum) + '''
        repo0folder=${dest%.iso}
        ''' + (repo0folder if repo0folder else "") + '''
        [ -z "FLAVORASREPOORS" ] || [ $( echo "$flavor" | grep -E -c "^(FLAVORASREPOORS)$" ) -eq 0 ] || echo "[ -d /var/lib/openqa/factory/repo/$repo0folder ] || {
    mkdir /var/lib/openqa/factory/repo/$repo0folder
    bsdtar xf /var/lib/openqa/factory/iso/$dest -C /var/lib/openqa/factory/repo/$repo0folder
}"
    done
done'''

rsync_hdds = '''
archs=(ARCHITECTURS)

for flavor in {FLAVORLIST,}; do
    for arch in "${archs[@]}"; do
        while read src; do
            folder=""
            for i in "${!hdd_folder[@]}"; do
                if [[ $src =~ $i ]]; then
                    folder="${hdd_folder[$i]}"
                    break
                fi
            done
            [[ $src =~ .iso$ ]] && asset="iso" || asset="hdd"
            echo "rsync --timeout=3600 -tlp4 --specials PRODUCTISOPATH/$folder/$src /var/lib/openqa/factory/$asset/"
            echo "rsync --timeout=3600 -tlp4 --specials PRODUCTISOPATH/$folder/$src.sha256 /var/lib/openqa/factory/other/"
            echo ""
        done < <(grep ${arch} __envsub/files_iso.lst | sort)
    done
done'''

def pre_rsync_repo(repos):
    return ''

rsync_repo1 = '''
echo '# REPOOWNLIST'
[ ! -f __envsub/files_iso.lst ] || buildid=$(cat __envsub/files_iso.lst | grep -E 'FLAVORORS' | grep -o -E '(Build|Snapshot)[^-]*' | head -n 1)
[ ! -f __envsub/files_iso.lst ] || test -n "$buildid" || buildid=$(cat __envsub/files_iso.lst | grep -o -E '(Build|Snapshot)[^-]*' | head -n 1)
[ -z "__STAGING" ] || buildid=${buildid//Build/Build__STAGING.}
[ ! -f __envsub/files_repo.lst ] || ! grep -q -- "-POOL-" __envsub/files_repo.lst || additional_repo_suffix=-POOL
[ -n "$buildid" ] || buildid=$(grep -hEo 'Build[0-9]+(.[0-9]+)?' __envsub/Media1_*.lst 2>/dev/null | head -n 1)

for repo in {REPOOWNLIST,}; do
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
        echo "rsync --timeout=3600 -rtlp4 --delete --specials PRODUCTREPOPATH/$src/ /var/lib/openqa/factory/repo/$repoCur"
        echo "rsync --timeout=3600 -rtlp4 --delete --specials --link-dest /var/lib/openqa/factory/repo/$repoCur/ /var/lib/openqa/factory/repo/$repoCur/ /var/lib/openqa/factory/repo/$repoDest/"
    done < <(grep $repo$additional_repo_suffix __envsub/files_repo.lst)
done
'''

rsync_repodir1 = '''
archs=(ARCHITECTURREPO)
[ ! -f __envsub/files_iso.lst ] || buildid=$(cat __envsub/files_iso.lst | grep -E 'FLAVORORS' | grep -o -E '(Build|Snapshot)[^-]*' | head -n 1)
[ -n "$buildid" ] || buildid=$(grep -hEo 'Build[0-9]+(.[0-9]+)?' __envsub/Media1_*.lst 2>/dev/null | head -n 1)


if [[ ! -n $build ]] && [[ ! $buildid =~ (Build|Snapshot)[0-9]*[0-9]$ ]]; then
    buildid=${buildid%%\.[[:alpha:]]*}
fi

for arch in "${archs[@]}"; do
    while read src; do
        [ ! -z "$src" ] || continue
        dest=$src
        dest=${dest%-Build*}
        destPrefix=${dest%$arch*}
        destSuffix=${dest#$destPrefix}
        mid=''
        dest=$destPrefix$mid$destSuffix'''

def rsync_repodir2():
    return '''
        dest=${dest//-Media2/}
        echo rsync --timeout=3600 -rtlp4 --delete --specials RSYNCFILTER PRODUCTREPOPATH/*Media2/*  /var/lib/openqa/factory/repo/$dest-CURRENT-debuginfo/
        echo rsync --timeout=3600 -rtlp4 --delete --specials --link-dest /var/lib/openqa/factory/repo/$dest-CURRENT-debuginfo/ /var/lib/openqa/factory/repo/$dest-CURRENT-debuginfo/ /var/lib/openqa/factory/repo/$dest-$buildid-debuginfo
    done < <(grep ${arch//i686/i586} __envsub/files_repo.lst | grep Media2)
done
'''

rsync_repodir1_dest = lambda dest: '''
archs=(ARCHITECTURREPO)
buildid=$(cat __envsub/files_iso.lst | grep -E 'FLAVORORS' | grep -o -E '(Build|Snapshot)[^-]*' | head -n 1)

for arch in "${archs[@]}"; do
    while read src; do
        [ ! -z "$src" ] || continue
        [[ ''' + dest + ''' =~ $arch ]] || [[ ''' + dest + ''' =~ ${arch//i686/i586} ]] || [[ "ARCHITECTURREPO" == . ]] || break
        dest=''' + dest


def openqa_call_fix_destiso(distri, version, staging):
    if not staging:
        return ''
    if (version == 'Factory' or len(staging)>1):
        return '''destiso=${iso//$flavor/Staging:__STAGING-$flavor}
        flavor=Staging-$flavor'''
    return '''version=${version}:S:__STAGING
        destiso=${iso//$flavor/Staging:__STAGING-Staging-$flavor}
        flavor=Staging-$flavor'''

def openqa_call_start_fix_iso(archs):
    if 'armv7hl' in archs and not 'armv7l' in archs:
        return '[ -n "$iso" ] || [ "$arch" != armv7hl ] || iso=$(grep "$filter" __envsub/files_iso.lst | grep armv7l | head -n 1)'
    return ''

def openqa_call_news(news, news_archs):
    if not news:
        return ''
    news_str = '''[[ ! "$flavor" =~ ''' + news + ''' ]]'''
    if news_archs:
        news_str += ''' || [ "$arch" != ''' + news_archs + ''' ]'''
    return news_str + ''' || news["$flavor"]="$destiso"'''

def openqa_call_start_distri(flavor_distri):
    if flavor_distri:
        return '''distri=DISTRIVALUE
        [ -z "${flavor_distri[$flavor]}" ] || distri=${flavor_distri[$flavor]}'''
    return 'distri=DISTRIVALUE'

def openqa_call_start_meta_variables(meta_variables):
    if not meta_variables:
        return 'VERSION=$version\"'

    return '''VERSION=$version \\\\
 ''' + meta_variables + '\"'

def pre_openqa_call_start(repos):
    return ''

openqa_call_start = lambda distri, version, archs, staging, news, news_archs, flavor_distri, meta_variables, assets_flavor, repo0folder: '''
archs=(ARCHITECTURS)
[ ! -f __envsub/files_repo.lst ] || ! grep -q -- "-POOL-" __envsub/files_repo.lst || additional_repo_suffix=-POOL

for flavor in {FLAVORALIASLIST,}; do
    for arch in "${archs[@]}"; do
        filter=$flavor
        ''' + openqa_call_start_distri(flavor_distri) + '''
        [[ ! -v flavor_filter[@] ]] || [ -z "${flavor_filter[$flavor]}" ] || filter=${flavor_filter[$flavor]}
        [ $filter != Appliance ] || filter="qcow2"
        version=VERSIONVALUE
        if [ -z "${norsync_filter[$flavor]}" ] || [ -z $build1 ]; then {
        iso=$(grep "$filter" __envsub/files_iso.lst 2>/dev/null | grep $arch | head -n 1)
        ''' + openqa_call_start_fix_iso(archs) + '''
        build=$(echo $iso | grep -o -E '(Build|Snapshot)[^-]*' | grep -o -E '[0-9]\.?[0-9]+(\.[0-9]+)*' | tail -n 1) || :
        buildex=$(echo $iso | grep -o -E '(Build|Snapshot)[^-]*') || :
        [ -n "$iso" ] || [ "$flavor" != "''' + assets_flavor + '''" ] || build=$(grep -o -E '(Build|Snapshot)[^-]*' __envsub/files_asset.lst | grep -o -E '[0-9]\.?[0-9]+(\.[0-9]+)*' | head -n 1)
        [ -n "$iso" ] || [ "$flavor" != "''' + assets_flavor + '''" ] || buildex=$(grep -o -E '(Build|Snapshot)[^-]*' __envsub/files_asset.lst | head -n 1)
        [ -n "$iso$build" ] || build=$(grep -h -o -E '(Build|Snapshot)[^-]*' __envsub/Media1*.lst 2>/dev/null | head -n 1 | grep -o -E '[0-9]\.?[0-9]+(\.[0-9]+)*')|| :
        [ -n "$build"  ] || continue
        buildex=${buildex/.iso/}
        buildex=${buildex/.raw.xz/}
        buildex=${buildex/.qcow2/}
        build1=$build
        destiso=$iso
        [ -z "__STAGING" ] || build1=__STAGING.$build
        ''' + openqa_call_fix_destiso(distri, version, staging) + '''
        repo0folder=${destiso%.iso}
        ''' + (repo0folder if repo0folder else "") + '''
        [ "$arch" != . ] || arch=x86_64
        ''' + openqa_call_news(news, news_archs) + '''
        }
        fi
        echo "/usr/bin/openqa-cli api -X post isos?async=1 \\\\\"
(
 echo \" DISTRI=$distri \\\\
 ARCH=$arch \\\\
 BUILD=$build1 \\\\
 ''' + openqa_call_start_meta_variables(meta_variables)

openqa_call_legacy_builds_link=''

openqa_call_legacy_builds=''

def openqa_call_start_iso(checksum):
    if checksum:
        return ''' [ -z "$destiso" ] || echo \" ISO=${destiso} \\\\
 CHECKSUM_ISO=\$(cut -b-64 /var/lib/openqa/factory/other/${destiso}.sha256 | grep -E '[0-9a-f]{5,40}' | head -n1) \\\\
 ASSET_256=${destiso}.sha256 \\\\\"'''
    return ''' [ -z "$destiso]" || echo \" ISO=${destiso} \\\\
 ASSET_256=${destiso}.sha256 \\\\\"'''

def openqa_call_start_ex1(checksum, tag):
    res = tag + '=${destiso} \\\\'
    if checksum:
        res += '''
 CHECKSUM_''' + tag + '''=\$(cut -b-64 /var/lib/openqa/factory/other/${destiso}.sha256 | grep -E '[0-9a-f]{5,40}' | head -n1) \\\\
 ASSET_256=${destiso}.sha256 \\\\'''
    return res


def openqa_call_start_ex(checksum):
    return ''' if [[ ${norsync_filter[$filter]} == 1 ]]; then
   :
 elif [[ $destiso =~ \.iso$ ]]; then
   echo \" ''' + openqa_call_start_ex1(checksum, 'ISO')  + '''\"
 elif [[ $destiso =~ \.(hdd|qcow2|raw\.xz|raw\.gz|vhdx\.xz|vmdk\.xz)$ ]]; then
   echo \" ''' + openqa_call_start_ex1(checksum, 'HDD_1')  + '''\"
 elif [ -n "$destiso" ]; then
   echo \" ''' + openqa_call_start_ex1(checksum, 'ASSET_1')  + '''\"
 fi
'''

openqa_call_start_hdds='''
 i=1
 while read src; do
     folder=""
     for mask in "${!hdd_folder[@]}"; do
         if [[ $src =~ $mask ]]; then
             folder="${hdd_folder[$mask]}"
             break
         fi
     done
     n=$((i++))
     echo " ASSET_$((n+255))=$src.sha256 \\\\"
     if [[ $src =~ .iso$ ]]; then
         echo " ISO=$src \\\\"
         echo " CHECKSUM_ISO=\$(cut -b-64 /var/lib/openqa/factory/other/$src.sha256 | grep -E '[0-9a-f]{5,40}' | head -n1) \\\\"
     else
         echo " HDD_$n=$src \\\\"
         echo " CHECKSUM_HDD_$n=\$(cut -b-64 /var/lib/openqa/factory/other/$src.sha256 | grep -E '[0-9a-f]{5,40}' | head -n1) \\\\"
     fi
 done < <(grep ${arch} __envsub/files_iso.lst | sort)
'''

# if MIRROREPO is set - expressions for FLAVORASREPOORS will evaluate to false
def openqa_call_repo0():
    return ''' [ -z "FLAVORASREPOORSMIRRORREPO" ] || [ $( echo "$flavor" | grep -E -c "^(FLAVORASREPOORS)$" ) == 0"MIRRORREPO" ] || {
    echo " MIRROR_PREFIX=http://openqa.opensuse.org/assets/repo \\\\
 SUSEMIRROR=http://openqa.opensuse.org/assets/repo/REPO0_ISO \\\\
 MIRROR_HTTP=http://openqa.opensuse.org/assets/repo/REPO0_ISO \\\\
 MIRROR_HTTPS=https://openqa.opensuse.org/assets/repo/REPO0_ISO \\\\
 FULLURL=1 \\\\"
    }'''

openqa_call_repo0a = ' [ -z "FLAVORASREPOORS" ] || [ $( echo "$flavor" | grep -E -c "^(FLAVORASREPOORS)$" ) -eq 0 ] || '

openqa_call_repo0b = ' echo " REPO_0=REPO0_ISO \\\\"'

openqa_call_repo5 = '''    destRepo=${destiso%.iso}
  filter1=${filter//-DVD/-POOL}
  destRepo=${destRepo//$filter/$filter1}
  echo " REPO_5=$destRepo \\\\
 REPO_6=$destRepo.license \\\\
 REPO_REPOALIAS=$destRepo \\\\"
'''

def openqa_call_repot_part1():
    return '''[ -z "__STAGING" ] || repo=${repo//Module/Staging:__STAGING-Module}
                [ -z "__STAGING" ] || repo=${repo//Product/Staging:__STAGING-Product}'''

def openqa_call_repot_part2():
    return 'repoDest=$repoPrefix-Build$build$repoSuffix'

def openqa_call_repot_part3():
    return '''[[ $repoDest != *Media2* ]] || repoKey=${repoKey}_DEBUG
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

def openqa_call_extra(repos):
    return ''

openqa_call_repot = lambda build_id_from_iso, repos: '''
        for repot in {REPOLIST,}; do
            while read repo; do
                ''' + openqa_call_repot_part1() + '''
                repoPrefix=${repo%-Media*}
                repoSuffix=${repo#$repoPrefix}
                ''' + openqa_call_build_id_from_iso1(build_id_from_iso) + '''
                ''' + openqa_call_repot_part2() + '''
                repoKey=${repot}
                repoKey=${repoKey^^}
                repoKey=${repoKey//-/_}
                echo " REPO_$i=$repoDest \\\\"
                ''' + openqa_call_repot_part3() + '''
                ''' + openqa_call_build_id_from_iso2(build_id_from_iso) + '''
                [[ $repo =~ license ]] || echo " REPO_REPOPREFIX$repoKey=$repoDest \\\\"
                ''' + openqa_call_extra(repos) + '''
                : $((i++))
            done < <(grep $repot$additional_repo_suffix __envsub/files_repo.lst | grep REPOTYPE | grep $arch | sort)
        done'''

def openqa_call_repot1_debugsource():
    return '''[[ $src != *Media2* ]] || repoKey=${repoKey}_DEBUGINFO
            [[ $src != *Media2* ]] || dest=$dest-debuginfo
            [[ $src != *Media3* ]] || repoKey=${repoKey}_SOURCE
            [[ $src != *Media3* ]] || dest=$dest-source'''

openqa_call_repot1 = lambda: '''
        while read src; do
            dest=$src
            dest=${dest%-Build*}
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
            ''' + openqa_call_repot1_debugsource() + '''
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


openqa_call_repot1_dest = lambda dest: '''
        while read src; do
            [[ ''' + dest + ''' =~ $arch ]] || [[ ''' + dest + ''' =~ ${arch//i686/i586} ]] || [[ "ARCHITECTURREPO" == . ]] || break
            dest=''' + dest + '''-$buildex
            repoKey=REPOKEY
            ''' + openqa_call_repot1_debugsource() + '''
            repoKey=${repoKey^^}
            repoKey=${repoKey//-/_}
'''

def openqa_call_news_end(distri, news, news_arch):
    if not news:
        return ''
    suff = ''
    if news_arch and news_arch != 'x86_64':
        suff = '-' + news_arch
    folder='${n,,}'
    if distri != 'microos':
        folder = 'opensuse'
    return '''for n in "${!news[@]}"; do
    folder=''' + folder + '''
    folder=${folder%-dvd}''' + suff + '''
    echo  /var/lib/openqa/osc-plugin-factory/factory-package-news/factory-package-news.py save --dir /var/lib/snapshot-changes/$folder/VERSIONVALUE --snapshot $build1 /var/lib/openqa/factory/iso/${news[$n]}
done'''

def openqa_call_end(version):
    if version == 'Factory': return '''
        [ $flavor != MicroOS-DVD ] || flavor=DVD
        [ $flavor != Staging-MicroOS-DVD ] || flavor=Staging-DVD
        echo " FLAVOR=${flavor//Tumbleweed-/} \\\\"
) | LC_COLLATE=C sort
        echo ""
    done
done
'''
    return '''
        echo " FLAVOR=$flavor \\\\"
) | LC_COLLATE=C sort
        echo ""
    done
done
'''

def media2_name():
    return 'debug'

def media3_name():
    return 'source'
