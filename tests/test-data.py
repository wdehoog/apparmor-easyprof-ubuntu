#!/usr/bin/python3
#  Author: Jamie Strandboge <jamie@ubuntu.com>
#  Copyright (C) 2013-2014 Canonical Ltd.
#
#  This script is distributed under the terms and conditions of the GNU General
#  Public License, Version 3 or later. See http://www.gnu.org/copyleft/gpl.html
#  for details.

from __future__ import print_function
import glob
import json
import optparse
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

topdir = None
debugging = False

def recursive_rm(dirPath, contents_only=False):
    '''recursively remove directory'''
    names = os.listdir(dirPath)
    for name in names:
        path = os.path.join(dirPath, name)
        if os.path.islink(path) or not os.path.isdir(path):
            os.unlink(path)
        else:
            recursive_rm(path)
    if contents_only == False:
        os.rmdir(dirPath)

def cmd(command):
    '''Try to execute the given command.'''
    try:
        sp = subprocess.Popen(command, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              universal_newlines=True)
    except OSError as ex:
        return [127, str(ex)]

    out = sp.communicate()[0]
    return [sp.returncode, str(out)]

def debug(s):
    global debugging
    if not debugging:
        return
    print("DEBUG: %s" % s)

class T(unittest.TestCase):
    def setUp(self):
        '''Setup for tests'''
        global topdir
        self.data_dir = os.path.join(topdir, 'data')

        self.tmpdir = tempfile.mkdtemp(prefix='test-aa-easyprof-ubuntu')
        shutil.copytree(os.path.join(self.data_dir, 'templates'), \
                                     os.path.join(self.tmpdir, 'templates'))
        shutil.copytree(os.path.join(self.data_dir, 'policygroups'), \
                                     os.path.join(self.tmpdir, 'policygroups'))

        hardware_dir = os.path.join(self.tmpdir, 'hardware')
        shutil.copytree(os.path.join(self.data_dir, 'hardware'), hardware_dir)

        self.security = dict()
        self.security['profiles'] = dict()

        self.name = "com.ubuntu.testme"
        self.appname = "foo"
        self.version = "0.1"
        self.app_id_dbus = "com_2eubuntu_2etestme_5ffoo_5f0_2e1"
        self.app_pkgname_dbus = "com_2eubuntu_2etestme"

        self.profile_name = "%s_testme.desktop_%s" % (self.name, self.version)

        # create a profile
        p = dict()
        p['policy_version'] = 1.0
        p['policy_vendor'] = "ubuntu"
        p['policy_groups'] = []
        p['template_variables'] = dict()
        p['template_variables']['APP_PKGNAME'] = self.name
        p['template_variables']['APP_APPNAME'] = self.appname
        p['template_variables']['APP_VERSION'] = self.version
        p['template_variables']['APP_ID_DBUS'] = self.app_id_dbus
        p['template_variables']['APP_PKGNAME_DBUS'] = self.app_pkgname_dbus
        p['template_variables']['CLICK_DIR'] = '/opt/click.ubuntu.com'

        self.security['profiles'][self.profile_name] = p

        # Update the templates to use the location of the temporary directory
        # for hardware-specific accesses rather than the system one, so we can
        # test them
        for vendor_dir in glob.glob("%s/templates/*" % self.tmpdir):
            for version_dir in glob.glob("%s/*" % vendor_dir):
                for template_fn in glob.glob("%s/*" % version_dir):
                    rc, out = cmd(['sed', '-i',
                                   's,/usr/share/apparmor/hardware/,%s/,g' % \
                                       hardware_dir,
                                   template_fn])
                    self.assertTrue(rc == 0, "sed exited with error")

        # Update the policy groups to use the location of the temporary
        # directory for hardware-specific accesses rather than the system one,
        # so we can test them
        for vendor_dir in glob.glob("%s/policygroups/*" % self.tmpdir):
            for version_dir in glob.glob("%s/*" % vendor_dir):
                for group_fn in glob.glob("%s/*" % version_dir):
                    rc, out = cmd(['sed', '-i',
                                   's,/usr/share/apparmor/hardware/,%s/,g' % \
                                       hardware_dir,
                                   group_fn])
                    self.assertTrue(rc == 0, "sed exited with error")

    def _add_policy_group(self, g, name=None):
        pn = self.profile_name
        if name is not None:
            pn = name
        if g not in self.security['profiles'][pn]['policy_groups']:
            self.security['profiles'][pn]['policy_groups'].append(g)

    def _del_policy_group(self, g, name=None):
        pn = self.profile_name
        if name is not None:
            pn = name
        if g in self.security['profiles'][pn]['policy_groups']:
            self.security['profiles'][pn]['policy_groups'].remove(g)

    def _update_template(self, t, name=None):
        pn = self.profile_name
        if name is not None:
            pn = name
        self.security['profiles'][pn]['template'] = t

    def tearDown(self):
        '''Clean up after each test_* function'''
        if os.path.exists(self.tmpdir):
            recursive_rm(self.tmpdir)

    def emit_json(self, manifest=None):
        '''Emit json'''
        m = dict()
        m['security'] = self.security
        if manifest:
            m['security'] = manifest

        return json.dumps(m, indent=2)

    def _easyprof(self):
        '''Run easyprof'''
        contents = self.emit_json()
        debug("\n" + contents)
        out_dir = os.path.join(self.tmpdir, "out")
        m = os.path.join(self.tmpdir, "manifest")
        open(m, 'w').write(contents)
        rc, out = cmd(['aa-easyprof',
                       '--templates-dir=%s' % os.path.join(self.tmpdir, 'templates'),
                       '--policy-groups-dir=%s' % os.path.join(self.tmpdir, 'policygroups'),
                       '--manifest=%s' % m,
                       '--output-directory=%s' % out_dir,
                      ])
        self.assertTrue(rc == 0,
                        "aa-easyprof exited with error:\n%s\n%s\n[%d]" % (\
                            contents, out, rc)
                       )

        for fn in glob.glob("%s/*" % out_dir):
            debug(fn)
            debug("\n%s" % open(fn, 'r').read())

        if os.path.exists(out_dir):
            recursive_rm(out_dir)

    def test_templates(self):
        '''Test templates'''
        debug("")
        for vendor_dir in glob.glob("%s/templates/*" % self.tmpdir):
            vendor = os.path.basename(vendor_dir)
            for version_dir in glob.glob("%s/*" % vendor_dir):
                version = os.path.basename(version_dir)
                self.security['profiles'][self.profile_name]\
                             ['policy_version'] = version
                for template_fn in glob.glob("%s/*" % version_dir):
                    template = os.path.basename(template_fn)
                    self._update_template(template)
                    debug("%s/%s/%s" % (vendor, version, template))
                    self._easyprof()

    def test_policygroups(self):
        '''Test policygroups'''

        debug("")
        for vendor_dir in glob.glob("%s/policygroups/*" % self.tmpdir):
            vendor = os.path.basename(vendor_dir)
            for version_dir in glob.glob("%s/*" % vendor_dir):
                version = os.path.basename(version_dir)
                self.security['profiles'][self.profile_name]\
                             ['policy_version'] = version
                for group_fn in glob.glob("%s/*" % version_dir):
                    group = os.path.basename(group_fn)
                    self._add_policy_group(group)
                    for template_fn in glob.glob("%s/templates/%s/%s/*" % (\
                                                 self.tmpdir,
                                                 vendor,
                                                 version)):
                        template = os.path.basename(template_fn)
                        self._update_template(template)
                        debug("%s/%s/%s (%s)" % (vendor, version, group, template))
                        self._easyprof()
                    self._del_policy_group(group)

#
# Main
#
if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option("-d", "--debug",
                      dest='debug',
                      help='emit debugging information',
                      action='store_true',
                      default=False)
    (opt, args) = parser.parse_args()
    if opt.debug:
        debugging = True

    absfn = os.path.abspath(sys.argv[0])
    topdir = os.path.dirname(os.path.dirname(absfn))

    if len(sys.argv) > 1 and sys.argv[1] == '-d':
        debugging = True

    # run the tests
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(T))
    rc = unittest.TextTestRunner(verbosity=2).run(suite)

    found_parser = False
    for path in os.environ["PATH"].split(":"):
        if os.path.exists(path + "/" + "apparmor_parser"):
            found_parser = True
            break
    if not found_parser:
        print("WARN: could not find apparmor_parser. Policy syntax not verified")

    if not rc.wasSuccessful():
        sys.exit(1)

