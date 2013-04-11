#!/usr/bin/python

import os
import shutil
import sys
from optparse import OptionParser
from ConfigParser import SafeConfigParser

from updateutils import get_package_list, download, parse_patch, create_updateinfo, create_update_file, update_metadata


def read_config(config_file):
    config_file = os.path.expanduser(config_file)
    parser = SafeConfigParser()
    parser.read(config_file)
    return parser

parser = OptionParser()
parser.add_option('-U', '--updatesfile',  metavar='UPDATES',
              help='master updates.xml file')
parser.add_option('-O', '--original',  metavar='ORIGINAL',
              help='Original and Old package directory')

parser.add_option('-q', '--quiet', action='store_true',
              help='do not show downloading progress')
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

# Get packages
p1 = get_package_list(opts.image, release_url, opts.old, credentials, target_dir, packages_files_dir)
p2 = get_package_list(opts.image, release_url, opts.new, credentials, target_dir, packages_files_dir)

pkgs1 = {'%s|%s' % (pkg, attr['arch']) for pkg, attr in p1.iteritems()}
pkgs2 = {'%s|%s' % (pkg, attr['arch']) for pkg, attr in p2.iteritems()}
newpkgs = [pkg.split('|')[0] for pkg in pkgs2.difference(pkgs1)]

pkgs1 = {'%s|%s' % (pkg, attr['version']) for pkg, attr in p1.iteritems()}
pkgs2 = {'%s|%s' % (pkg, attr['version']) for pkg, attr in p2.iteritems()}
changedpkgs = [pkg.split('|')[0] for pkg in pkgs2.difference(pkgs1) if pkg.split('|')[0] in p1]

cached_pkgs_dir = os.path.join(CACHE_DIR, 'rpms')
if not os.path.exists(cached_pkgs_dir):
    os.makedirs(cached_pkgs_dir)

old_pkgs_dir = os.path.join(target_dir, 'old')
if not os.path.exists(old_pkgs_dir):
    os.makedirs(old_pkgs_dir)
new_pkgs_dir = os.path.join(target_dir, 'new')
if not os.path.exists(new_pkgs_dir):
    os.makedirs(new_pkgs_dir)
changed_pkgs_dir = os.path.join(target_dir, 'rpms')
if not os.path.exists(changed_pkgs_dir):
    os.makedirs(changed_pkgs_dir)

old_repourl = "%s/%s/repos/pc/x86_64/packages/" % (release_url, opts.old)
new_repourl = "%s/%s/repos/pc/x86_64/packages/" % (release_url, opts.new)

with open(os.path.join(target_dir, "repourl"), "w") as repourlfile:
    repourlfile.write("%s\n" % new_repourl)

for p in newpkgs:
    rpm = "%s-%s.%s.rpm" % (p, p2[p]['version'], p2[p]['arch'])
    arch = p2[p]['arch']
    download("%s/%s" % (new_repourl, arch), rpm, credentials, new_pkgs_dir, cached_pkgs_dir)

for p in changedpkgs:
    rpm = "%s-%s.%s.rpm" % (p, p1[p]['version'], p1[p]['arch'])
    arch = p1[p]['arch']
    download("%s/%s" % (old_repourl, arch), rpm, credentials, old_pkgs_dir, cached_pkgs_dir)
    rpm = "%s-%s.%s.rpm" % (p, p2[p]['version'], p2[p]['arch'])
    download("%s/%s" % (new_repourl, arch), rpm, credentials, changed_pkgs_dir, cached_pkgs_dir)

os.system("createrepo --deltas --oldpackagedirs=%s %s/%s" % (cached_pkgs_dir, root, patch_id))

# create updateinfo
create_updateinfo(root, patch)

# update repo
os.system("modifyrepo %s/updateinfo.xml %s/%s/repodata"  % (root, root, patch_id))

zip_checksum = create_update_file(patch_path, target_dir, destination,  patch_id)

update_metadata(destination, root, opts.updatesfile, patch, zip_checksum)
