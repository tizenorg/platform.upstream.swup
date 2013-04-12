#!/usr/bin/python

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
parser.add_option('-U', '--updatesfile',  metavar='UPDATES',
              help='master updates.xml file')
parser.add_option('-d', '--destdir', default='.', metavar='DIR',
              help='Directory where to store the updates.')
parser.add_option('-p', '--patch',  metavar='TEXT',
              help='Patch information')
parser.add_option('-P', '--patchdir', metavar='DIR',
              help='directory with patch files')
parser.add_option("-o", "--old",  dest="old", metavar="OLD", help="Old snapshot")
parser.add_option("-n", "--new",  dest="new", metavar="NEW", help="New snapshot")
parser.add_option("-t", "--type",  dest="type", metavar="TYPE", help="Release type")
parser.add_option("-i", "--image",  dest="image", metavar="IMAGE", help="Image Name")
parser.add_option("--username",  dest="username", metavar="USERNAME", help="Username for https")
parser.add_option("--password",  dest="password", metavar="PASSWD", help="Password for https")

(opts, args) = parser.parse_args()

config = read_config('~/.swuprc')

DAILY="pc/releases/daily/trunk"
WEEKLY="pc/releases/weekly/trunk"
SNAPSHOTS="snapshots/trunk/pc/"
BASE="https://download.tz.otcshare.org"

if opts.type == "daily":
    release_url = "%s/%s" %(BASE, DAILY)
if opts.type == "weekly":
    release_url = "%s/%s" %(BASE, WEEKLY)
else:
    release_url = "%s/%s" %(BASE, SNAPSHOTS)

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


root = os.getcwd()
if not opts.patch:
    print "missing opts --patch. You need to point to a patch file (YAML format)"
    sys.exit(1)

if opts.patchdir:
    root = opts.patchdir

patch_path = opts.patch
destination = ""
if not opts.destdir:
    destination = root
else:
    destination = opts.destdir

# create deltas (primary, deltainfo)
patch = parse_patch(patch_path)
patch_id = patch['ID']
target_dir = "%s/%s" % (root, patch_id)

# Prepare target dir
if not os.path.exists(target_dir):
    os.makedirs(target_dir)
else:
    print "Cleaning up %s" % target_dir
    for filename in ['rpms', 'new', 'old']:
        filepath = os.path.join(target_dir, filename)
        if os.path.exists(filepath):
            shutil.rmtree(os.path.join(filepath))

# Create a tempdir
tmp_dir = tempfile.mkdtemp(dir=".")

# Get packages files
old_baseurl = "%s/%s" % (release_url, opts.old)
new_baseurl = "%s/%s" % (release_url, opts.new)
download("%s/images/%s" % (old_baseurl, opts.image),
         "%s-%s.packages" % (opts.image, opts.old), credentials, tmp_dir, packages_files_dir, "packages")
download("%s/images/%s" % (new_baseurl, opts.image),
         "%s-%s.packages" % (opts.image, opts.new), credentials, target_dir, packages_files_dir, "packages")

with open(os.path.join(tmp_dir, "repourl"), "w") as repourlfile:
    repourlfile.write("%s/repos/pc/x86_64/packages/\n" % old_baseurl)
with open(os.path.join(target_dir, "repourl"), "w") as repourlfile:
    repourlfile.write("%s/repos/pc/x86_64/packages/\n" % new_baseurl)


repo_dir = create_delta_repo(tmp_dir, target_dir, cached_pkgs_dir, tmp_dir, credentials)

# create updateinfo
create_updateinfo(tmp_dir, patch)

# update repo
os.system("modifyrepo %s/updateinfo.xml %s/repodata"  % (tmp_dir, repo_dir))

zip_checksum = create_update_file(patch_path, repo_dir, destination,  patch_id)

update_metadata(destination, tmp_dir, opts.updatesfile, patch, zip_checksum)

# store patch metadata in patch dir, too
shutil.copy2(os.path.join(repo_dir, patch_id), os.path.join(target_dir, 'patch.yaml'))

shutil.rmtree(tmp_dir)
