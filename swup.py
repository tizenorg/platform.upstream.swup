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
import copy
import sys
import zipfile
import rpm
import subprocess as sub
import distutils
import fileinput

update_repo="http://www.planux.com/updates"
update_cache="/var/cache/updatemanager"
# zypper return values that are acceptable when running the patch command
patch_okay_codes = [0, 102, 103]

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
    if not os.path.exists("%s/download/metadata" %update_cache):
        os.mkdir("%s/download/metadata" %update_cache)

    fp = open("%s/download/metadata/updatemd.xml" % update_cache , "w")
    fp.write(updatemd)
    fp.close()

    updatemd_local = open("%s/download/metadata/updatemd.xml" % update_cache )
    root = etree.XML(updatemd_local.read())
    data = root.xpath("//data[@type='updates']")[0]
    loc = data.xpath("location")[0]
    href = loc.attrib['href']
    chksum = data.xpath("checksum")[0]
    chksum_type = chksum.attrib['type']

    if os.path.exists("%s/download/metadata/updates.xml" % update_cache):
        cur_sum = checksum("%s/download/metadata/updates.xml" % update_cache, checksum_type=chksum_type)
        if cur_sum ==  chksum.text:
            print "Using file from cache, no new updates on server."
        else:
            print "Fetching new updates..."
            get_new_update_list(href)
    else:
        get_new_update_list(href)


def parse_updates():

    updates = {}
    fp = open("%s/download/metadata/updates.xml" % update_cache , "r")
    updates_root = etree.XML(fp.read())
    updates_el = updates_root.xpath("//update")
    for update in updates_el:
        up = {}
        attr = update.attrib
        up['id'] = attr['id']
        up['checksum'] = update.xpath("checksum")[0].text
        up['version'] = update.xpath("version")[0].text
        up['build-id'] = update.xpath("build-id")[0].text
        up['title'] = update.xpath("title")[0].text
        loc = update.xpath("location")[0]
        up['location'] = "%s" % ( loc.attrib['href'])

        updates[up['id']] = up
    return updates


def download_update(update_data):
    u = update_data
    location = u['location']
    if not os.path.exists("%s/download" % (update_cache)):
        os.mkdir("%s/download" % (update_cache))
    if not os.path.exists("%s/download/%s/download_done" % (update_cache, u['id'] )):
        print "Downloading %s/%s" % (update_repo, location)
        update_file = urllib2.urlopen("%s/%s" % (update_repo, location) )
        location = os.path.basename(location)
        announced_csum = u['checksum']
        update_raw = update_file.read()
        fp = open("%s/download/%s" % (update_cache,location) , "w")
        fp.write(update_raw)
        fp.close()
        downloaded_csum = checksum("%s/download/%s" % (update_cache,location), "sha256")
        # Verify Checksum
        if downloaded_csum != announced_csum:
            print "Error: Checksum mismatch"
            os.remove("%s/download/%s" % (update_cache,location))
            raise Exception("Checksum failed")
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
    import gzip
    update_raw = up.read()
    fp = open("%s/download/metadata/updates.xml.gz" % update_cache , "w")
    fp.write(update_raw)
    fp.close()
    f = gzip.open("%s/download/metadata/updates.xml.gz" % update_cache, 'rb')
    file_content = f.read()
    f.close()
    fp = open("%s/download/metadata/updates.xml" % update_cache , "w")
    fp.write(file_content)
    fp.close()


def create_zip():
    #distutils.archive_util.make_zipfile(base_name, base_dir[, verbose=0, dry_run=0])
    pass

def pack(target):
    from zipfile_infolist import print_info
    import zipfile
    try:
        import zlib
        compression = zipfile.ZIP_DEFLATED
    except:
        compression = zipfile.ZIP_STORED

    modes = { zipfile.ZIP_DEFLATED: 'deflated',
              zipfile.ZIP_STORED:   'stored',
              }

    print 'creating update archive'
    zf = zipfile.ZipFile('%s.zip' %target, mode='w')
    try:
        print 'adding README.txt with compression mode', modes[compression]
        zf.write('README.txt', compress_type=compression)
    finally:
        print 'closing'
        zf.close()

    print
    print_info('%s.zip' %target)

def unpack(location, update_id):
    #os.mkdir("%s/download/%s" %(update_cache, update_id))
    zfile = zipfile.ZipFile("%s/download/%s/%s" % (update_cache,update_id, location))
    for name in zfile.namelist():
        (dirname, filename) = os.path.split(name)
        print "Decompressing " + filename + " on " + dirname
        if not os.path.exists("%s/download/%s/%s" % (update_cache, update_id, dirname)):
            os.mkdir("%s/download/%s/%s" % (update_cache, update_id, dirname))
        if filename != "":
            fd = open("%s/download/%s/%s" % (update_cache, update_id, name),"w")
            fd.write(zfile.read(name))
            fd.close()

    os.rename("%s/download/%s/%s" % (update_cache,update_id, update_id), "%s/download/%s/content" % (update_cache,update_id))


def prepare_update(update_data, download):
    u = update_data
    location = u['location']
    update_id = u['id']
    # unzip
    if os.path.exists("%s/download/%s" % (update_cache,update_id)) and not os.path.exists("%s/download/%s/content" % (update_cache,update_id)):
        print "Unpacking %s" %location
        unpack(location, update_id)
    else:
        print "Update %s already unpacked" % update_id

    repodir = "%s/repos.d" %update_cache
    repourl = "file://%s/download/%s/content" % (update_cache, update_id)
    if not os.path.exists("%s/%s.repo" % (repourl, update_id)):
        r = os.system("zypper --quiet --reposd-dir %s ar --no-gpgcheck --no-keep-packages %s %s" %(repodir, repourl, update_id))
        if r != 0:
            raise Exception("zypper add repo error: %s" % r)
    if not download:
        r = os.system("zypper --quiet --non-interactive --reposd-dir %s patch --repo %s -d" % (repodir, update_id) )
        if r not in patch_okay_codes:
            raise Exception("zypper patch error: %s" % r)

