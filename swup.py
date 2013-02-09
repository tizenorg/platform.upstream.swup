#!/usr/bin/python

import ConfigParser
from optparse import OptionParser
import urllib2
from lxml import etree
from BeautifulSoup import *
import hashlib
import os
import tempfile
import shutil

update_repo="file:///home/nashif/system-updates/repo"
update_cache="/tmp/updates"



class FakeSecHead(object):
    def __init__(self, fp):
        self.fp = fp
        self.sechead = '[os-release]\n'
    def readline(self):
        if self.sechead:
            try: return self.sechead
            finally: self.sechead = None
        else: return self.fp.readline()

def get_current_version():
    config = ConfigParser.SafeConfigParser()
    config.readfp(FakeSecHead(open('/etc/os-release')))
    return dict(config.items('os-release'))

 
def checksum(fileName, checksum_type="sha256", excludeLine="", includeLine=""):
    """Compute sha256 hash of the specified file"""
    m = hashlib.sha256()
    if checksum_type == "md5":
        m = hashlib.md5()

    try:
        fd = open(fileName,"rb")
    except IOError:
        print "Unable to open the file in readmode:", filename
        return
    content = fd.readlines()
    fd.close()
    for eachLine in content:
        if excludeLine and eachLine.startswith(excludeLine):
            continue
        m.update(eachLine)
    m.update(includeLine)
    return m.hexdigest()


def probe_updates():
    print "Checking for new updates..."
    response = urllib2.urlopen("%s/data/updatemd.xml" % update_repo )
    updatemd = response.read()
    if not os.path.exists("%s/data" %update_cache):
        os.mkdir("%s/data" %update_cache)

    fp = open("%s/data/updatemd.xml" % update_cache , "w")
    fp.write(updatemd)
    fp.close()

    updatemd_local = open("%s/data/updatemd.xml" % update_cache )
    root = etree.XML(updatemd_local.read())
    data = root.xpath("//data[@type='update']")[0]
    loc = data.xpath("location")[0]
    href = loc.attrib['href']
    chksum = data.xpath("checksum")[0]
    chksum_type = chksum.attrib['type']
    
    if os.path.exists("%s/data/updates.xml" % update_cache):
        cur_sum = checksum("%s/data/updates.xml" % update_cache, checksum_type=chksum_type) 
        if cur_sum ==  chksum.text:
            print "Using file from cache, no new updates on server."
        else:
            print "Fetching new updates..."
            get_new_update_list(href)
    else:
        get_new_update_list(href)

    

def get_new_update_list(location):
    up = urllib2.urlopen("%s/%s" % (update_repo, location) )
    update_raw = up.read()
    fp = open("%s/data/updates.xml" % update_cache , "w")
    fp.write(update_raw)
    fp.close()


def list_updates():
    fp = open("%s/data/updates.xml" % update_cache , "r")
    updates_root = etree.XML(fp.read())
    updates = updates_root.xpath("//update")
    for update in updates:
        attr = update.attrib
        print "  %s:" %attr['id']
        print "       %s" %update.xpath("title")[0].text




parser = OptionParser()
parser.add_option("-V", "--os-version", action="store_true", dest="osver", default=False,
                  help="Current OS Version")
parser.add_option("-l", "--list-updates", action="store_true", dest="listupdates", default=False,
                  help="List updates")
parser.add_option("-d", "--download-only", action="store_true", dest="downloadonly", default=False,
                  help="Download only")
parser.add_option("-i", "--install",  dest="install", metavar="LABEL",
                  help="Install update")
parser.add_option("-r", "--recommended",  dest="recommended", action="store_true", default=False,
                  help="Install recommended updates only")
parser.add_option("-q", "--quiet",
                  action="store_false", dest="verbose", default=True,
                  help="don't print status messages to stdout")

(options, args) = parser.parse_args()

if options.osver:
    os_release = get_current_version()
    print os_release['version_id'].strip('"')

if options.listupdates:
    probe_updates()
    list_updates()
