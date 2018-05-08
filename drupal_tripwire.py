#!/usr/bin/env python2.7

import argparse
import sys
from optparse import OptionParser
from os.path import basename, join
import get_joomla_checksums
from webapp_tripwire import WebappTripwire

webapp_name = 'joomla-core'
ignore_dirs = ['language']
ignore_files = ['configuration.php', 'error.php', 'joomla_update.php']
ignore_types = ['.ini']

class DrupalTripwire(WebappTripwire):
    def get_checksums(self):
        try:
            from webapp_checksums import sums # dict of md5sums of original webapp source files 
            self.checksums = sums[self.webapp_name][self.webapp_version]
            return 0
        except ImportError:
            if self.verbose:
                print 'unable to open webapp_checksums.py'
        except KeyError:
            if self.verbose:
                print 'missing checksum for version %s'% (self.webapp_version,)
        # Download  archive and generate checksums
        get_drupal_checksums.add_checksums(self.webapp_version, verbose=True)
        from webapp_checksums import sums # dict of md5sums of original webapp source files 
        self.checksums = sums[self.webapp_name][self.webapp_version]
        return 0

    def get_webapp_version(self):
        '''
        get version from file - looks like

        Drupal 6.31, 2014-04-16
	----------------------
	- Fixed security issues (information disclosure). See SA-CORE-2014-002.

	Drupal 6.30, 2014-01-15
	----------------------
	- Fixed security issues (multiple vulnerabilities), see SA-CORE-2014-001.

        '''
	# for drupal 6.x or 7.x
        version_file = join(self.docroot, 'CHANGELOG.txt')
        try:
            f = open(version_file)
        except IOError:
	    # for drupal 8.x
	    version_file = join(self.docroot, 'core/CHANGELOG.txt')
            f = open(version_file)
        except IOError:
            if self.verbose:
                print 'Error checking webapp version'
                print 'Unable to open file %s'% (version_file,)
            return None
        version  = ''
        for line in f:
            if not version and line.startswith('Drupal'):
                version = line.split()[1].strip(',')
        f.close()
	# basic sanity check 
        if version[0] in ['6', '7', '8', '9']:
            self.webapp_version = version
            if self.verbose:
                print "Drupal version %s"% (self.webapp_version,)
	else:
            print "Unexpected result trying to determine Drupal version: %s"% (version,)
        try:
            return self.webapp_version
        except AttributeError:
            if self.verbose:
                print 'Unable to determine %s version from file %s'% (self.webapp_name, version_file,)
        return None

    def scan(self):
        '''
        Return a dict of {file: error}
        '''
        if not self.get_webapp_version():
            # this is not Drupal
            return {}
        self.get_checksums()
        return super(DrupalTripwire, self).scan()


if __name__ == '__main__':
    usage = "%s [options] path [path path] \n e.g. \n %s -c -n -e toddj@swcp.com /users/bubba/public_html/bubba.com "% \
                 (basename(__file__), basename(__file__),) 
    parser = OptionParser(usage=usage)
    parser.add_option("-v", "--verbose", action="store_true", default=False,
                        dest="verbose", help="verbose output")
    parser.add_option("-p", "--print-version", action="store_true", default=False,
                        dest="print_version", help="print web application/version if found")
    parser.add_option("-c", "--changed-files", action="store_true", default=False,
                        dest="find_changed_files", help="Scan for modified files in web application core")
    parser.add_option("-n", "--new-files", action="store_true", default=False,
                        dest="find_new_files", help="Scan for files added to web application core directories")
    parser.add_option("-w", "--whitelist-files", action="store_true", default=False,
                        dest="whitelist_files", help="add files from scan to whitelist")
    parser.add_option("-u", "--unwhitelist-files", action="store_true", default=False,
                        dest="unwhitelist_files", help="remove files on this path from whitelist")
    parser.add_option("-f", "--from-file", dest="from_file", type="string", action="store",
		      default=None, help="read file paths from a file (probably a little faster)") 
    # parser.add_option("-e", "--email", dest="email_notify", type="string", action="store") 
    (options, fs_paths) = parser.parse_args()
    if (options.whitelist_files and options.unwhitelist_files):
        print "conflicting whitelist options given"
        parser.print_help()
        sys.exit(1)
    if options.from_file:
	f = open(options.from_file)

        fs_paths += [line.strip() for line in f]
        f.close()   
    if not (fs_paths):
        print "you must specify a path to inspect"
        parser.print_help()
        sys.exit(1)

    # set() == uniq 
    for fs_path in sorted(list(set(fs_paths))):
        if options.unwhitelist_files:
            tw = DrupalTripwire(verbose=options.verbose, webapp_name=webapp_name)
            tw.remove_from_whitelist(fs_path)
        else:
            tw = DrupalTripwire(fs_path, ignore_dirs=ignore_dirs, ignore_files=ignore_files, ignore_types=ignore_types, verbose=options.verbose, exclude_files=options.whitelist_files, check_changed_files=options.find_changed_files, check_new_files=options.find_new_files, webapp_name=webapp_name)
            joomla_version = tw.get_webapp_version()
            if options.print_version and tw.get_webapp_version():
                print tw.get_webapp_details()
            for f, error in tw.scan().iteritems():
                print '%s %s'% (error, f)

