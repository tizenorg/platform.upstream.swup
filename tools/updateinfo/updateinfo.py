import yaml
from xml.dom import minidom
import rpm
import glob
from optparse import OptionParser
import sys, os

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





parser = OptionParser()
parser.add_option('-a', '--arch',  metavar='TEXT',
              help='Architecture')
parser.add_option('-u', '--updateinfo',  metavar='TEXT',
              help='cached meta updateinfo file')
parser.add_option('-q', '--quiet', action='store_true',
              help='do not show downloading progress')
parser.add_option('-d', '--destdir', default='.', metavar='DIR',
              help='Directory where to store the updates.')
parser.add_option('-o', '--origdir', default='.', metavar='DIR',
              help='Directory where to store original packages if they do not exist already.')
parser.add_option('-p', '--patch',  metavar='TEXT',
              help='Patch information')
parser.add_option('-P', '--patchdir', metavar='DIR',
              help='directory with patch files')
parser.add_option('-t', '--testing', action='store_true',
              help='test updates')

(opts, args) = parser.parse_args()

if not opts.patch and not opts.patchdir:
    print "missing options --patch or --patchdir"
    sys.exit(1)

if opts.patch and opts.patchdir:
    print "please use only one of options --patch and --patchdir"
    sys.exit(1)

if not opts.arch:
    print "missing options -a|--arch"
    sys.exit(1)



ui = UpdateInfo(cache = opts.updateinfo)
patches = [opts.patch] if opts.patch else glob.glob(opts.patchdir+'/*.yaml')

updates = []
for patch_path in patches:
    print 'Processing patch file:', patch_path
    try:
        stream = file(patch_path, 'r')
    except IOError:
        print 'Cannot read file: %s' % patch_path

    try:
        patch = yaml.load(stream)
    except yaml.scanner.ScannerError, e:
        print 'syntax error found in yaml: %s' % str(e)

    packages = glob.glob('rpms/*.rpm') + glob.glob('new/*.rpm')
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
if opts.updateinfo:
    f = open(opts.updateinfo, "w")
else:
    f = open("updateinfo.xml", "w")
f.write(updateinfo_xml)
f.close()

# update repo
#os.system("createrepo --unique-md-filenames --basedir %s ." %packdir)
#os.system("createrepo --unique-md-filenames --basedir %s ." %sourcedir)
#os.system("createrepo --unique-md-filenames --basedir %s ." %debugdir)
#os.system("modifyrepo updateinfo.xml %s/repodata"  %packdir)
