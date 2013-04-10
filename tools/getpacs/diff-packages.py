#!/usr/bin/python

from sets import Set
import csv
import urllib2
from optparse import OptionParser
import os
import re, base64

username = ""
password = ""

def http_get(url):
    print "Downloading %s" %url
    request = urllib2.Request(url)
    if username and password:
        base64string = base64.encodestring('%s:%s' % (username, password)).replace('\n', '')
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

def get_package_list(image_name, base_url, build_id):
    cache_dir = "cache"
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    cache_file = "%s/%s-%s.packages" %(cache_dir, image_name, build_id )
    package_file = None
    if not os.path.exists(cache_file):
        image_packages = "%s/%s/images/%s/%s-%s.packages" %(base_url, build_id, image_name, image_name, build_id )
        package_file = http_get(image_packages)
        cache = open(cache_file, "w")
        cache.write(package_file.read())
        cache.close()
    package_file = open(cache_file, "rb")

    packages = []

    pkgreader = csv.reader(package_file, delimiter=' ', quotechar='|')
    for row in pkgreader:
        pkg = row[0].split(".")
        name = "%s-%s.%s" %(pkg[0], row[1], pkg[1])
        packages.append(name)

    package_file.close()
    return packages

def get_package_list2(image_name, base_url, build_id):
    cache_dir = "cache"
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    cache_file = "%s/%s-%s.packages" %(cache_dir, image_name, build_id )
    package_file = None
    if not os.path.exists(cache_file):
        image_packages = "%s/%s/images/%s/%s-%s.packages" %(base_url, build_id, image_name, image_name, build_id )
        #print image_packages
        package_file = http_get(image_packages)
        cache = open(cache_file, "w")
        cache.write(package_file.read())
        cache.close()
    else:
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

(options, args) = parser.parse_args()

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

username = options.username
password = options.password

p1 = get_package_list(options.image, release_url, options.old)
p2 = get_package_list(options.image, release_url, options.new)

if not os.path.exists('new'):
    os.makedirs('new')
for p in Set(p2).difference(Set(p1)):
    if "noarch" in p:
        download("%s/%s/repos/pc/x86_64/packages/noarch/%s.rpm" %(release_url, options.new, p), "new/%s.rpm" %p)
    else:
        download("%s/%s/repos/pc/x86_64/packages/x86_64/%s.rpm" %(release_url, options.new, p), "new/%s.rpm" %p)

if not os.path.exists('old'):
    os.makedirs('old')
for p in Set(p1).difference(Set(p2)):
    if "noarch" in p:
        download("%s/%s/repos/pc/x86_64/packages/noarch/%s.rpm" %(release_url, options.old, p), "old/%s.rpm" %p)
    else:
        download("%s/%s/repos/pc/x86_64/packages/x86_64/%s.rpm" %(release_url, options.old, p), "old/%s.rpm" %p)


