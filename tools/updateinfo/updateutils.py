import csv
import urllib2
import os
import re, base64
import shutil
import yaml
from xml.dom import minidom
import rpm
import glob
import sys, os
import zipfile
import hashlib
import fileinput


def http_get(url, credentials=(None, None)):
    print "Downloading %s" %url
    request = urllib2.Request(url)
    if credentials[0] and credentials[1]:
        base64string = base64.encodestring('%s:%s' % (credentials[0], credentials[1])).replace('\n', '')
        request.add_header("Authorization", "Basic %s" % base64string)
    html_page = urllib2.urlopen(request)
    return html_page

def download(url, fname, credentials, outdir, cachedir):
    cached_file = os.path.join(cachedir, fname)
    if os.path.exists(cached_file):
        print "File cache hit: %s" % fname
    else:
        ret = http_get(os.path.join(url, fname), credentials)
        cache = open(cached_file, "w")
        cache.write(ret.read())
        cache.close()
    if outdir:
        dest_file = os.path.join(outdir, fname)
        if not os.path.exists(dest_file):
            shutil.copy2(cached_file, dest_file)

def get_package_list(base_url, build_id, image_name, credentials, out_dir, cache_dir):
    cache_file = "%s/%s-%s.packages" % (cache_dir, image_name, build_id)
    if not os.path.exists(cache_file):
        image_packages = "%s/%s/images/%s/%s-%s.packages" %(base_url, build_id, image_name, image_name, build_id )
        package_file = http_get(image_packages, credentials)
        with open(cache_file, "w") as cache:
            cache.write(package_file.read())
    with open(cache_file, "rb") as package_file:
        packages = {}
        pkgreader = csv.reader(package_file, delimiter=' ', quotechar='|')
        for row in pkgreader:
            pkg = row[0].split(".")
            if len(row)>2:
                packages[pkg[0]] = {'scm': row[2], 'version': row[1], 'arch': pkg[1]}
            else:
                packages[pkg[0]] = {'scm': None, 'version': row[1], 'arch': pkg[1]}
    shutil.copy2(cache_file, os.path.join(out_dir, "packages"))

    return packages



def get_checksum(fileName, checksum_type="sha256", excludeLine="", includeLine=""):
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

