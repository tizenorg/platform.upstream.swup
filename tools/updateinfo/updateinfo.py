import yaml
from xml.dom import minidom
import rpm
import glob
from optparse import OptionParser
import sys, os
import zipfile
import hashlib
import shutil
import fileinput

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

    def _insert(self, parent, name, attrs={}, text=None):
        """ Helper function to trivialize inserting an element into the doc """
        child = self.doc.createElement(name)
        for item in attrs.items():
            child.setAttribute(item[0], unicode(item[1]))
        if text:
            txtnode = self.doc.createTextNode(unicode(text))
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

        self._insert(root, 'description', text=update['Description'])

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

    def _insert(self, parent, name, attrs={}, text=None):
        """ Helper function to trivialize inserting an element into the doc """
        child = self.doc.createElement(name)
        for item in attrs.items():
            child.setAttribute(item[0], unicode(item[1]))
        if text:
            txtnode = self.doc.createTextNode(unicode(text))
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
                'status'    : update['Status'],
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
            filename = u['binary']
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

def parse_patch( patch_path):
    print 'Processing patch file:', patch_path
    try:
        stream = file("%s" % ( patch_path), 'r')
    except IOError:
        print "Cannot read file: %s/%s" % ( patch_path)

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

def create_update_file(target_dir, destination, patch_id):
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
    up = Updates(cache=opts.updatesfile)
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



parser = OptionParser()
parser.add_option('-u', '--updateinfo',  metavar='TEXT',
              help='cached meta updateinfo file')
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
parser.add_option('-t', '--testing', action='store_true',
              help='test updates')

(opts, args) = parser.parse_args()

root = os.getcwd()
if not opts.patch:
    print "missing options --patch. You need to point to a patch file (YAML format)"
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
patch = parse_patch ( patch_path)
patch_id = patch['ID']
target_dir = "%s/%s" % (root, patch_id)

os.system("createrepo --deltas --oldpackagedirs=%s %s/%s" % (opts.original, root, patch_id))

# create updateinfo
create_updateinfo(root, patch)

# update repo
os.system("modifyrepo %s/updateinfo.xml %s/%s/repodata"  % (root, root, patch_id))

zip_checksum = create_update_file(target_dir, destination,  patch_id)

update_metadata(destination, root, opts.updatesfile, patch, zip_checksum)