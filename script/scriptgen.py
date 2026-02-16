import sys
import os
import re
from subprocess import check_output, CalledProcessError, STDOUT
import argparse
import copy
from contextlib import suppress
from xml.etree import ElementTree
from collections import defaultdict

import cfg


class ActionGenerator:
    def __init__(self, envdir, project, productpath, version, brand):
        self.brand = brand
        self.envdir = os.path.join(envdir, project)
        self.distri = ""
        self.openqa_cli = "/usr/bin/openqa-cli api -X post isos?async=1"
        self.version = version
        self.batches = []
        project = project.split("::")[0]
        pp = productpath
        if not pp or ("::" not in pp and "//" not in pp):
            if self.staging():
                pp = os.path.join("obspublish-stage::openqa", os.path.basename(project))
            else:
                pp = os.path.join("obspublish::openqa", os.path.basename(project))
            if productpath and "::" not in productpath and "//" not in productpath:
                pp = os.path.join(pp, productpath)
        self.productpath = pp
        self.archs = "aarch64 armv7l armv7hl ppc64le riscv64 s390x x86_64"
        self.media1 = 1

    def staging(self):
        m = re.match(r".*Staging:(?P<staging>[A-Z]).*", self.envdir)
        if m:
            return m.groupdict().get("staging", "")
        m = re.match(r".*Rings:(?P<ring>[0-9]).*", self.envdir)
        if m:
            return "Core"
        return ""

    def productisopath(self):
        if self.iso_path and self.productpath:
            return self.productpath + "/" + self.iso_path
        if self.iso_path and self.iso_path != "iso":
            return self.iso_path
        return self.productpath

    def productrepopath(self):
        if self.repo_path and self.productpath:
            return self.productpath + "/" + self.repo_path
        if self.repo_path and self.repo_path != "repo":
            return self.repo_path
        return self.productpath

    def doFile(self, filename):
        tree = ElementTree.parse(filename)
        root = tree.getroot()
        self.iso_path = root.attrib.get("iso_path", "")
        self.repo_path = root.attrib.get("repo_path", "repo")
        self.domain = root.attrib.get("domain", "")
        self.archs = root.attrib.get("archs", self.archs)
        self.version = root.attrib.get("version", self.version)
        if root.attrib.get("distri", ""):
            self.distri = root.attrib["distri"]
        if root.attrib.get("media1", ""):
            self.media1 = root.attrib["media1"]

        self.openqa_cli = root.attrib.get("openqa_cli", self.openqa_cli)

        for t in root.findall(".//batch"):
            batch = self.doBatch(t)
            if batch:
                for news in t.findall(".//news"):
                    if news.attrib.get("iso", ""):
                        batch.news = news.attrib["iso"]
                    if news.attrib.get("archs", ""):
                        batch.news_archs = news.attrib["archs"]
                for flavor in t.findall(".//flavor"):
                    batch.doFlavor(flavor)
                if not batch.flavors:
                    batch.doFlavor(t)

        if not len(self.batches):
            batches_string = root.attrib.get("batches", "default")
            for b in batches_string.split("|"):
                batch = self.doBatch(root, b)
                if root.attrib.get("metavars"):
                    batch.meta_variables = root.attrib.get("metavars")
                if batch:
                    for news in root.findall(".//news"):
                        if news.attrib.get("iso", ""):
                            batch.news = news.attrib["iso"]
                        if news.attrib.get("archs", ""):
                            batch.news_archs = news.attrib["archs"]
                    for flavor in root.findall(".//flavor"):
                        batch.doFlavor(flavor)

    def doBatch(self, node, name=None, root=None):
        if not name:
            name = node.attrib.get("name", "")
        if not name:
            print("Batch node has no name attribute", file=sys.stderr)
            return
        batch = ActionBatch(name, self)
        batch.media1 = self.media1
        if node.attrib.get("repos", ""):
            batch.repolink = node.attrib["repos"]
        if node.attrib.get("folder", ""):
            batch.folder = node.attrib["folder"]
        if node.attrib.get("archs", ""):
            batch.archs = node.attrib["archs"]
        elif root:
            batch.archs = root.attrib.get("archs", batch.archs)

        if node.attrib.get("mask", ""):
            batch.mask = node.attrib["mask"]
        if node.attrib.get("distri", ""):
            batch.distri = node.attrib["distri"]
        if node.attrib.get("checksum", "") == "0":
            batch.checksum = 0
        if node.attrib.get("repo0folder", ""):
            batch.repo0folder = node.attrib["repo0folder"]
        if node.attrib.get("variable", ""):
            batch.variable = node.attrib["variable"]
        if node.tag != "openQA":
            batch.iso_path = node.attrib.get("iso_path", "")

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
        self.dist_path = ""
        self.iso_path = ""
        self.repo_path = "repo"
        self.archs = actionGenerator.archs
        self.news = ""
        self.news_archs = ""
        self.archs_repo = ""
        self.flavors = []
        self.flavor_aliases = defaultdict(list)
        self.flavor_aliases_flavor = []
        self.flavor_distri = defaultdict(list)
        self.staging_pattern = {}
        self.iso1 = {}
        self.hdds = []
        self.hdd_folder = {}
        self.assets = []
        self.assets_flavor = ""
        self.assets_archs = ""
        self.asset_folders = {}
        self.asset_tags = {}
        self.asset_rsync = {}
        self.norsync = {}
        self.isos = []
        self.isos_fixed = []
        self.iso_folder = {}
        self.iso_5 = ""
        self.fixed_iso = ""
        self.mask = ""
        self.iso_extract_as_repo = {}
        self.ln_iso_to_repo = {}
        self.mirror_repo = ""
        self.repos = []
        self.reposmultiarch = []  # these repos need not to be processed for each arch
        self.rsync_timeout = 3600
        self.repolink = ""
        self.build_id_from_iso = 0
        self.repodirs = []
        self.version_from_media = 0  # works only whith repodirs. Will also sync in read_files.sh PRODUCTDIR*/%repodir.folder%*Media1/media.1/media
        self.renames = []
        self.distri = actionGenerator.distri
        self.folder = ""
        self.legacy_builds = 0
        self.checksum = 1
        self.repo0folder = ""
        self.variable = ""
        self.meta_variables = "_OBSOLETE=1"
        if self.ag.brand != "obs" and not self.ag.staging():
            self.meta_variables = "_DEPRIORITIZEBUILD=1"
        self.offset = 1
        self.media1 = 1

    def productpath(self):
        if self.dist_path:
            return self.dist_path
        return self.ag.productpath

    def productisopath(self):
        if self.iso_path and self.dist_path:
            return self.dist_path + "/" + self.iso_path
        if self.dist_path:
            return self.dist_path
        ret = self.ag.productisopath()
        if self.iso_path:
            return ret + "/" + self.iso_path
        return ret

    def productrepopath(self):
        if self.repo_path and self.dist_path:
            return self.dist_path + "/" + self.repo_path
        if self.repo_path and self.repo_path != "repo":
            return self.repo_path
        if self.dist_path:
            return self.dist_path
        return self.ag.productrepopath()

    def p(
        self,
        s,
        f,
        extra1=None,
        extra2=None,
        extra3=None,
        extra4=None,
        extra5=None,
        extra6=None,
        extra7=None,
        extra8=None,
        extra9=None,
        extra10=None,
    ):
        if extra1 != None and extra2 != None:
            s = s.replace(extra1, extra2)
            if extra3 != None and extra4 != None:
                s = s.replace(extra3, extra4)
                if extra5 != None and extra6 != None:
                    s = s.replace(extra5, extra6)
                    if extra7 != None and extra8 != None:
                        s = s.replace(extra7, extra8)
                        if extra9 != None and extra10 != None:
                            s = s.replace(extra9, extra10)
        xtrapath = ""
        if self.folder:
            xtrapath = "/" + self.folder
        s = s.replace("PRODUCTPATH", self.productpath() + xtrapath)
        s = s.replace("PRODUCTISOPATH", self.productisopath() + xtrapath)
        s = s.replace("PRODUCTREPOPATH", self.productrepopath() + xtrapath)
        if self.subfolder and self.subfolder != "default":
            s = s.replace("__envsub", self.ag.envdir + "/" + self.subfolder)
        else:
            s = s.replace("__envsub", self.ag.envdir)
        s = s.replace("__envdir", self.ag.envdir)
        if self.ag.version.startswith("15.") and self.ag.staging() == "Core":
            s = s.replace("VERSIONVALUE", self.ag.version + ":Core")
        elif self.ag.version.startswith("15.") and "Jump" in self.ag.envdir:
            s = s.replace("VERSIONVALUE", "Jump:" + self.ag.version)
        elif self.subfolder and self.subfolder != "default" and not self.ag.version:
            s = s.replace("VERSIONVALUE", self.subfolder.replace("Leap_", ""))
        elif self.ag.staging() and self.ag.version == "Factory":
            s = s.replace("VERSIONVALUE", "Staging:" + self.ag.staging())
        else:
            s = s.replace("VERSIONVALUE", self.ag.version.replace("Factory", "Tumbleweed"))
        s = s.replace("DISTRIVALUE", self.distri)
        s = s.replace("__STAGING", self.ag.staging())
        s = s.replace("ARCHITECTURS", self.archs)
        if self.archs_repo:
            s = s.replace("ARCHITECTURREPO", self.archs_repo)
        else:
            s = s.replace("ARCHITECTURREPO", self.archs)
        s = s.replace("ARCHORS", self.archs.replace(" ", "|").replace("armv7hl", "armv7hl|armv7l"))
        s = s.replace("SUBFOLDER", self.subfolder)

        if self.flavors or self.flavor_aliases_flavor:
            s = s.replace("FLAVORLIST", ",".join(self.flavors))
            aliases = copy.deepcopy(self.flavors)
            aliases.extend(self.flavor_aliases_flavor)
            s = s.replace("FLAVORORS", "|".join(self.flavors))
            s = s.replace("FLAVORALIASLIST", ",".join(aliases))
            s = s.replace("FLAVORASREPOORS", "|".join([f for f in self.flavors if self.iso_extract_as_repo.get(f, 0)]))
            s = s.replace("FLAVORTOREPOORS", "|".join([f for f in self.flavors if self.ln_iso_to_repo.get(f, 0)]))

        if self.repos or (self.repolink and not "/" in self.repolink):
            repos = self.repos.copy()
            s = s.replace(
                "REPOOWNLIST", ",".join([m.attrib["name"] if "name" in m.attrib else m.tag for m in repos.copy()])
            )
            if self.repolink:
                repos.extend(self.ag.batch_by_name(self.repolink).repos)
            if self.iso_5:
                s = s.replace(
                    "REPOLIST",
                    ",".join(
                        [
                            m.attrib["name"] if "name" in m.attrib else m.tag
                            for m in self.ag.batch_by_name(self.repolink).repos
                        ]
                    ),
                )
            else:
                s = s.replace("REPOLIST", ",".join([m.attrib["name"] if "name" in m.attrib else m.tag for m in repos]))
            s = s.replace("REPOORS", "|".join([m.attrib["name"] if "name" in m.attrib else m.tag for m in repos]))
        mirror_repo = self.mirror_repo
        if not mirror_repo and self.repolink and not "/" in self.repolink:
            self.mirror_repo = self.ag.batch_by_name(self.repolink).mirror_repo
        s = s.replace("MIRRORREPO", self.mirror_repo)
        if self.ag.domain:
            s = s.replace("opensuse.org", self.ag.domain)
        s = s.replace("REPOLINK", self.repolink)
        fixediso = "0"
        if self.isos_fixed:
            fixediso = "1"
        s = s.replace("FIXEDISO", fixediso)
        print(s, file=f)

    def doFlavor(self, node):
        if node.attrib.get("archs", ""):
            self.archs = node.attrib["archs"]

        if node.attrib.get("staging_pattern", ""):
            self.staging_pattern[node.attrib["name"]] = node.attrib["staging_pattern"]
        if node.attrib.get("iso1", ""):
            self.iso1[node.attrib["name"]] = node.attrib["iso1"]

        if node.attrib.get("dist_path", ""):
            self.dist_path = node.attrib["dist_path"]

        if node.attrib.get("name", ""):
            if node.attrib.get("news"):
                self.news = node.attrib["name"]
                if node.attrib["news"] != "1":
                    self.news_archs = node.attrib["news"]
            for f in node.attrib["name"].split("|"):
                if node.attrib.get("flavor", "") != "0":
                    self.flavors.append(f)
                if node.attrib.get("distri", ""):
                    self.flavor_distri[f] = node.attrib["distri"]
                if node.attrib.get("iso_5", ""):
                    self.flavor_aliases[node.attrib.get("iso_5")].append(f)
                    self.iso_5 = node.attrib.get("iso_5")
                if node.attrib.get("fixed_iso", ""):
                    self.fixed_iso = node.attrib["fixed_iso"]
                if node.attrib.get("rsync", "1") == "0":
                    self.norsync[f] = 1
        iso_attrib = node.attrib.get("iso", "")
        if iso_attrib.endswith(".iso"):
            self.isos_fixed.append(iso_attrib)
        elif iso_attrib and node.attrib.get("name", ""):
            for iso in node.attrib["name"].split("|"):
                if node.attrib.get("folder", ""):
                    # self.iso_path = node.attrib["folder"]
                    self.iso_folder[iso] = node.attrib["folder"]
                if iso_attrib == "extract_as_repo":
                    self.iso_extract_as_repo[iso] = 1
                elif iso_attrib != "1":
                    if node.attrib.get("extract_as_repo", ""):
                        self.iso_extract_as_repo[iso] = 1
                    iso = iso_attrib
                    self.iso_extract_as_repo[iso_attrib] = 1
                else:
                    if node.attrib.get("extract_as_repo", ""):
                        self.iso_extract_as_repo[iso] = 1
                        self.repo0folder = node.attrib["extract_as_repo"]
                self.isos.append(iso)
                if node.attrib.get("ln_iso_to_repo", ""):
                    self.ln_iso_to_repo[iso] = node.attrib["ln_iso_to_repo"]
        elif node.attrib.get("name", "") and node.attrib.get("folder", ""):
            for iso in node.attrib["name"].split("|"):
                self.iso_folder[iso] = node.attrib["folder"]

        for t in node.findall(".//isos/*"):
            self.isos.append(t.tag)

        if node.attrib.get("distri", ""):
            self.distri = node.attrib["distri"]
        if node.attrib.get("legacy_builds", ""):
            self.legacy_builds = node.attrib["legacy_builds"]
        if node.attrib.get("offset", ""):
            self.offset = node.attrib["offset"]
        if node.attrib.get("media1", ""):
            self.media1 = node.attrib["media1"]

        for t in node.findall(".//repos"):
            if t.attrib.get("archs", ""):
                self.archs_repo = t.attrib["archs"]

        for t in node.findall(".//repos/*"):
            if t.get("multiarch", "") and not self.isos_fixed:
                self.reposmultiarch.append(t)
                continue

            if "folder" in t.attrib:
                self.repodirs.append(t)
            else:
                self.repos.append(t)
            if t.attrib.get("mirror", ""):
                self.mirror_repo = t.tag

        if node.attrib.get("version_from_media", ""):
            self.version_from_media = node.attrib["version_from_media"]

        for t in node.findall("./alias"):
            prefix = t.attrib.get("prefix", "")
            suffix = t.attrib.get("suffix", "")
            suffix = suffix.replace("${version}", self.ag.version)
            name = t.attrib.get("name", "")
            for p in prefix.split("|"):
                for n in name.split("|"):
                    for s in suffix.split("|"):
                        self.flavor_aliases[t.attrib.get("alias", "")].append(p + n + s)
                        self.flavor_aliases_flavor.append(p + n + s)

        if node.attrib.get("extra_flavors", ""):
            extra_flavors = node.attrib.get("extra_flavors", "")
            for extra_flavor in extra_flavors.split("|"):
                flavor, distri = extra_flavor.split("/")
                self.flavor_distri[flavor].append(distri)
                self.flavor_aliases[flavor].append(distri)
                self.flavor_aliases_flavor.append(flavor)


        for t in node.findall(".//renames/*"):
            if "to" in t.attrib:
                self.renames.append([t.attrib.get("from", t.tag), t.attrib["to"]])

        assets_folder = ""
        for t in node.findall(".//assets"):
            if t.attrib.get("flavor"):
                self.assets_flavor = t.attrib["flavor"]
            else:
                self.assets_flavor = node.attrib.get("name", "")

            if t.attrib.get("archs"):
                self.assets_archs = t.attrib["archs"]
            if t.attrib.get("folder"):
                assets_folder = t.attrib["folder"]

        for t in node.findall(".//assets/*"):
            self.assets.append(t.attrib["filemask"])
            self.asset_tags[t.attrib["filemask"]] = t.tag
            if t.attrib.get("filemask") and t.attrib.get("folder"):
                self.asset_folders[t.attrib["filemask"]] = t.attrib["folder"]
            elif t.attrib.get("filemask") and assets_folder:
                self.asset_folders[t.attrib["filemask"]] = assets_folder

        for t in node.findall(".//*"):
            if t.tag == "iso":
                self.isos.append(t.attrib["filemask"])
                if t.attrib.get("folder", ""):
                    self.iso_folder[t.attrib["filemask"]] = t.attrib["folder"]
                    self.hdd_folder[t.attrib["filemask"]] = t.attrib["folder"]
            if t.tag == "hdd":
                self.hdds.append(t.attrib["filemask"])
                if node.attrib.get("folder", ""):
                    self.iso_folder[t.attrib["filemask"]] = node.attrib["folder"]
                    if not t.attrib.get("folder", ""):
                        self.hdd_folder[t.attrib["filemask"]] = node.attrib["folder"]
                if t.attrib.get("folder", ""):
                    self.hdd_folder[t.attrib["filemask"]] = t.attrib["folder"]
            if t.tag == "asset" and not self.asset_tags:
                self.assets.append(t.attrib["filemask"])
                if t.attrib.get("flavor"):
                    self.assets_flavor = t.attrib["flavor"]
                if t.attrib.get("archs"):
                    self.assets_archs = t.attrib["archs"]
                if t.attrib.get("filemask"):
                    if t.attrib.get("rsync"):
                        self.asset_rsync[t.attrib["filemask"]] = t.attrib["rsync"]
                    if t.attrib.get("folder"):
                        self.asset_folders[t.attrib["filemask"]] = t.attrib["folder"]
                    elif node.attrib.get("folder"):
                        self.asset_folders[t.attrib["filemask"]] = node.attrib["folder"]
            if t.tag == "repos" and t.attrib.get("build_id_from_iso", ""):
                self.build_id_from_iso = 1

    def gen_if_not_customized(self, folder, fname):
        filename = folder + "/" + fname
        line1 = ""
        line2 = ""
        custom = 0
        if os.path.exists(filename):
            with open(filename, "r") as f:
                line1 = f.readline()
                line2 = f.readline()
                if line1 and not "GENERATED" in line1:
                    if not line1.lstrip().startswith("#"):
                        custom = 1
                    elif line2 and not "GENERATED" in line2:
                        custom = 1
        if custom:
            print("Will not overwrite custom file: " + filename, file=sys.stderr)
            return
        with open(filename, "w") as f:
            if fname == "read_files.sh":
                self.gen_read_files(f)
            elif fname == "print_rsync_iso.sh":
                self.gen_print_rsync_iso(f)
            elif fname == "print_rsync_repo.sh":
                self.gen_print_rsync_repo(f)
            elif fname == "print_openqa.sh":
                self.gen_print_openqa(f)

    def gen_repo(self, repodir, gen, f):
        if "$build" in gen:
            self.p(
                r"""build=$(grep -o -E '(Build|Snapshot)[^-]*' __envsub/files_iso.lst | grep -o -E '[0-9]\.?[0-9]+(\.[0-9]+)*' | head -n 1)""",
                f,
            )
        body = gen
        if repodir.attrib.get("source", ""):
            body = (
                body
                + """
"""
                + gen.replace("Media1", "Media2")
            )
        if repodir.attrib.get("debug", ""):
            body = (
                body
                + """
"""
                + gen.replace("Media1", "Media3")
            )
        self.p('echo "' + body + '" > __envsub/files_repo_' + repodir.attrib["folder"] + ".lst", f)

    def gen_read_files(self, f):
        self.p(cfg.header, f, "set -e", "set -eo pipefail")
        self.p(cfg.clear_lst, f)
        for hdd in self.hdds:
            if self.ag.productpath.startswith("http"):
                self.p(cfg.read_files_curl, f, "ISOMASK", hdd)
            else:
                awkpartfrom = """| awk '{ $1=$2=$3=$4=""; print substr($0,5); }' """
                awkpartto = awkpartfrom
                if not hdd.startswith(".*"):
                    awkpartto = ""

                if " " in self.archs:
                    self.p(
                        cfg.read_files_hdd,
                        f,
                        "FOLDER",
                        self.iso_folder.get(hdd, ""),
                        "ISOMASK",
                        hdd,
                        "| head -n 1",
                        "",
                        awkpartfrom,
                        awkpartto,
                    )
                else:
                    self.p(
                        cfg.read_files_hdd,
                        f,
                        "FOLDER",
                        self.iso_folder.get(hdd, self.hdd_folder.get(hdd, "")),
                        "ISOMASK",
                        hdd,
                        awkpartfrom,
                        awkpartto,
                    )
        if not self.isos and not self.hdds:
            for asset in self.assets:
                self.p(cfg.read_files_hdd, f, "FOLDER", self.asset_folders.get(asset, ""), "ISOMASK", asset)
        if self.iso_5:
            self.p(cfg.read_files_iso, f, "FOLDER", self.iso_folder.get(self.iso_5, ""), "SRCISO", self.iso_5)
        elif self.isos:
            # if isos don't belong to custom folder - just read them all with single command
            if not self.iso_folder and self.media1 != "0":
                # self.p(cfg.read_files_isos, f, "FOLDER", self.folder)
                self.p(cfg.read_files_isos, f)
            else:
                for iso in self.isos:
                    folder = self.iso_folder.get(iso, "")
                    if folder:
                        folder = folder + "/"

                    if "*" in iso:
                        self.p(
                            cfg.read_files_iso,
                            f,
                            "FOLDER/",
                            folder,
                            "SRCISO",
                            "",
                            "Media1?.iso$",
                            iso,
                            "(Media1?|install.*).iso$",
                            iso,
                        )
                    elif self.media1 != "0":
                        self.p(cfg.read_files_iso, f, "FOLDER/", folder, "SRCISO", iso)
                    else:
                        self.p(
                            cfg.read_files_iso,
                            f,
                            "FOLDER/",
                            folder,
                            "SRCISO",
                            iso,
                            "Media1?.iso$",
                            ".iso$",
                        )

        if self.isos_fixed:
            self.p("for arch in ARCHITECTURS; do", f)
            for iso in self.isos_fixed:
                self.p("  echo {} >> __envsub/files_iso.lst".format(iso), f)
            self.p("done", f)

        if self.repolink:
            self.p(cfg.read_files_repo_link, f)
        if self.repolink and self.build_id_from_iso:
            self.p(cfg.read_files_repo_link2, f)
        if self.repolink and not self.isos and not self.iso_5 and not self.hdds and not self.assets:
            self.p(cfg.read_files_repo_link3, f)
        if self.repos:
            if self.media1 == "0":
                self.p(
                    cfg.read_files_repo,
                    f,
                    "| grep -P 'Media1(.license)?$'",
                    "",
                    "| grep -P 'Media[1-3](.license)?$'",
                    "",
                )
            else:
                self.p(cfg.read_files_repo, f)
            if self.build_id_from_iso:
                self.p(
                    cfg.read_files_repo,
                    f,
                    "PRODUCTREPOPATH/",
                    "PRODUCTREPOPATH/../iso/",
                    "files_repo.lst",
                    "files_iso_buildid.lst",
                    "Media1(.license)?$",
                    "Media1?.iso$",
                )
            if any(repo.attrib.get(cfg.media2_name(), "") for repo in self.repos):
                self.p(
                    cfg.read_files_repo,
                    f,
                    "Media1",
                    "Media2",
                    "REPOORS",
                    "|".join(
                        [
                            m.attrib["name"] if "name" in m.attrib else m.tag
                            for m in filter(lambda x: x.attrib.get(cfg.media2_name(), ""), self.repos)
                        ]
                    ),
                )
            if any(repo.attrib.get(cfg.media3_name(), "") for repo in self.repos):
                self.p(
                    cfg.read_files_repo,
                    f,
                    "Media1",
                    "Media3",
                    "REPOORS",
                    "|".join(
                        [
                            m.attrib["name"] if "name" in m.attrib else m.tag
                            for m in filter(lambda x: x.attrib.get(cfg.media3_name(), ""), self.repos)
                        ]
                    ),
                )
        for repodir in self.repodirs:
            gen = repodir.attrib.get("gen", "")
            if gen:
                self.gen_repo(repodir, gen, f)
            else:
                archs = repodir.attrib.get("archs", "ARCHORS")
                txt = "PRODUCTREPOPATH"
                if self.version_from_media:
                    txt = "PRODUCTREPOPATH/"
                suffix = ""
                if repodir.attrib.get("suffix"):
                    suffix = repodir.attrib["suffix"]

                selffolder = ""
                if self.folder:
                    selffolder = "/" + self.folder
                if "/" in self.folder or "/" in repodir.attrib["folder"]:
                    repopath = self.ag.productpath + selffolder + "/*" + repodir.attrib["folder"] + "*" + suffix
                else:
                    repopath = self.ag.productrepopath() + selffolder + "/*" + repodir.attrib["folder"] + "*" + suffix

                args = (
                    cfg.read_files_repo,
                    f,
                    txt,
                    repopath,
                    "REPOORS",
                    "",
                    "files_repo.lst",
                    "files_repo_{}.lst".format(os.path.basename(repodir.attrib["folder"]).strip("*")),
                    "ARCHORS",
                    archs.replace(" ", "|").replace("armv7hl", "armv7hl|armv7l"),
                )
                if self.media1 == "0":
                    args += ("| grep -P 'Media[1-3](.license)?$'", "| grep -v .license")
                self.p(*args)

        # let's sync media.1/media to be able verify build_id
        if "ToTest" or "LEO" in self.ag.envdir or self.version_from_media:
            if "Leap" in self.ag.envdir or "Jump" in self.ag.envdir or self.version_from_media:
                for repodir in self.repodirs:
                    archs = self.archs
                    if not archs:
                        archs = self.ag.archs
                    wild = ""
                    arch = ""
                    done = ""
                    if archs and not " " in archs:
                        wild = "*" + archs + "*"

                    if " " in archs and self.repodirs and "1" != repodir.attrib.get("multiarch", ""):
                        self.p("for arch in {}; do".format(archs), f)
                        wild = "*$arch*"
                        arch = "$arch"
                        done = "done"

                    selffolder = ""
                    if self.folder:
                        selffolder = "/" + self.folder
                    if "/" in self.folder or "/" in repodir.attrib["folder"]:
                        repopath = self.ag.productpath + selffolder + "/*" + repodir.attrib["folder"] + wild
                    else:
                        repopath = self.ag.productrepopath() + selffolder + "/*" + repodir.attrib["folder"] + wild

                    Media1Replace = "*Media1"
                    if self.media1 == "0":
                        Media1Replace = "*"
                    self.p(
                        cfg.read_files_repo_media,
                        f,
                        "PRODUCTREPOPATH",
                        repopath,
                        "Media1.lst",
                        "Media1_{}.lst".format(
                            os.path.basename(repodir.attrib["folder"]).strip("*") + repodir.get("archs", arch)
                        ),
                        "*Media1",
                        Media1Replace,
                    )

                    if done:
                        self.p(done, f)

        if self.assets and self.assets_flavor:
            for k, v in self.asset_folders.items():
                self.p(
                    """rsync -4 --list-only $rsync_pwd_option PRODUCTPATH/{}/*{} | awk '{{ $1=$2=$3=$4=""; print substr($0,5); }}' >> __envsub/files_asset.lst""".format(
                        v, k
                    ),
                    f,
                )

    def gen_print_array_no_rsync(self, f):
        self.p("declare -A norsync_filter", f)
        for fl in self.norsync:
            self.p("norsync_filter[{}]='{}'".format(fl, 1), f)
        for fl, h in zip(self.flavors, self.assets):
            if self.asset_rsync.get(h, 1) == "0":
                self.p("norsync_filter[{}]='{}'".format(h, 1), f)

    def gen_print_array_flavor_filter(self, f):
        added_declare_flavor_filter = 0
        if self.hdds or self.assets or self.flavor_aliases:
            self.p("declare -A flavor_filter", f)
            added_declare_flavor_filter = 1
        # this assumes every flavor has hdd_url - we must store relation if that is not the case
        for fl, h in zip(self.flavors, self.hdds):
            self.p("flavor_filter[{}]='{}'".format(fl, h), f)
        if not self.isos and not self.hdds:
            for fl, h in zip(self.flavors, self.assets):
                self.p("flavor_filter[{}]='{}'".format(fl, h), f)
        if not self.assets and ((not self.hdds) or len(self.flavors) == 1):
            for fl, iso in zip(self.flavors, self.isos):
                if iso != "1" and iso != "0" and iso != "extract_as_repo":
                    if not added_declare_flavor_filter:
                        self.p("declare -A flavor_filter", f)
                        added_declare_flavor_filter = 1
                    self.p("flavor_filter[{}]='{}'".format(fl, iso), f)
        for fl, alias_list in self.flavor_aliases.items():
            for alias in alias_list:
                self.p("flavor_filter[{}]='{}'".format(alias, fl), f)

        if len(self.staging_pattern) > 0:
            self.p("declare -A flavor_staging", f)
            for k, v in self.staging_pattern.items():
                self.p("flavor_staging[{}]='{}'".format(k, v), f)
        if len(self.iso1) > 0:
            self.p("declare -A flavor_iso1", f)
            for k, v in self.iso1.items():
                self.p("flavor_iso1[{}]='{}'".format(k, v), f)

    def gen_print_array_flavor_distri(self, f):
        if self.news:
            self.p("declare -A news", f)
        if not self.flavor_distri:
            return
        self.p("declare -A flavor_distri", f)
        for fl, distri in self.flavor_distri.items():
            self.p("flavor_distri[{}]='{}'".format(fl, distri), f)

    def gen_print_array_iso_folder(self, f):
        if self.iso_folder:
            self.p("declare -A iso_folder", f)
        for k, v in self.iso_folder.items():
            self.p("iso_folder[{}]='{}/'".format(k, v), f)

    def gen_print_array_hdd_folder(self, f):
        if ((len(self.hdd_folder) > 1) or (self.hdd_folder and self.isos)) and len(self.flavors) == 1:
            self.p("declare -A hdd_folder", f)
            for k, v in self.hdd_folder.items():
                self.p("hdd_folder[{}]='{}'".format(k, v), f)

    def gen_print_rsync_assets(self, f):
        self.p(
            """echo ""
echo "# Syncing assets"
declare -A asset_folders""",
            f,
        )
        for k, v in self.asset_folders.items():
            self.p("asset_folders[{}]='{}'".format(k, v), f)
        self.p(
            """while read src; do
    folder=""
    for mask in "${!asset_folders[@]}"; do
        [[ $src =~ $mask ]] || continue
        folder=${asset_folders[$mask]}
        break
    done
    echo "rsync --timeout=3600 -tlp4 --specials PRODUCTPATH/$folder/*$src /var/lib/openqa/factory/other/"
done < <(LANG=C.UTF-8 sort __envsub/files_asset.lst)""",
            f,
        )

    def gen_print_rsync_iso(self, f):
        print(cfg.header, file=f)
        self.gen_print_array_no_rsync(f)
        if ((len(self.hdds) > 1 and (not self.isos)) or (self.isos and self.hdds)) and len(self.flavors) < 2:
            self.gen_print_array_hdd_folder(f)
            if self.archs == "armv7hl":
                self.p(cfg.rsync_hdds, f, "grep ${arch}", "grep ${arch//armv7hl/armv7l}")
            else:
                self.p(cfg.rsync_hdds, f)
        elif self.isos or self.iso_5 or (self.hdds and not self.productpath().startswith("http")) or self.assets:
            self.gen_print_array_flavor_filter(f)
            self.gen_print_array_iso_folder(f)
            if self.mask:
                self.p(
                    cfg.rsync_iso(
                        self.ag.distri,
                        self.ag.version,
                        self.archs,
                        self.ag.staging(),
                        self.checksum,
                        self.repo0folder,
                        len(self.staging_pattern),
                    ),
                    f,
                    "| head -n 1",
                    "| grep {} | head -n 1".format(self.mask),
                )
            else:
                self.p(
                    cfg.rsync_iso(
                        self.ag.distri,
                        self.ag.version,
                        self.archs,
                        self.ag.staging(),
                        self.checksum,
                        self.repo0folder,
                        len(self.staging_pattern),
                    ),
                    f,
                )
        elif self.assets:
            self.gen_print_array_flavor_filter(f)
            self.p(
                cfg.rsync_iso(
                    self.ag.distri,
                    self.ag.version,
                    self.archs,
                    self.ag.staging(),
                    self.checksum,
                    self.repo0folder,
                    len(self.staging_pattern),
                ),
                f,
            )

        if self.assets and (self.isos or self.hdds):
            self.gen_print_rsync_assets(f)

    def gen_print_rsync_repo(self, f):
        print(cfg.header, file=f)
        if self.ag.version:
            print("version=" + self.ag.version, file=f)

        if self.reposmultiarch:
            self.p(cfg.rsync_repo_buildid, f)
            for repo in self.reposmultiarch:
                rsync_timeout = repo.get("rsynctimeout", self.rsync_timeout)
                destpath = repo.get("folder", repo.tag)
                dest = os.path.basename(destpath)
                self.p(
                    cfg.rsync_repomultiarch(
                        repo.get("folder", repo.tag), repo.get("debug", ""), repo.get("source", "")
                    ),
                    f,
                    "RSYNCTIMEOUT",
                    rsync_timeout,
                )

        if self.repos:
            self.p(cfg.pre_rsync_repo(self.repos), f)
            self.p(cfg.rsync_repo1, f)
            for ren in self.renames:
                self.p("        dest=${{dest//{}/{}}}".format(ren[0], ren[1]), f)
            if self.build_id_from_iso:
                self.p(
                    """        buildid1=$(grep $repo __envsub/files_iso_buildid.lst | grep -o -E '(Build|Snapshot)[^-]*' | head -n 1)
         [ -z "$buildid1" ] || buildid=$buildid1""",
                    f,
                )

            self.p(cfg.rsync_repo2, f)

        xtrapath = "/*"
        if self.folder:
            xtrapath = "/" + self.folder + "/*"
        for r in self.repodirs:
            if r.attrib.get("gen", ""):
                continue
            if self.media1 == "0" and "1" == r.attrib.get("multiarch", ""):
                rsync_timeout = r.attrib.get("rsynctimeout", self.rsync_timeout)
                self.p(
                    cfg.rsync_remodir_multiarch,
                    f,
                    "files_repo.lst",
                    "files_repo_{}.lst".format(os.path.basename(r.attrib["folder"]).strip("*")),
                    "PRODUCTREPOPATH",
                    self.productrepopath() + xtrapath + r.attrib["folder"],
                    "RSYNCTIMEOUT",
                    rsync_timeout,
                )
                if r.attrib.get("debug", ""):
                    self.p(
                        cfg.rsync_remodir_multiarch_debug,
                        f,
                        "files_repo.lst",
                        "files_repo_{}.lst".format(os.path.basename(r.attrib["folder"]).strip("*")),
                        "PRODUCTREPOPATH",
                        self.productrepopath() + xtrapath + r.attrib["folder"],
                        "RSYNCFILTER",
                        " --include=PACKAGES --exclude={aarch64,armv7hl,i586,i686,noarch,nosrc,ppc64,ppc64le,riscv64,s390x,src,x86_64}/*".replace(
                            "PACKAGES", r.attrib["debug"]
                        ),
                        "RSYNCTIMEOUT",
                        rsync_timeout,
                    )
                continue

            if not r.attrib.get("dest", ""):
                self.p(cfg.rsync_repodir1, f, "mid=''", "mid='{}'".format(r.attrib.get("mid", "")))
            elif self.media1 == "0":
                self.p(
                    cfg.rsync_repodir1_dest_media0(
                        r.attrib["dest"], r.get("debug", ""), r.get("source", ""), r.attrib["folder"]
                    ),
                    f,
                )
                continue
            elif not r.attrib.get("gen", ""):
                self.p(cfg.rsync_repodir1_dest(r.attrib["dest"]), f)

            for ren in self.renames:
                self.p("        dest=${{dest//{}/{}}}".format(ren[0], ren[1]), f)
            suffix = "*$arch*"
            if self.archs_repo == ".":
                suffix = "*"
            self.p(
                cfg.rsync_repodir2(),
                f,
                "PRODUCTREPOPATH",
                self.productpath() + xtrapath + r.attrib["folder"] + suffix,
                "files_repo.lst",
                "files_repo_{}.lst".format(os.path.basename(r.attrib["folder"]).strip("*")),
                "Media2",
                "Media1",
                "-debuginfo",
                "",
                "RSYNCFILTER",
                "",
            )
            if r.attrib.get("debug", ""):
                if not r.attrib.get("dest", ""):
                    self.p(cfg.rsync_repodir1, f, "mid=''", "mid='{}'".format(r.attrib.get("mid", "")))
                else:
                    self.p(cfg.rsync_repodir1_dest(r.attrib["dest"]), f)
                for ren in self.renames:
                    self.p("        dest=${{dest//{}/{}}}".format(ren[0], ren[1]), f)
                self.p(
                    cfg.rsync_repodir2(),
                    f,
                    "PRODUCTREPOPATH",
                    self.productpath() + xtrapath + r.attrib["folder"] + suffix,
                    "files_repo.lst",
                    "files_repo_{}.lst".format(os.path.basename(r.attrib["folder"]).strip("*")),
                    "RSYNCFILTER",
                    " --include=PACKAGES --exclude={aarch64,armv7hl,i586,i686,noarch,nosrc,ppc64,ppc64le,riscv64,s390x,src,x86_64}/*".replace(
                        "PACKAGES", r.attrib["debug"]
                    ),
                )
            if r.attrib.get("source", ""):
                if not r.attrib.get("dest", ""):
                    self.p(cfg.rsync_repodir1, f, "mid=''", "mid='{}'".format(r.attrib.get("mid", "")))
                else:
                    self.p(cfg.rsync_repodir1_dest(r.attrib["dest"]), f)
                for ren in self.renames:
                    self.p("        dest=${{dest//{}/{}}}".format(ren[0], ren[1]), f)
                if self.ag.brand == "obs":
                    self.p(
                        cfg.rsync_repodir2(),
                        f,
                        "PRODUCTREPOPATH",
                        self.productpath() + xtrapath + r.attrib["folder"] + suffix,
                        "files_repo.lst",
                        "files_repo_{}.lst".format(os.path.basename(r.attrib["folder"]).strip("*")),
                        "RSYNCFILTER",
                        " --include=PACKAGES --exclude={aarch64,armv7hl,i586,i686,noarch,nosrc,ppc64,ppc64le,riscv64,s390x,src,x86_64}/*".replace(
                            "PACKAGES", r.attrib["source"]
                        ),
                        "Media2",
                        "Media3",
                        "-debuginfo",
                        "-source",
                    )

    def gen_print_openqa(self, f):
        print(cfg.header, file=f)
        self.p(cfg.pre_openqa_call_start(self.repos), f)
        self.gen_print_array_no_rsync(f)
        self.gen_print_array_flavor_filter(f)
        self.gen_print_array_flavor_distri(f)
        self.gen_print_array_hdd_folder(f)
        if self.assets and self.assets_flavor:
            self.p("declare -A asset_tags", f)
            for k, v in self.asset_tags.items():
                self.p("asset_tags[{}]='{}'".format(k, v), f)

        if not self.flavors and not self.flavor_aliases:
            return
        if self.mask:
            self.p(
                cfg.openqa_call_start(
                    self.ag.distri,
                    self.ag.version,
                    self.archs,
                    self.ag.staging(),
                    self.news,
                    self.news_archs,
                    self.flavor_distri,
                    self.meta_variables,
                    self.assets_flavor,
                    self.repo0folder,
                    self.ag.openqa_cli,
                ),
                f,
                "| grep $arch | head -n 1",
                "| grep {} | grep $arch | head -n 1".format(self.mask),
            )
        else:
            self.p(
                cfg.openqa_call_start(
                    self.ag.distri,
                    self.ag.version,
                    self.archs,
                    self.ag.staging(),
                    self.news,
                    self.news_archs,
                    self.flavor_distri,
                    self.meta_variables,
                    self.assets_flavor,
                    self.repo0folder,
                    self.ag.openqa_cli,
                ),
                f,
            )

        imultiarch = 0
        mirrorsalreadyadded = False
        for repo in self.reposmultiarch:
            destpath = repo.get("folder", repo.tag)
            destpath = destpath.rstrip("/")
            dest = os.path.basename(destpath)
            self.p(' echo " REPO_{}={}-$buildex" \\\\'.format(imultiarch, dest), f)
            self.p(' echo " REPO_{}={}-$buildex" \\\\'.format(repo.tag.upper(), dest), f)
            imultiarch = imultiarch + 1
            if repo.get("debug", ""):
                self.p(' echo " REPO_{}={}-Debug-$buildex" \\\\'.format(imultiarch, dest), f)
                self.p(' echo " REPO_{}_DEBUG={}-Debug-$buildex" \\\\'.format(repo.tag.upper(), dest), f)
                self.p(" echo \" REPO_{}_DEBUG_PACKAGES='{}'\" \\\\".format(repo.tag.upper(), repo.get("debug", "")), f)
                imultiarch = imultiarch + 1
            if repo.get("source", ""):
                self.p(' echo " REPO_{}={}-Source-$buildex" \\\\'.format(imultiarch, dest), f)
                self.p(' echo " REPO_{}_SOURCE={}-Source-$buildex" \\\\'.format(repo.tag.upper(), dest), f)
                self.p(
                    " echo \" REPO_{}_SOURCE_PACKAGES='{}'\" \\\\".format(repo.tag.upper(), repo.get("source", "")), f
                )
                imultiarch = imultiarch + 1
            if imultiarch > 0 and repo.get("mirror", 0) and not mirrorsalreadyadded:
                self.p(cfg.openqa_call_repo_unconditional(), f, "REPO0_ISO", "{}-$buildex".format(dest))
                mirrorsalreadyadded = True

        if len(self.iso1) > 0:
            self.p(' iso1=""', f)
            self.p(
                ' [ -z "${flavor_iso1[${flavor#Staging-}]}" ] || iso1=$(grep "${flavor_iso1[${flavor#Staging-}]}" __envsub/files_iso.lst 2>/dev/null | grep $arch | head -n 1)',
                f,
            )
            if self.ag.staging:
                self.p(
                    ' [ -z "$iso1" ] || echo " ISO_1=${iso1//${flavor_iso1[${flavor#Staging-}]}/Staging:__STAGING-${flavor_iso1[${flavor#Staging-}]}} \\\\"',
                    f,
                )
            else:
                self.p(' [ -z "$iso1" ] || echo " ISO_1=$iso1 \\\\"', f)
        if len(self.staging_pattern) > 0:
            self.p(' staging_pattern="${flavor_staging[${flavor#Staging-}]}"', f)
            self.p(
                ' [ -z "$staging_pattern" ] || destiso=${destiso//$staging_pattern/Staging:__STAGING-$staging_pattern}',
                f,
            )

        if self.repolink and not self.iso_5:
            self.p(cfg.openqa_call_legacy_builds_link, f)
        if self.legacy_builds or (self.repolink and not self.iso_5):
            self.p(cfg.openqa_call_legacy_builds, f)

        i = 0
        isos = self.isos.copy()
        if ((len(self.hdds) > 1 and not self.isos) or (self.hdds and self.isos)) and len(self.flavors) == 1:
            if self.archs == "armv7hl":
                self.p(cfg.openqa_call_start_hdds, f, "grep ${arch}", "grep ${arch//armv7hl/armv7l}")
            else:
                self.p(cfg.openqa_call_start_hdds, f, "i=1", "i=" + self.offset)
        elif self.hdds or (self.assets and not self.isos):
            if self.hdds and self.productpath().startswith("http"):
                self.p(' echo " HDD_URL_1=PRODUCTPATH/$destiso \\\\"', f)
            else:
                self.p(cfg.openqa_call_start_ex(self.checksum), f)
        else:
            if self.iso_5:
                if self.fixed_iso:
                    self.p(' echo " ISO={} \\\\"'.format(self.fixed_iso), f)
                self.p(cfg.openqa_call_start_iso(self.checksum), f, "ISO", "ISO_5")
            else:
                self.p(cfg.openqa_call_start_iso(self.checksum), f)
            if not isos and self.iso_5:
                isos = [self.iso_5]

        for iso in isos:
            if self.iso_extract_as_repo.get(iso, 0) or self.iso_5:
                destiso = "${repo0folder}"
                i += 1
                s = ""
                if not self.fixed_iso:
                    self.p(cfg.openqa_call_repo0(), f, "REPO0_ISO", destiso, f)
                    s = cfg.openqa_call_repo0a + cfg.openqa_call_repo0b
                else:
                    s = cfg.openqa_call_repo0b
                    destiso = self.fixed_iso[:-4]
                self.p(s, f, "REPO0_ISO", destiso)
                if self.ln_iso_to_repo.get(iso, 0):
                    self.p(s, f, "REPO_0", "REPO_999", "REPO0_ISO", destiso + ".iso")
                if self.iso_5:
                    pref = self.iso_5.replace("-", "_").rstrip("_DVD")
                    self.p(cfg.openqa_call_repo5, f, "REPOALIAS", "SLE_{}".format(pref))
                break  # for now only REPO_0

        arch_expression = ""
        if self.assets_archs:
            arch_expression = '|| [ "$arch" != ' + self.assets_archs + " ]"
        if self.assets and self.assets_flavor:
            self.p(
                """ i=1
 [[ ! "$flavor" =~ """
                + self.assets_flavor
                + """ ]] """
                + arch_expression
                + """ || [[ ${norsync_filter[$filter]} == 1 ]] || while read src; do
     echo " ASSET_$i=$src \\\\"
     asset_tag=""
     for mask in "${!asset_tags[@]}"; do
         [[ $src =~ $mask ]] || continue
         asset_tag=${asset_tags[$mask]}
         break
      done
      [ -z "$asset_tag" ] || echo " ASSET_${asset_tag^^}=$src \\\\"
      : $((i++))
  done < <(grep ${arch} __envsub/files_asset.lst | LANG=C.UTF-8 sort)""",
                f,
            )

        self.p(" i={}".format(i), f)

        if self.repos or self.repolink:
            if self.ag.brand == "ibs":
                self.p(" i=9", f)  # temporary to simplify diff with old rsync scripts, may be removed later
            # some trickery for REPO_SLE_ vs REPO_SL_ variables in ibs
            sl = "SLE_"
            for r in self.repos:
                if r.tag.startswith("SL"):
                    sl = ""
                    break
            self.p(cfg.openqa_call_repot(self.build_id_from_iso, self.repos), f, "REPOTYPE", "''", "REPOPREFIX", sl)

        repodirs = self.repodirs
        if not repodirs and self.repolink:
            repodirs = self.ag.batch_by_name(self.repolink).repodirs

        for r in repodirs:
            if r.attrib.get("dest", "") == "":
                self.p(
                    cfg.openqa_call_repot1(r.get("debug", ""), r.get("source", "")),
                    f,
                    "REPOKEY",
                    r.attrib.get("rename", r.tag),
                    "mid=''",
                    "mid='{}'".format(r.attrib.get("mid", "")),
                )
            else:
                self.p(
                    cfg.openqa_call_repot1_dest(r.attrib["dest"], r.get("debug", ""), r.get("source", "")),
                    f,
                    "REPOKEY",
                    r.attrib.get("rename", r.tag),
                )

            for ren in self.renames:
                self.p("            dest=${{dest//{}/{}}}".format(ren[0], ren[1]), f)
            if i == 0:
                self.p(
                    "            [ $i != 0 ] || {{ {};  }}".format(cfg.openqa_call_repo0()), f, "REPO0_ISO", "$dest", f
                )
            media_filter = ""
            if self.media1 != "0" and (r.attrib.get("debug", "") == "" or r.attrib.get("source", "") == ""):
                if r.attrib.get("debug", "") == "" and r.attrib.get("source", "") == "":
                    media_filter = "| grep Media1 "
                elif r.attrib.get("debug", "") == "":
                    media_filter = "| grep -E '(Media1|Media3)' "
                else:
                    media_filter = "| grep -E '(Media1|Media2)' "
            self.p(
                cfg.openqa_call_repot2.format(media_filter),
                f,
                "files_repo.lst",
                "files_repo_{}.lst".format(os.path.basename(r.attrib["folder"]).strip("*")),
                "DEBUG_PACKAGES",
                r.attrib.get("debug", "").strip("{}"),
                "SOURCE_PACKAGES",
                r.attrib.get("source", "").strip("{}"),
            )

        if self.ag.staging():
            self.p("echo ' STAGING=__STAGING \\'", f)
        if self.variable:
            self.p('echo " {} \\\\"'.format(self.variable), f)

        self.p(cfg.openqa_call_end(self.ag.version), f)
        self.p(cfg.openqa_call_news_end(self.distri, self.news, self.news_archs), f)