class Updates:
    def __init__(self, patch = None, updates = None, cache = None):
        self.doc = None
        self.pids = []
        self._check_update(cache)

        if patch and updates:
            self.add_update(patch, updates)

    def _desc_to_html(self, page, desc):
        in_ul = False
        for line in desc.splitlines():
            if line.startswith('- ') or line.startswith('* '):
                if not in_ul:
                    page.ul()
                    in_ul = True
                page.li(line[2:])
            else:
                if in_ul:
                    page.ul.close()
                    in_ul = False
                page.p(line)
        if in_ul:
            page.ul.close()

    def get_title(self, t, is_html = False):
        if is_html:
            import markup
            page = markup.page()
            page.init( title = t, style = CSS_STRIKE)
            page.h1(t)
            return str(page).rstrip('</html>').rstrip().rstrip('</body>')
        else:
            return t

    def get_summary_info(self, sum, is_html = False):
        if is_html:
            import markup
            page = markup.page()
            page.h2(sum['Title'])
            self._desc_to_html(page, sum['Description'])

            return str(page)

        else:
            return '%s\n%s' %(sum['Title'], sum['Description'])

    def get_patch_info(self, update, is_html = False):
        if is_html:
            import markup
            page = markup.page()
            #page.h3(update['Title'])
            self._desc_to_html(page, update['Description'])

            if update.has_key("Bugs"):
                page.p.open()
                page.add('Resolved Bugs: ')
                firstone = True
                for bug in update['Bugs']:
                    if firstone:
                        firstone = False
                    else:
                        page.add(', ')
                    page.a(bug, href='http://bugs.tizen.org/show_bug.cgi?id=%s' %bug, class_="strike_link")
                page.p.close()

            if update.has_key("CVEs"):
                page.p.open()
                page.add('Resolved CVE Issues: ')
                firstone = True
                for cve in update['CVEs']:
                    if firstone:
                        firstone = False
                    else:
                        page.add(', ')
                    page.a(cve, href='http://cve.mitre.org/cgi-bin/cvename.cgi?name=%s\n' % cve, class_="strike_link")
                page.p.close()

            return str(page)
        else:
            INFO = """

    Patch <%s>:
        Title: %s
        Type: %s
        Project: %s
        Repository: %s
        Release: %s
        Packages: %s
        Description:
            %s
    """ % (update['ID'],
           update['Title'],
           update['Type'],
           update['Project'],
           update['Repository'],
           update['Release'],
           ", ".join(update['Packages']),
           '\n        '.join(update['Description'].splitlines()))

            if update.has_key("CVEs"):
                INFO += "    CVEs:\n"
                cve_info = ''
                for cve in update['CVEs']:
                    cve_info += '       http://cve.mitre.org/cgi-bin/cvename.cgi?name=%s\n' %cve
                INFO += cve_info

            if update.has_key("Bugs"):
                INFO += "    Bugs:\n"
                bug_info = ''
                for bug in update['Bugs']:
                    bug_info += '       http://bugs.tizen.org/show_bug.cgi?id=%s\n' %bug
                INFO += bug_info

            if update.has_key('Reboot') and  update['Reboot']:
                INFO += '    NOTE: reboot needed\n'
            if update.has_key('Relogin') and  update['Relogin']:
                INFO += '    NOTE: relogin needed\n'
            if update.has_key('Restart') and update['Restart']:
                INFO += '    NOTE: restart needed\n'

        return INFO

    def _new_doc(self):
        print "Creating new updates.xml file..."
        doc = minidom.Document()
        doc.appendChild(doc.createElement('updates'))
        self.doc = doc

    def _sanity_check(self):
        if not self.doc:
            print 'Empty or invalid updates.xml file.'
            self._new_doc()
            return

        # check for duplicate patch entries

    def _check_update(self, cache):
        if cache:
            try:
                self.doc = cache.doc
            except AttributeError:
                if os.path.exists(cache):
                    self.doc = minidom.parse(cache)
            self._sanity_check()
            self.next =  len(self.doc.getElementsByTagName('update'))
        else:
            self._new_doc()
            self.next = 0
    def _insert(self, parent, name, attrs={}, text=None, data=None):
        """ Helper function to trivialize inserting an element into the doc """
        child = self.doc.createElement(name)
        for item in attrs.items():
            child.setAttribute(item[0], unicode(item[1]))
        if text:
            txtnode = self.doc.createTextNode(unicode(text))
            child.appendChild(txtnode)
        if data:
            txtnode = self.doc.createCDATASection(unicode(data))
            child.appendChild(txtnode)
        parent.appendChild(child)
        return child

    def _get_notice(self, update_id):
        return update_id in self.pids

    def add_update(self, update,  location, checksum):
        """
        Generate the extended metadata for a given update
        """
        import time

        self.next = self.next + 1
        root = self._insert(self.doc.firstChild, 'update', attrs={
                'id'      : update['ID']
        })

        self._insert(root, 'title', text=update['Title'])
        self._insert(root, 'type', text=update['Type'])
        self._insert(root, 'location', attrs={'href': location})
        self._insert(root, 'checksum', text=checksum)
        self._insert(root, 'version', text=update['Release'])
        times = str(time.time()).split(".")
        issued_time = times[0]
        self._insert(root, 'issued', attrs={ 'date' : issued_time })

        if update.has_key('Reboot') and  update['Reboot']:
            self._insert(root, 'reboot_required', text='True')
        if update.has_key('Relogin') and  update['Relogin']:
            self._insert(root, 'relogin_required', text='True')
        if update.has_key('Restart') and update['Restart']:
            self._insert(root, 'restart_required', text='True')

        html = self.get_patch_info(update, True)
        self._insert(root, 'description', data=html)