def install_update(update_data):
    u = update_data
    location = u['location']
    update_id = u['id']
    # unzip
    if not os.path.exists("%s/download/%s/content" % (update_cache,update_id)):
        prepare_update(update_data, False)

    repodir = "%s/repos.d" %update_cache
    repourl = "file://%s/download/%s/content" % (update_cache, update_id)
    if not os.path.exists("%s/%s.repo" % (repodir, update_id)):
        r = os.system("zypper --quiet --reposd-dir %s ar --no-gpgcheck --no-keep-packages %s %s" %(repodir, repourl, update_id))
        if r != 0:
            raise Exception("zypper add repo error: %s" % r)
    print "zypper -n  --reposd-dir %s patch --with-interactive  --repo %s " % (repodir, update_id)
    os.system("plymouth message --text='%s'" % u['title'])
    r = os.system("zypper -n  --reposd-dir %s patch --with-interactive --repo %s " % (repodir, update_id) )
    if r not in patch_okay_codes:
        raise Exception("zypper patch error: %s" % r)
    if not os.path.exists("%s/installed" % (update_cache)):
        os.mkdir("%s/installed" % (update_cache))
    shutil.copyfile("%s/download/%s/content/%s" %(update_cache, update_id, update_id), "%s/installed/%s" % (update_cache, update_id))

    os_release = get_current_version()
    current_version = os_release['version_id'].strip('"')
    current_build = os_release['build_id'].strip('"')
    print "Finished installing %s. (from %s to %s)" % (update_id, current_version, u['version'])
    for line in fileinput.input("/etc/os-release", inplace=1):
        print line.replace(current_version, u['version']).replace(current_build, u['build-id']),
    for line in fileinput.input("/etc/tizen-release", inplace=1):
        print line.replace(current_version, u['version']),

def apply_update(update_data):
    pass

def list_updates():
    updates = parse_updates()
    for k in updates.keys():
        u = updates[k]
        installed = "%s/installed/%s" % (update_cache, u['id'])
        if not os.path.exists(installed):
            print "%s" %u['id']
            print "    %s" %u['title']

def get_uninstalled_updates(updates):
    uninstalled = copy.deepcopy(updates)
    if os.path.isdir("%s/installed/" % update_cache):
        update_ids = sorted(uninstalled.keys(), reverse=True)
        installed = sorted(os.listdir("%s/installed/" % update_cache), reverse=True)
        if len(installed) != 0:
            latest = installed[0]
            if update_ids.count(latest) != 0:
                for i in update_ids[update_ids.index(latest):]:
                    uninstalled.pop(i)

    return uninstalled

def get_options():
    parser = OptionParser()
    parser.add_option("-V", "--os-version", action="store_true", dest="osver", default=False,
                      help="Current OS Version")

    parser.add_option("-l", "--list-updates", action="store_true", dest="listupdates", default=False,
                      help="List updates")

    parser.add_option("-d", "--download-only", action="store_true", dest="downloadonly", default=False,
                      help="Download only")

    parser.add_option("-i", "--install",  dest="install", metavar="LABEL",
                      help="Install update")

    parser.add_option("-p", "--prepare",  dest="prepare", metavar="LABEL",
                      help="Prepare update")

    parser.add_option("-a", "--install-all",  dest="install_all", action="store_true", default=False,
                      help="Install all updates")

    parser.add_option("-P", "--prepare-all",  dest="prepare_all", action="store_true", default=False,
                      help="prepare update")

    parser.add_option("-r", "--recommended",  dest="recommended", action="store_true", default=False,
                      help="Install recommended updates only")

    parser.add_option("-q", "--quiet",
                      action="store_false", dest="verbose", default=True,
                      help="don't print status messages to stdout")

    (options, args) = parser.parse_args()

    return options

def run_action(options):
    if not os.path.exists(update_cache):
        os.mkdir("%s" % update_cache)
    if not os.path.exists("%s/download" % update_cache):
        os.mkdir("%s/download" % update_cache)
        os.mkdir("%s/download/metadata" % update_cache)

    if not os.path.exists("%s/repos.d" % update_cache):
        os.mkdir("%s/repos.d" % update_cache)

    if options.osver:
        os_release = get_current_version()
        print os_release['version_id'].strip('"')

    if options.listupdates:
        probe_updates()
        list_updates()

    if options.downloadonly:
        probe_updates()
        download_all_updates()

    if options.prepare is not None and not options.prepare_all:
        probe_updates()
        updates = parse_updates()
        if not updates.has_key(options.prepare):
            print "%s is not available for installation. Abort." %options.prepare
            sys.exit(0)
        u = updates[options.prepare]
        download_update(u)
        prepare_update(u, False)

    if options.install is not None and not options.install_all:
        updates = parse_updates()
        if not updates.has_key(options.install):
            print "%s is not available for installation. Abort." %options.install
            sys.exit(0)
        u = updates[options.install]
        download_update(u)
        install_update(u)

    if options.install_all:
        updates = parse_updates()
        uninstalled_updates = get_uninstalled_updates(updates)
        for u in uninstalled_updates.values():
            download_update(u)
            install_update(u)

if __name__ == '__main__':
    try:
        options = get_options()
        run_action(options)
    except:
        sys.exit(-1)
