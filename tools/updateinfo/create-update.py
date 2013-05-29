#!/usr/bin/python


# Copyright Intel 2013 (c)
# Authors:
# 	Anas Nashif <anas.nashif@intel.com>
#	Markus Lehtonen <markus.lehtonen@intel.com>

import os
import shutil
import sys
import tempfile
from optparse import OptionParser
from ConfigParser import SafeConfigParser

from updateutils import (parse_package_list, create_delta_repo, download,
                         parse_patch, create_updateinfo, create_update_file,
                         update_metadata)


def read_config(config_file):
    config_file = os.path.expanduser(config_file)
    parser = SafeConfigParser()
    parser.read(config_file)
    return parser

parser = OptionParser()
parser.add_option('-d', '--destdir', default='updates', metavar='DIR',
              help='Directory where to store the updates.')
parser.add_option('-p', '--patch',  metavar='TEXT',
              help='Patch information')
parser.add_option('-P', '--patchdir', metavar='DIR',
              help='directory for the (cumulative) patch files',
              default='patches')
parser.add_option("-o", "--old",  dest="old", metavar="OLD", help="Old snapshot")
parser.add_option("-n", "--new",  dest="new", metavar="NEW", help="New snapshot")
parser.add_option("-t", "--type",  dest="type", metavar="TYPE", help="Release type")
parser.add_option("--product",  help="Product name", default="tzpc")
parser.add_option("--username",  dest="username", metavar="USERNAME", help="Username for https")
parser.add_option("--password",  dest="password", metavar="PASSWD", help="Password for https")

(opts, args) = parser.parse_args()

config = read_config('~/.swup.conf')

if opts.type:
    config.set(opts.product, 'release-path', config.get(opts.product, opts.type))

credentials = [None, None]
if opts.username:
    credentials[0] = opts.username
elif config.has_option('DEFAULT', 'username'):
    credentials[0] = config.get('DEFAULT', 'username')
if opts.password:
    credentials[1] = opts.password
elif config.has_option('DEFAULT', 'password'):
    credentials[1] = config.get('DEFAULT', 'password')

# Initialize cache dir
CACHE_DIR = "cache"
if config.has_option('DEFAULT', 'cache-dir'):
    CACHE_DIR = config.get('DEFAULT', 'cache-dir')
CACHE_DIR = os.path.abspath(os.path.expanduser(CACHE_DIR))
packages_files_dir = os.path.join(CACHE_DIR, 'packages-files')
if not os.path.exists(packages_files_dir):
    os.makedirs(packages_files_dir)
cached_pkgs_dir = os.path.join(CACHE_DIR, 'rpms')
if not os.path.exists(cached_pkgs_dir):
    os.makedirs(cached_pkgs_dir)

if not opts.patch:
    print "missing opts --patch. You need to point to a patch file (YAML format)"
    sys.exit(1)

# create deltas (primary, deltainfo)
patch = parse_patch(opts.patch)
patch_id = patch['ID']
patch_dir = "%s/%s" % (opts.patchdir, patch_id)

# Prepare target dir
if not os.path.exists(patch_dir):
    os.makedirs(patch_dir)
else:
    print "Cleaning up %s" % patch_dir
    for filename in ['rpms', 'new', 'old']:
        filepath = os.path.join(patch_dir, filename)
        if os.path.exists(filepath):
            shutil.rmtree(os.path.join(filepath))

# Create a tempdir
tmp_dir = tempfile.mkdtemp(dir=".")

# Get packages files
download(config.get(opts.product, 'packages-file', False, {'build-id': opts.old}),
         credentials, tmp_dir, packages_files_dir, "packages")
download(config.get(opts.product, 'packages-file', False, {'build-id': opts.new}),
         credentials, patch_dir, packages_files_dir, "packages")

with open(os.path.join(tmp_dir, "repourl"), "w") as repourlfile:
    repourlfile.write("%s\n" % config.get(opts.product, 'repo-url', False, {'build-id': opts.old}))
with open(os.path.join(patch_dir, "repourl"), "w") as repourlfile:
    repourlfile.write("%s\n" % config.get(opts.product, 'repo-url', False, {'build-id': opts.new}))


repo_dir = create_delta_repo(tmp_dir, patch_dir, cached_pkgs_dir, tmp_dir, credentials)

# create updateinfo
create_updateinfo(tmp_dir, patch)

# update repo
os.system("modifyrepo %s/updateinfo.xml %s/repodata"  % (tmp_dir, repo_dir))

if not os.path.exists(opts.destdir):
    os.makedirs(opts.destdir)

zip_checksum = create_update_file(opts.patch, repo_dir, opts.destdir, patch_id)
extra_meta = {'checksum': zip_checksum,
              'build-id': opts.new}

update_metadata(opts.destdir, tmp_dir, patch, extra_meta)

# store patch metadata in patch dir, too
shutil.copy2(os.path.join(repo_dir, patch_id), os.path.join(patch_dir, 'patch.yaml'))

shutil.rmtree(tmp_dir)
