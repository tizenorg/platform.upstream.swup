#!/usr/bin/python

from sets import Set
import csv
import urllib2
from optparse import OptionParser
import os
import re, base64
import ConfigParser

USERNAME = ""
PASSWORD = ""
CACHE_DIR = "cache"

def read_config(config_file):
    config_file = os.path.expanduser(config_file)
    parser = ConfigParser.SafeConfigParser()
    parser.read(config_file)
    return parser

def http_get(url):
    print "Downloading %s" %url
    request = urllib2.Request(url)
    if USERNAME and PASSWORD:
        base64string = base64.encodestring('%s:%s' % (USERNAME, PASSWORD)).replace('\n', '')
        request.add_header("Authorization", "Basic %s" % base64string)
    html_page = urllib2.urlopen(request)
    return html_page

def download(url, out):
    if not os.path.exists(out):
        ret = http_get(url)
        cache = open(out, "w")
        cache.write(ret.read())
        cache.close()
    else:
        print "Already exists: %s" % out

def get_package_list(image_name, base_url, build_id, cachedir):
    cache_file = "%s/%s-%s.packages" %(cachedir, image_name, build_id )
    package_file = None
    if not os.path.exists(cache_file):
        image_packages = "%s/%s/images/%s/%s-%s.packages" %(base_url, build_id, image_name, image_name, build_id )
        #print image_packages
        package_file = http_get(image_packages)
        cache = open(cache_file, "w")
        cache.write(package_file.read())
        cache.close()
    package_file = open(cache_file, "rb")

    packages = {}

    pkgreader = csv.reader(package_file, delimiter=' ', quotechar='|')
    for row in pkgreader:
        pkg = row[0].split(".")
        if len(row)>2:
            packages[pkg[0]] = {'scm': row[2], 'version': row[1], 'arch': pkg[1]}
        else:
            packages[pkg[0]] = {'scm': None, 'version': row[1], 'arch': pkg[1]}

    package_file.close()
    return packages

parser = OptionParser()
parser.add_option("-o", "--old",  dest="old", metavar="OLD", help="Old snapshot")
parser.add_option("-n", "--new",  dest="new", metavar="NEW", help="New snapshot")
parser.add_option("-t", "--type",  dest="type", metavar="TYPE", help="Release type")
parser.add_option("-i", "--image",  dest="image", metavar="IMAGE", help="Image Name")
parser.add_option("-u", "--username",  dest="username", metavar="USERNAME", help="Username for https")
parser.add_option("-p", "--password",  dest="password", metavar="PASSWD", help="Password for https")
parser.add_option("--outdir",  dest="outdir", help="Output directory")

(options, args) = parser.parse_args()

config = read_config('~/.swuprc')

DAILY="/pc/releases/daily/trunk"
WEEKLY="/pc/releases/weekly/trunk"
SNAPSHOTS="/snapshots/trunk/pc/"
BASE="https://download.tz.otcshare.org/"

if options.type == "daily":
    release_url = "%s/%s" %(BASE, DAILY)
if options.type == "weekly":
    release_url = "%s/%s" %(BASE, WEEKLY)
else:
    release_url = "%s/%s" %(BASE, SNAPSHOTS)

if options.username:
    USERNAME = options.username
elif config.has_option('DEFAULT', 'username'):
    USERNAME = config.get('DEFAULT', 'username')
if options.password:
    PASSWORD = options.password
elif config.has_option('DEFAULT', 'password'):
    PASSWORD = config.get('DEFAULT', 'password')
# Initialize cache dir
if config.has_option('DEFAULT', 'cache-dir'):
    CACHE_DIR = config.get('DEFAULT', 'cache-dir')
CACHE_DIR = os.path.abspath(os.path.expanduser(CACHE_DIR))
packages_files_dir = os.path.join(CACHE_DIR, 'packages-files')
if not os.path.exists(packages_files_dir):
    os.makedirs(packages_files_dir)

p1 = get_package_list(options.image, release_url, options.old, packages_files_dir)
p2 = get_package_list(options.image, release_url, options.new, packages_files_dir)

pkgs1 = {'%s|%s' % (pkg, attr['arch']) for pkg, attr in p1.iteritems()}
pkgs2 = {'%s|%s' % (pkg, attr['arch']) for pkg, attr in p2.iteritems()}
newpkgs = [pkg.split('|')[0] for pkg in pkgs2.difference(pkgs1)]

pkgs1 = {'%s|%s' % (pkg, attr['version']) for pkg, attr in p1.iteritems()}
pkgs2 = {'%s|%s' % (pkg, attr['version']) for pkg, attr in p2.iteritems()}
changedpkgs = [pkg.split('|')[0] for pkg in pkgs2.difference(pkgs1) if pkg.split('|')[0] in p1]

old_pkgs_dir = os.path.join(CACHE_DIR, 'rpms')
if not os.path.exists(old_pkgs_dir):
    os.makedirs(old_pkgs_dir)

outdir = options.outdir if options.outdir else "update-%s-to-%s" % (options.old, options.new)
new_pkgs_dir = os.path.join(outdir, 'new')
if not os.path.exists(new_pkgs_dir):
    os.makedirs(new_pkgs_dir)
changed_pkgs_dir = os.path.join(outdir, 'rpms')
if not os.path.exists(changed_pkgs_dir):
    os.makedirs(changed_pkgs_dir)

for p in newpkgs:
    rpm = "%s-%s.%s.rpm" % (p, p2[p]['version'], p2[p]['arch'])
    arch = p2[p]['arch']
    download("%s/%s/repos/pc/x86_64/packages/%s/%s" % (release_url, options.new, arch, rpm), os.path.join(new_pkgs_dir, rpm))

for p in changedpkgs:
    rpm = "%s-%s.%s.rpm" % (p, p1[p]['version'], p1[p]['arch'])
    arch = p1[p]['arch']
    download("%s/%s/repos/pc/x86_64/packages/%s/%s" % (release_url, options.old, arch, rpm), os.path.join(old_pkgs_dir, rpm))
    rpm = "%s-%s.%s.rpm" % (p, p2[p]['version'], p2[p]['arch'])
    download("%s/%s/repos/pc/x86_64/packages/%s/%s" %(release_url, options.new, arch, rpm), os.path.join(changed_pkgs_dir, rpm))

