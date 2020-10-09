#!/usr/bin/python3
# Copyright (c) 2020 SUSE LLC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from base64 import b64decode
from binascii import hexlify
from lxml import etree as ET


# filename -> { url: <string>, sum: <string>, path = set([<string>, ..]) }
MODULE_MAP = dict()

# this is a hack for obs_scm integration
OBS_SCM_COMPRESSION = None

def update_checksum(fn):
    with open(fn, 'rb') as fh:
        h = hashlib.new(MODULE_MAP[fn].setdefault("algo", 'sha256'), fh.read())
        MODULE_MAP[fn]["chksum"] = h.hexdigest()


def collect_deps_recursive(d, deps):
    for module in sorted(deps):
        path = "/".join(("node_modules", module))
        if d:
            path = "/".join((d, path))
        entry = deps[module]
        if "bundled" in entry and entry["bundled"]:
            continue
        elif "resolved" not in entry:
            if "from" in entry:
                o = urllib.parse.urlparse(entry["from"])
                if o.scheme in ("git+http", "git+https"):
                    _, scheme = o.scheme.split("+")
                    branch = "master"
                    # XXX: not sure that is correct
                    if o.fragment:
                        branch = o.fragment
                    p = os.path.basename(o.path)
                    if p.endswith(".git"):
                        p = p[:-4]
                    if OBS_SCM_COMPRESSION:
                        fn = "{}-{}.tar.{}".format(p, branch, OBS_SCM_COMPRESSION)
                    else:
                        fn = "{}-{}.tgz".format(p, branch)
                    MODULE_MAP[fn] = {
                        "scm": "git",
                        "branch": branch,
                        "basename": p,
                        "url": urllib.parse.urlunparse(
                            (scheme, o.netloc, o.path, o.params, o.query, None)
                        ),
                    }

                    MODULE_MAP[fn].setdefault("path", set()).add(path)

                else:
                    logging.warning(
                        "entry %s is from unsupported location %s",
                        module,
                        entry["from"],
                    )

            else:
                logging.warning("entry %s has no download", module)
        else:
            url = entry["resolved"]
            algo, chksum = entry["integrity"].split("-", 2)
            chksum = hexlify(b64decode(chksum)).decode("ascii")
            fn = os.path.basename(url)
            # looks like some module are from some kind of branch and
            # may use the same file name. So prefix with this
            # namespace.
            if "/" in module:
                fn = module.split("/")[0] + "-" + fn
            if fn in MODULE_MAP:
                if (
                    MODULE_MAP[fn]["url"] != url
                    or MODULE_MAP[fn]["algo"] != algo
                    or MODULE_MAP[fn]["chksum"] != chksum
                ):
                    logging.error(
                        "%s: mismatch %s <> %s, %s:%s <> %s:%s",
                        module,
                        MODULE_MAP[fn]["url"],
                        url,
                        MODULE_MAP[fn]["algo"],
                        MODULE_MAP[fn]["chksum"],
                        algo,
                        chksum,
                    )
            else:
                MODULE_MAP[fn] = {"url": url, "algo": algo, "chksum": chksum}

            MODULE_MAP[fn].setdefault("path", set()).add(path)

        if "dependencies" in entry:
            collect_deps_recursive(path, entry["dependencies"])

def write_rpm_sources(fh, args):
    i = args.source_offset if args.source_offset is not None else ''
    for fn in sorted(MODULE_MAP):
        fh.write("Source{}:         {}#/{}\n".format(i, MODULE_MAP[fn]["url"], fn))
        if args.source_offset is not None:
            i += 1