class UpdateInfo:
    def __init__(self, patch = None, updates = None, cache = None):
        self.doc = None
        self.pids = []
        self._check_update(cache)

        if patch and updates:
            self.add_patch(patch, updates)

    def _new_doc(self):
        print "Creating new updateinfo.xml file..."
        doc = minidom.Document()
        doc.appendChild(doc.createElement('updates'))

        self.doc = doc

    def _sanity_check(self):
        if not self.doc:
            print 'Empty or invalid updateinfo.xml file.'
            self._new_doc()
            return

        # check for duplicate patch entries
        for u in self.doc.getElementsByTagName('update'):
            pid =u.getElementsByTagName('id')[0].firstChild.data
            if pid in self.pids:
                print 'Found duplicate update entry: %s' % pid
            else:
                self.pids.append(pid)

    def _check_update(self, cache):
        if cache:
            try:
                self.doc = cache.doc
            except AttributeError:
                if os.path.exists(cache):
                    self.doc = minidom.parse(cache)
            self._sanity_check()
            self.next =  len(self.doc.getElementsByTagName('update'))
        else:
            self._new_doc()
            self.next = 0

    def _insert(self, parent, name, attrs={}, text=None, data=None):
        """ Helper function to trivialize inserting an element into the doc """
        child = self.doc.createElement(name)
        for item in attrs.items():
            child.setAttribute(item[0], unicode(item[1]))
        if text:
            txtnode = self.doc.createTextNode(unicode(text))
            child.appendChild(txtnode)
        if data:
            txtnode = self.doc.createCDATASection(unicode(data))
            child.appendChild(txtnode)
        parent.appendChild(child)
        return child

    def _get_notice(self, update_id):
        return update_id in self.pids

    def add_patch(self, update, updates):
        """
        Generate the extended metadata for a given update
        """

        import time

        self.next = self.next + 1
        root = self._insert(self.doc.firstChild, 'update', attrs={
                'type'      : update['Type'],
                'version'   : "%04d" %self.next,
                'from'      : 'updates@tizen.org'
        })

        self._insert(root, 'id', text=update['ID'])
        self._insert(root, 'title', text=update['Title'])
        self._insert(root, 'release', text=update['Release'])
        times = str(time.time()).split(".")
        issued_time = times[0]
        self._insert(root, 'issued', attrs={ 'date' : issued_time })

        ## Build the references
        refs = self.doc.createElement('references')
        if update.has_key("CVEs"):
            for cve in update['CVEs']:
                self._insert(refs, 'reference', attrs={
                        'type' : 'cve',
                        'href' : 'http://cve.mitre.org/cgi-bin/cvename.cgi?name=%s' %cve,
                        'id'   : cve
                })

        if update.has_key("Bugs"):
            for bug in update['Bugs']:
                self._insert(refs, 'reference', attrs={
                        'type' : 'bugzilla',
                        'href' : 'http://bugs.tizen.org/show_bug.cgi?id=%s' %bug,
                        'id'   : bug,
                        'title': 'Bug number %s' %bug
                })
        root.appendChild(refs)

        ## Errata description
        self._insert(root, 'description', text=update['Description'])

        ## The package list
        pkglist = self.doc.createElement('pkglist')
        collection = self.doc.createElement('collection')
        #collection.setAttribute('short', update.release.name)
        #self._insert(collection, 'name', text=update.release.long_name)

        for u in updates:
            filename = "rpms/%s" % (os.path.basename(u['binary']))
            if u['header'][rpm.RPMTAG_SOURCEPACKAGE] or 'debuginfo' in u['binary']:
                continue
            pkg = self._insert(collection, 'package', attrs={
                            'name'      : u['header'][rpm.RPMTAG_NAME],
                            'version'   : u['header'][rpm.RPMTAG_VERSION],
                            'release'   : u['header'][rpm.RPMTAG_RELEASE],
                            'arch'      : u['header'][rpm.RPMTAG_ARCH],
            })
            self._insert(pkg, 'filename', text=filename)

            if update.has_key('Reboot') and  update['Reboot']:
                self._insert(pkg, 'reboot_suggested', text='True')
            if update.has_key('Relogin') and  update['Relogin']:
                self._insert(pkg, 'relogin_suggested', text='True')
            if update.has_key('Restart') and update['Restart']:
                self._insert(pkg, 'restart_suggested', text='True')

            collection.appendChild(pkg)

        pkglist.appendChild(collection)
        root.appendChild(pkglist)

