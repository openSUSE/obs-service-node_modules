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

from pprint import pprint
import os, sys, re
import logging
import argparse
import json
from base64 import b64decode
from binascii import hexlify

# filename -> { url: <string>, sum: <string>, path = set([<string>, ..]) }
module_map = dict()

def collect_deps_recursive(d, deps):

    for module in sorted(deps.keys()):
        path='/'.join(('node_modules', module))
        if d:
            path='/'.join((d, path))
        entry = deps[module]
        if 'resolved' in entry:
            url = entry['resolved']
            sum = entry['integrity']
            fn = os.path.basename(url)
            # looks like some module are from some kind of branch and may
            # use the same file name. So prefix with this namespace.
            if '/' in module:
                fn = module.split('/')[0] + '-' + fn
            if fn in module_map:
                if module_map[fn]['url'] != url \
                    or module_map[fn]['sum'] != sum:
                    logging.error("%s: mismatch %s <> %s, %s <> %s", module, module_map[fn]['url'], url, module_map[fn]['sum'], sum)
            else:
                module_map[fn] = { 'url' : url, 'sum': sum }

            module_map[fn].setdefault('path', set()).add(path)

        if 'dependencies' in entry:
            collect_deps_recursive(path, entry['dependencies'])

def main(args):

    # do some work here
    logger = logging.getLogger("boilerplate")
    logger.info("main")

    with open(args.input, 'r') as fh:
        js = json.load(fh)
        if 'dependencies' in js:
            collect_deps_recursive('', js['dependencies'])

    if args.output:
        with open(args.output, 'w') as fh:
            i = 100
            for fn in sorted(module_map.keys()):
                fh.write("Source{}:     {}#/{}\n".format(i, module_map[fn]['url'], fn))
                i += 1

    if args.checksums:
        with open(args.checksums, 'w') as fh:
            for fn in sorted(module_map.keys()):
                algo, chksum = module_map[fn]['sum'].split('-', 2)
                fh.write("{} ({}) = {}\n".format(algo.upper(), fn, hexlify(b64decode(chksum)).decode('ascii')))

    if args.locations:
        with open(args.locations, 'w') as fh:
            for fn in sorted(module_map.keys()):
                fh.write("{} {}\n".format(fn, ' '.join(module_map[fn]['path'])))

    return 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='boilerplate python commmand line program')
    parser.add_argument("--dry", action="store_true", help="dry run")
    parser.add_argument("--debug", action="store_true", help="debug output")
    parser.add_argument("--verbose", action="store_true", help="verbose")
    parser.add_argument("-i", "--input", metavar="FILE", default="package-lock.json", help="input package lock file")
    parser.add_argument("-o", "--output", metavar="FILE", help="spec files source lines into that file")
    parser.add_argument("--checksums", metavar="FILE", help="Write BSD style checksum file")
    parser.add_argument("--locations", metavar="FILE", help="Write locations into that file")

    args = parser.parse_args()

    if args.debug:
        level  = logging.DEBUG
    elif args.verbose:
        level = logging.INFO
    else:
        level = None

    logging.basicConfig(level = level)

    sys.exit(main(args))

# vim: sw=4 et