def parse_dir(root, d, files):
    for f in files:
        if not f.endswith(".xml"):
            continue

        rootXml = ElementTree.parse(root + "/" + f).getroot()
        if rootXml is None:
            print("Ignoring [" + f + "]: Cannot parse xml", file=sys.stderr)
            continue

        pattern = rootXml.attrib.get("project_pattern", "")
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
        version = found_match.groupdict().get("version", "")
        if version.find("'") != -1:
            print(
                "OBS: Ignoring [" + d + "]: Version cannot contain quote characters; got: " + version, file=sys.stderr
            )
            continue

        dist_path = rootXml.attrib.get("dist_path", "")
        if dist_path.find('"') != -1:
            print(
                "OBS: Ignoring [" + d + "]: dist_path cannot contain quote characters; got: " + dist_path,
                file=sys.stderr,
            )
            continue
        if dist_path.find("`") != -1:
            print(
                "OBS: Ignoring [" + d + "]: dist_path cannot contain backtick characters; got: " + dist_path,
                file=sys.stderr,
            )
            continue
        if dist_path.find("$(") != -1:
            print(
                "OBS: Ignoring [" + d + "]: dist_path cannot contain '$(' characters; got: " + dist_path,
                file=sys.stderr,
            )
            continue

        # make substitutions of common variables if needed
        if dist_path:
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