def main(args):
    logging.info("main")

    def _out(fn):
        return os.path.join(args.outdir, fn) if args.outdir else fn

    with open(args.input) as fh:
        js = json.load(fh)

    if "dependencies" in js:
        collect_deps_recursive("", js["dependencies"])

    if args.output:
        with open(_out(args.output), "w") as fh:
            write_rpm_sources(fh, args)

    if args.spec:
        ok = False
        newfn = _out(args.spec)
        if not args.outdir:
            newfn += '.new'
        with open(newfn, "w") as ofh:
            with open(args.spec, "r") as ifh:
                for line in ifh:
                    if line.startswith('# NODE_MODULES BEGIN'):
                        ofh.write(line)
                        for line in ifh:
                            if line.startswith('# NODE_MODULES END'):
                                write_rpm_sources(ofh, args)
                                ok = True
                                break

                    ofh.write(line)
        if not ok:
            raise Exception("# NODE_MODULES [BEGIN|END] not found")
        if not args.outdir:
            os.rename(args.spec+".new", args.spec)

    if args.locations:
        with open(_out(args.locations), "w") as fh:
            for fn in sorted(MODULE_MAP):
                fh.write("{} {}\n".format(fn, " ".join(sorted(MODULE_MAP[fn]["path"]))))

    if args.download:
        for fn in sorted(MODULE_MAP):
            if args.file and fn not in args.file:
                continue
            url = MODULE_MAP[fn]["url"]
            if "scm" in MODULE_MAP[fn]:
                d = MODULE_MAP[fn]["basename"]
                if os.path.exists(d):
                    r = subprocess.run(["git", "remote", "update"], cwd=d)
                    if r.returncode:
                        logging.error("failed to clone %s", url)
                        continue
                else:
                    r = subprocess.run(["git", "clone", "--bare", url, d])
                    if r.returncode:
                        logging.error("failed to clone %s", url)
                        continue
                r = subprocess.run(
                    [
                        "git",
                        "archive",
                        "--format=tar." + (OBS_SCM_COMPRESSION if OBS_SCM_COMPRESSION else 'gz'),
                        "-o",
                        _out(fn),
                        "--prefix",
                        "package/",
                        MODULE_MAP[fn]["branch"],
                    ],
                    cwd=d,
                )
                if not args.outdir:
                    os.rename(os.path.join(d, fn), fn)
                if r.returncode:
                    logging.error("failed to create tar %s", url)
                    continue
            else:
                req = urllib.request.Request(url)
                if os.path.exists(_out(fn)):
                    if args.download_skip_existing:
                        logging.info("skipping download of existing %s", fn)
                        continue
                    stamp = time.strftime(
                        "%a, %d %b %Y %H:%M:%S GMT", time.gmtime(os.path.getmtime(_out(fn)))
                    )
                    logging.debug("adding If-Modified-Since %s: %s", fn, stamp)
                    req.add_header("If-Modified-Since", stamp)

                logging.info("fetching %s as %s", url, fn)
                algo = MODULE_MAP[fn]["algo"]
                chksum = MODULE_MAP[fn]["chksum"]
                h = hashlib.new(algo)
                response = urllib.request.urlopen(req)
                try:
                    data = response.read()
                    h.update(data)
                    if h.hexdigest() != chksum:
                        logging.error(
                            "checksum failure for %s %s %s %s",
                            fn,
                            algo,
                            h.hexdigest,
                            chksum,
                        )
                    else:
                        try:
                            with open(_out(fn) + ".new", "wb") as fh:
                                fh.write(data)
                        except OSError as e:
                            logging.error(e)
                        finally:
                            os.rename(_out(fn) + ".new", _out(fn))
                except urllib.error.HTTPError as e:
                    logging.error(e)

    if args.checksums:
        with open(_out(args.checksums), "w") as fh:
            for fn in sorted(MODULE_MAP):
                if 'algo' not in MODULE_MAP[fn]:
                    update_checksum(_out(fn))
                fh.write(
                    "{} ({}) = {}\n".format(
                        MODULE_MAP[fn]["algo"].upper(), fn, MODULE_MAP[fn]["chksum"]
                    )
                )

    if args.obs_service:
        parser = ET.XMLParser(remove_blank_text=True)
        tree = ET.parse(args.obs_service, parser)
        root = tree.getroot()
        # to make sure pretty printing works
        for element in root.iter():
            element.tail = None

        if not args.obs_service_scm_only:
            # FIXME: remove only entries we added?
            for node in root.findall("service[@name='download_url']"):
                root.remove(node)

        tar_scm_toremove = set()
        for fn in sorted(MODULE_MAP):
            if "scm" in MODULE_MAP[fn]:
                tar_scm_toremove.add(MODULE_MAP[fn]['url'])

        for u in tar_scm_toremove:
            for node in root.findall("service[@name='obs_scm']"):
                if node.find("param[@name='url']").text == u:
                    root.remove(node)

        for fn in sorted(MODULE_MAP):
            if args.file and fn not in args.file:
                continue
            url = MODULE_MAP[fn]["url"]
            if "scm" in MODULE_MAP[fn]:
                s = ET.SubElement(root, 'service', { 'name': 'obs_scm'})
                ET.SubElement(s, 'param', { 'name': 'scm'}).text = "git"
                ET.SubElement(s, 'param', { 'name': 'url'}).text = MODULE_MAP[fn]["url"]
                ET.SubElement(s, 'param', { 'name': 'revision'}).text = MODULE_MAP[fn]["branch"]
                ET.SubElement(s, 'param', { 'name': 'version'}).text = MODULE_MAP[fn]["branch"]
            elif not args.obs_service_scm_only:
                s = ET.SubElement(root, 'service', { 'name': 'download_url'})
                ET.SubElement(s, 'param', { 'name': 'url'}).text = MODULE_MAP[fn]["url"]
                ET.SubElement(s, 'param', { 'name': 'prefer-old'}).text = 'enable'

        tree.write(args.obs_service, pretty_print=True)

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="boilerplate python commmand line program"
    )
    parser.add_argument("--dry", action="store_true", help="dry run")
    parser.add_argument("--debug", action="store_true", help="debug output")
    parser.add_argument("--verbose", action="store_true", help="verbose")
    parser.add_argument(
        "-i",
        "--input",
        metavar="FILE",
        default="package-lock.json",
        help="input package lock file",
    )
    parser.add_argument(
        "-f", "--file", nargs="+", metavar="FILE", help="limit to file"
    )
    parser.add_argument(
        "-o", "--output", metavar="FILE", help="spec files source lines into that file"
    )
    parser.add_argument(
        "--spec", metavar="FILE", help="spec file to process"
    )
    parser.add_argument(
        "--source-offset", metavar="N", type=int, help="Spec file source offset"
    )
    parser.add_argument(
        "--checksums", metavar="FILE", help="Write BSD style checksum file"
    )
    parser.add_argument(
        "--locations", metavar="FILE", help="Write locations into that file"
    )
    parser.add_argument(
        "--obs-service", metavar="FILE", help="OBS service file for download_url"
    )
    parser.add_argument(
        "--outdir", metavar="DIR", help="where to put files"
    )
    parser.add_argument(
        "--compression", metavar="EXT", help="use EXT compression"
    )
    parser.add_argument(
        "--obs-service-scm-only",
        action="store_true",
        help="only generate tar_scm entries in service file",
    )

    parser.add_argument("--download", action="store_true", help="download files")
    parser.add_argument(
        "--download-skip-existing",
        action="store_true",
        help="don't download existing files again",
    )

    args = parser.parse_args()

    if args.debug:
        level = logging.DEBUG
    elif args.verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(format='%(levelname)s:%(message)s', level=level)

    if args.compression:
        OBS_SCM_COMPRESSION = args.compression
    elif args.obs_service:
        OBS_SCM_COMPRESSION = 'xz'

    sys.exit(main(args))

# vim: sw=4 et
