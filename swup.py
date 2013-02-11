#!/usr/bin/python

import ConfigParser
from optparse import OptionParser
import urllib2
from lxml import etree
#from BeautifulSoup import *
import hashlib
import os
import tempfile
import shutil
import sys
import zipfile
import rpm

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


def parse_updates():

    updates = {}

    fp = open("%s/data/updates.xml" % update_cache , "r")
    updates_root = etree.XML(fp.read())
    updates_el = updates_root.xpath("//update")
    for update in updates_el:
        up = {}
        attr = update.attrib
        up['id'] = attr['id']
        up['checksum'] = update.xpath("checksum")[0].text
        up['title'] = update.xpath("title")[0].text 
        loc = update.xpath("location")[0]
        up['location'] = "%s" % ( loc.attrib['href'])
        
        updates[up['id']] = up
    return updates


def download_update(update_data):
    u = update_data
    location = u['location']
    if not os.path.exists("%s/downloads/%s" % (update_cache,location)):
        update_file = urllib2.urlopen("%s/%s" % (update_repo, location) )
        location = os.path.basename(location)
        announced_csum = u['checksum']
        update_raw = update_file.read()
        fp = open("%s/downloads/%s" % (update_cache,location) , "w")
        fp.write(update_raw)
        fp.close()
        downloaded_csum = checksum("%s/downloads/%s" % (update_cache,location), "sha256")
        # Verify Checksum
        if downloaded_csum != announced_csum:
            print "Error: Checksum mismatch"
            os.remove("%s/downloads/%s" % (update_cache,location))
    else:
        print "%s already downloaded" % location    

def download_all_updates(update_label=None):
    updates = parse_updates()

    if update_label is not None:
        u = updates[update_label]
        download_update(u)
    else:
        for k in updates.keys():
            u = updates[k]
            download_update(u)
        

def get_new_update_list(location):
    up = urllib2.urlopen("%s/%s" % (update_repo, location) )
    update_raw = up.read()
    fp = open("%s/data/updates.xml" % update_cache , "w")
    fp.write(update_raw)
    fp.close()


def prepare_update(update_data):
    u = update_data
    location = u['location']
    # unzip
    if os.path.exists("%s/downloads/%s" % (update_cache,location)) and not os.path.exists("%s/downloads/%s" % (update_cache,u['id'])):    
        zfile = zipfile.ZipFile("%s/downloads/%s" % (update_cache,location))
        for name in zfile.namelist():            
            (dirname, filename) = os.path.split(name)
            print "Decompressing " + filename + " on " + dirname
            if not os.path.exists("%s/downloads/%s" % (update_cache, dirname)):
                os.mkdir("%s/downloads/%s" % (update_cache, dirname))            
            if filename != "":
                fd = open("%s/downloads/%s" % (update_cache, name),"w")
                fd.write(zfile.read(name))
                fd.close()
    # apply deltas
    print "Delta Packages:"
    for delta in os.listdir("%s/downloads/%s/delta" % (update_cache,u['id'])):
        

        ts = rpm.TransactionSet()
        fdno = os.open("%s/downloads/%s/delta/%s" % (update_cache, u['id'], delta), os.O_RDONLY)
        hdr = ts.hdrFromFdno(fdno)
        os.close(fdno)
        target_rpm =  "%s-%s-%s.%s.rpm" % (hdr['name'], hdr['version'], hdr['release'], hdr['arch'])
        version = "_%s.%s.drpm" % (hdr['release'], hdr['arch'])
        
        original_rpm = "%s.%s.rpm" %( delta.replace(version, ""), hdr['arch'] )
        print "   %s" %original_rpm
        print " + %s" %delta
        print " = %s" %target_rpm

        # Verify
        
        mi = ts.dbMatch("name", hdr['name'])
        Found = False
        for r in mi:
            installed = "%s-%s-%s.%s.rpm" % (r.name, r.version, r.release, r.arch)
            original = "%s-%s-%s.%s" % (hdr['name'], hdr['version'], hdr['release'], hdr['arch'])                
            if installed == original:
                found = True
        if Found:
            print "Original availale, delta can be applied. Applying now..."
            # apply delta here
        else:
            print "Error: original not available, can't apply delta. We have %s instead of %s" % (installed, original_rpm)



def apply_update(update_data):
    pass

def list_updates():
    updates = parse_updates()
    for k in updates.keys():
        u = updates[k]
        print "%s" %u['id']
        print "    %s" %u['title']


parser = OptionParser()
parser.add_option("-V", "--os-version", action="store_true", dest="osver", default=False,
                  help="Current OS Version")
parser.add_option("-l", "--list-updates", action="store_true", dest="listupdates", default=False,
                  help="List updates")
parser.add_option("-d", "--download-only", action="store_true", dest="downloadonly", default=False,
                  help="Download only")
parser.add_option("-i", "--install",  dest="install", metavar="LABEL",
                  help="Install update")
parser.add_option("-a", "--install-all",  dest="installall", action="store_true", default=False,
                  help="Install all updates")
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

if options.downloadonly:
    probe_updates()
    download_all_updates()

if options.install is not None:
    probe_updates()
    updates = parse_updates()
    if not updates.has_key(options.install):
        print "%s is not available for installation. Abort." %options.install
        sys.exit()
    u = updates[options.install]
    download_update(u)
    prepare_update(u)