def detect_xml_dir(project):
    # if project has no path
    if not "/" in project:
        return os.getcwd()[-3:]

    return os.path.dirname(project)[-3:]


def gen_files(project):
    project = project.rstrip("/")
    xmlfile = ""

    xmldir = detect_xml_dir(project)

    for root, _, files in os.walk("xml/" + xmldir):
        (xmlfile, dist_path, version) = parse_dir(root, project, files)

    if not xmlfile:
        print("Cannot find xml file for {} ...".format(project), file=sys.stderr)
        return 1

    if xmldir == "abs":
        import abs
    if xmldir == "ibs":
        import ibs

    a = ActionGenerator(os.getcwd(), project, dist_path, version, xmldir)
    if a is None:
        print("Couldnt initialize", file=sys.stderr)
        sys.exit(1)

    a.doFile(xmlfile)

    for batch in a.batches:
        path = project
        if batch.subfolder != "default":
            path = project + "/" + batch.subfolder
            if not os.path.exists(path):
                os.mkdir(path)
        batch.gen_if_not_customized(path, "read_files.sh")
        batch.gen_if_not_customized(path, "print_rsync_iso.sh")
        batch.gen_if_not_customized(path, "print_rsync_repo.sh")
        batch.gen_if_not_customized(path, "print_openqa.sh")

    return 0


if __name__ == "__main__":
    # execute only if run as the entry point into the program
    parser = argparse.ArgumentParser(
        description="Generate scripts for OBS project synchronization according to XML definition."
    )
    parser.add_argument("project", nargs="?", help="Folder matching OBS project")

    class Args:
        pass

    args = Args()
    parser.parse_args(namespace=args)

    ret = 1

    if args.project:
        print("Generating scripts for " + args.project)
        ret = gen_files(args.project)
        if ret == 0:
            print("OK")

    sys.exit(ret)