def parse_patch(patch_path):
    print 'Processing patch file:', patch_path
    try:
        stream = file("%s" % (patch_path), 'r')
    except IOError:
        print "Cannot read file: %s/%s" % (patch_path)

    try:
        patch = yaml.load(stream)
    except yaml.scanner.ScannerError, e:
        print 'syntax error found in yaml: %s' % str(e)

    return patch

def create_updateinfo(root, patch):
    ui = UpdateInfo()
    updates = []

    patch_id = patch['ID']

    packages = glob.glob("%s/%s/rpms/*.rpm" % (root, patch_id) ) + glob.glob("%s/%s/new/*.rpm" % (root, patch_id) )
    for package in packages:
        u = {}
        u['binary'] = package
        ts = rpm.TransactionSet("/", rpm._RPMVSF_NOSIGNATURES)
        fd = os.open(package, os.O_RDONLY)
        header = ts.hdrFromFdno(fd)
        #print header
        os.close(fd)
        u['header'] = header
        updates.append(u) 

    ui.add_patch(patch, updates)           

    # save to file
    updateinfo_xml = ui.doc.toxml()
    f = open("%s/updateinfo.xml" % root, "w")
    f.write(updateinfo_xml)
    f.close()

def create_update_file(patch_path, target_dir, destination, patch_id):
    # create zip file
    shutil.copyfile(patch_path, "%s/%s" %(target_dir, patch_id))
    zip = zipfile.ZipFile("%s/%s.zip" % (destination, patch_id ), 'w', zipfile.ZIP_DEFLATED)
    rootlen = len(target_dir) + 1
    for base, dirs, files in os.walk(target_dir):
        basedir = os.path.basename(base)
        if basedir == "rpms":
            continue
        for file in files:
            fn = os.path.join(base, file)
            zip.write(fn, "%s/%s" % (patch_id, fn[rootlen:]))
    zip.close()
    zip_checksum = get_checksum("%s/%s.zip" % (destination, patch_id))
    return zip_checksum

def update_metadata(destination, root, updates_file, patch, zip_checksum):
    # creates updates.xml
    patch_id = patch['ID']
    up = Updates(cache=updates_file)
    up.add_update(patch, "%s.zip" %patch_id, zip_checksum)
    # save to file
    updates_xml = up.doc.toxml()
    f = open("%s/updates.xml" % root, "w")
    f.write(updates_xml)
    f.close()

    if not os.path.exists("%s/data/updatemd.xml" %destination):
        os.mkdir("%s/data" %destination)
        updatemd = open("%s/data/repomd.xml" %destination, "w")
        template = """<?xml version="1.0" encoding="UTF-8"?>
    <repomd xmlns="http://linux.duke.edu/metadata/repo" xmlns:rpm="http://linux.duke.edu/metadata/rpm">
    </repomd>
    """
        updatemd.write(template)
        updatemd.close()
    else:
        for line in fileinput.input("%s/data/updatemd.xml" %destination, inplace=1):
            print line.replace("updatemd", "repomd"),
        shutil.copyfile("%s/data/updatemd.xml" %destination, "%s/data/repomd.xml" %destination)

    os.system("modifyrepo --mdtype=updates %s/updates.xml %s/data" % (root, destination))
    shutil.move("%s/data/repomd.xml" %destination, "%s/data/updatemd.xml" %destination)
    for line in fileinput.input("%s/data/updatemd.xml" %destination, inplace=1):
        print line.replace("repodata", "data"),
    for line in fileinput.input("%s/data/updatemd.xml" %destination, inplace=1):
        print line.replace("repomd", "updatemd"),

