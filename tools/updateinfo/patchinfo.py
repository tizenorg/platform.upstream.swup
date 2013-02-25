#!/usr/bin/python
# vim: ai ts=4 sts=4 et sw=4

#    Copyright (c) 2009 Intel Corporation
#
#    This program is free software; you can redistribute it and/or modify it
#    under the terms of the GNU General Public License as published by the Free
#    Software Foundation; version 2 of the License
#
#    This program is distributed in the hope that it will be useful, but
#    WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
#    or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
#    for more details.
#
#    You should have received a copy of the GNU General Public License along
#    with this program; if not, write to the Free Software Foundation, Inc., 59
#    Temple Place - Suite 330, Boston, MA 02111-1307, USA.

import os,sys
import optparse
import yaml
import glob

CSS_STRIKE = 'a.strike_link { text-decoration: line-through; }'

# TODO configurable
SMTP_SERVER = "or-out.intel.com"

def get_recipient_mail():
    # TODO configurable

    name = 'Anas'
    mail = 'anas.nashif@intel.com'

    return name, mail

def get_sender_mail():
    # TODO configurable

    name = 'Jian-feng Ding'
    mail = "jian-feng.ding@intel.com"

    return name, mail

def _send_email(To, From, Message, smtpserver, smtpuser=None, smtppass=None):
    import smtplib

    if not isinstance(To, list):
        To = [To] 

    print "Sending email to %s ..." % ', '.join(['<%s>' % m for m in To])

    if smtpuser and smtppass:
        AUTHREQUIRED = 1
    else:
        AUTHREQUIRED = 0

    SENDER = From

    session = smtplib.SMTP(smtpserver)
    if AUTHREQUIRED:
        session.login(smtpuser, smtppass)
    smtpresult = session.sendmail(SENDER, To, Message)

    if smtpresult:
        errstr = ""
        for recip in smtpresult.keys():
            errstr = """Could not delivery mail to: %s
Server said: %s
%s

%s""" % (recip, smtpresult[recip][0], smtpresult[recip][1], errstr)
        raise smtplib.SMTPException, errstr

        sys.exit('Sending email failed. Please do so using your email client\n')

def _load_yamlfile(path):
    try:
        stream = file(path, 'r')
    except IOError:
        print >>sys.stderr, 'Cannot read file: %s' % path

    try:
        data = yaml.load(stream)
    except yaml.scanner.ScannerError, e:
        print >>sys.stderr, 'syntax error found in yaml: %s' % str(e)

    return data

def _desc_to_html(page, desc):
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

def get_title(t, is_html = False):
    if is_html:
        import markup
        page = markup.page()
        page.init( title = t, style = CSS_STRIKE)
        page.h1(t)
        return str(page).rstrip('</html>').rstrip().rstrip('</body>')
    else:
        return t

def get_summary_info(sum, is_html = False):
    if is_html:
        import markup
        page = markup.page()
        page.h2(sum['Title'])
        _desc_to_html(page, sum['Description'])

        return str(page)

    else:
        return '%s\n%s' %(sum['Title'], sum['Description'])

def get_patch_info(update, is_html = False):
    if is_html:
        import markup
        page = markup.page()
        page.h3(update['Title'])
        _desc_to_html(page, update['Description'])

        if update.has_key("Bugs"):
            page.p.open()
            page.add('Resolved Bugs: ')
            firstone = True
            for bug in update['Bugs']:
                if firstone:
                    firstone = False
                else:
                    page.add(', ')
                page.a(bug, href='http://bugs.meego.com/show_bug.cgi?id=%s' %bug, class_="strike_link")
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
    Status: %s
    Packages: %s
    Description:
        %s
""" % (update['ID'],
       update['Title'],
       update['Type'],
       update['Project'],
       update['Repository'],
       update['Release'],
       update['Status'],
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
                bug_info += '       http://bugs.meego.com/show_bug.cgi?id=%s\n' %bug
            INFO += bug_info

        if update.has_key('Reboot') and  update['Reboot']:
            INFO += '    NOTE: reboot needed\n'
        if update.has_key('Relogin') and  update['Relogin']:
            INFO += '    NOTE: relogin needed\n'
        if update.has_key('Restart') and update['Restart']:
            INFO += '    NOTE: restart needed\n'

    return INFO


if __name__ == '__main__':

    usage = "Usage: %prog [options] [yaml-path]"
    parser = optparse.OptionParser(usage)

    parser.add_option("-P", "--patchdir", metavar="DIR", default=None,
                      help="Dir of patch yaml files")
    
    parser.add_option("-t", "--title", default=None,
                      help="Title for all patch info")

    parser.add_option("-m", "--sendmail", action="store_true", default=False,
                      help="To sendmail")

    parser.add_option("-H", "--html", action="store_true", default=False,
                      help="Use HTML as the format for output")

    opts, args = parser.parse_args()

    patches = args
    if opts.patchdir:
        patches += glob.glob(os.path.join(opts.patchdir, '*.yaml'))

    sum_yaml = None
    for p in patches[:]:
        if 'summary.yaml' in p:
            if not sum_yaml:
                sum_yaml = p
                patches.remove(p)
            else:
                print >>sys.stderr, 'Multiple summay.yaml found, maybe an error, quit'
                sys.exit(1)
        elif not p.endswith('.yaml') and not p.endswith('.yml'):
            print >>sys.stderr, 'unsupported file: %s found, skip' %p
            patches.remove(p)

    if not patches:
        print >>sys.stderr, 'Please specify YAML files'
        sys.exit(1)

    is_html = opts.html and not opts.sendmail

    if opts.title:
        patch_info = get_title(opts.title, is_html)
    else:
        if is_html:
            patch_info = '<body><style type="text/css"><!--\n' + CSS_STRIKE + '\n--></style>'
        else:
            patch_info = ''

    if sum_yaml:
        sum = _load_yamlfile(sum_yaml)
        patch_info += get_summary_info(sum, is_html)

    if is_html:
        patch_info += "<h2>Detailed information about changes in this update</h2>"
    else:
        patch_info += "Detailed information about changes in this update"

    for pf in patches:
        patch = _load_yamlfile(pf)
        patch_info += get_patch_info(patch, is_html)

    if is_html:
        if opts.title:
            patch_info += '</body></html>'
        else:
            patch_info += '</body>'

    if opts.sendmail:
        s_name, s_mail = get_sender_mail()
        r_name, r_mail = get_recipient_mail()
        MESSAGE = """To: %s
From: %s <%s>
Bcc: %s <%s>
Subject: Summary of Patch information (based on YAML)

Hi %s,

%d patch yaml files are scanned, all the details as the following:
%s

---

%s

""" %(r_mail, s_name, s_mail, s_name, s_mail, r_name, len(patches), patch_info, s_name)
        _send_email(r_mail, s_mail, MESSAGE, SMTP_SERVER)
    else:
        print patch_info
    
