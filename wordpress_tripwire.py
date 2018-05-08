#!/usr/bin/env python

import argparse
import sys
from optparse import OptionParser
from os import setuid, stat
from os.path import basename, join
from subprocess import call, check_output, CalledProcessError
from pwd import getpwuid
import get_wordpress_checksums
from get_wordpress_addon_checksums import WpAddonChecksums
from webapp_tripwire import WebappTripwire

webapp_name = 'wordpress-core'
ignore_files = ['error_log', 'wp-config.php',]

class WordpressTripwire(WebappTripwire):
    def get_checksums(self):
        try:
            import webapp_checksums # dict of md5sums of original webapp source files 
            self.checksums = webapp_checksums.sums[self.webapp_name][self.webapp_version]
            return 0
        except ImportError:
            if self.verbose:
                print 'unable to open webapp_checksums.py'
        except KeyError:
            if self.verbose:
                print 'missing checksum for version %s'% (self.webapp_version,)
        # Download needed WP archive and generate checksums
        get_wordpress_checksums.add_checksums(self.webapp_version, verbose=True)
        reload(webapp_checksums)
        self.checksums = webapp_checksums.sums[self.webapp_name][self.webapp_version]
        return 0

    def get_webapp_version(self):
        '''
        get WP version from file - looks like
        $wp_version = '4.4.2';
        '''
        version_file = join(self.docroot, 'wp-includes/version.php')
        try:
            f = open(version_file)
        except IOError:
            if self.verbose:
                print 'Error checking WP  version'
                print 'Unable to open file %s'% (version_file,)
            return None
        for line in f:
            if line.startswith('$wp_version ='):
                self.webapp_version = line.split("'")[1]
        try:
            return self.webapp_version
        except AttributeError:
            if self.verbose:
                print 'Unable to determine WP version from file  %s'% (version_file,)
        return None

    def scan_core(self):
        '''
        Return a dict of {file: error}
        '''
        if not self.get_webapp_version():
            # this is not Wordpress install
            return {}
        self.get_checksums()
        return super(WordpressTripwire, self).scan()

## END class WordpressTripwire(WebappTripwire) ##

## BEGIN wp-cli bits ##
def get_checksums(addon_type, addon_name, addon_version):
    addon_key = 'wordpress-%s-%s'% (addon_type, addon_name)
    try:
        import webapp_checksums 
        return webapp_checksums.sums[addon_key][addon_version]
    except ImportError:
        if options.verbose:
            print 'unable to open webapp_checksums.py'
    except KeyError:
        if options.verbose:
            print 'missing checksum for %s version %s'% (addon_key, addon_version,)
    # try and download needed WP archive and generate checksums
    WpAddonChecksums(addon_type, addon_name, addon_version).add_checksums()
    try:
        reload(webapp_checksums)
    except NameError:
        import webapp_checksums
    try: 
        return webapp_checksums.sums[addon_key][addon_version]
    except KeyError:
        return {}

def get_wp_plugins_dir(fs_path):
    return check_output(['/root/webapp_scanner/get_wordpress_plugins_dir', fs_path]).strip()

def get_wp_themes_dir(fs_path):
    return check_output(['/root/webapp_scanner/get_wordpress_themes_dir', fs_path]).strip()

def get_wp_plugins(fs_path):
    cmd = ['/root/webapp_scanner/get_wordpress_plugins', fs_path]
    return parse_wp_cli_addons(cmd)

def get_wp_themes(fs_path):
    cmd = ['/root/webapp_scanner/get_wordpress_themes', fs_path]
    return parse_wp_cli_addons(cmd)

def scan_wp_addons(fs_path, addon_type):
    if addon_type == 'plugin':
        addons_dir = get_wp_plugins_dir(fs_path)
        addons = get_wp_plugins(fs_path)
    elif addon_type == 'theme':
        addons_dir = get_wp_themes_dir(fs_path)
        addons = get_wp_themes(fs_path)
    else:
        print "unknown WP addon type %s"% (addon_type,)
    for addon in addons:
        name = addon[0]
        version = addon[3]
        checksums = get_checksums(addon_type, name, version)
        if checksums:
            addon_path = join(addons_dir, name)
            addon_tw = WebappTripwire(addon_path, verbose=options.verbose, exclude_files=options.whitelist_files, check_changed_files=options.find_changed_files, check_new_files=options.find_new_files)
            addon_tw.checksums = checksums
            addon_tw.webapp_name = name
            addon_tw.webapp_version = version
            for f, error in addon_tw.scan().iteritems():
                print '%s %s'% (error, f)

def scan_wp_plugins(fs_path):
    scan_wp_addons(fs_path, 'plugin')

def scan_wp_themes(fs_path):
    scan_wp_addons(fs_path, 'theme')

def parse_wp_cli_addons(cmd):
    '''
    e.g.
    name    status  update  version
    Aqua    active  none    2.0
    '''
    results = []
    validated = False
    for line in check_output(cmd).strip().split("\n"):
        name = status = update = version = None
        if validated:
            try:
                (name, status, update, version) = line.split()
            except ValueError as e:
                name = line.split()[0]
            results.append((name, status, update, version))
        else:
            assert len(line.split()) == 4
            assert line.split()[0] == 'name'
            assert line.split()[1] == 'status'
            assert line.split()[2] == 'update'
            assert line.split()[3] == 'version'
            validated = True
    return results
## END wp-cli bits ##

def min_version(v1, v2):
    '''
    return True if v1 >= v2
    turn version numbers into lists 
    so we can use cmp() to see which is greater
    '''
    v1 = [int(x) for x in v1.split(".")]
    v2 = [int(x) for x in v2.split(".")]
    return (cmp(v1, v2) >= 0)


if __name__ == '__main__':
    usage = "%s [options] path [path path] \n e.g. \n %s -c -n -e bubba@bubba.com /users/bubba/public_html/bubba.com "% \
                 (basename(__file__), basename(__file__),) 
    parser = OptionParser(usage=usage)
    parser.add_option("-v", "--verbose", action="store_true", default=False,
                        dest="verbose", help="verbose output")
    parser.add_option("-V", "--print-version", action="store_true", default=False,
                        dest="print_version", help="print web application name and version, if found")
    parser.add_option("-p", "--scan-plugins", action="store_true", default=False,
                        dest="scan_plugins", help="scan WP plugins")
    parser.add_option("-t", "--scan-themes", action="store_true", default=False,
                        dest="scan_themes", help="scan WP themes")
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
            tw = WordpressTripwire(verbose=options.verbose, webapp_name=webapp_name)
            tw.remove_from_whitelist(fs_path)
        else:
            tw = WordpressTripwire(fs_path, ignore_files=ignore_files, verbose=options.verbose, exclude_files=options.whitelist_files, check_changed_files=options.find_changed_files, check_new_files=options.find_new_files, webapp_name=webapp_name)
            wp_version = tw.get_webapp_version()
            if wp_version:
                if options.scan_plugins or options.scan_themes:
                    wp_cli_min_version = '3.5.2'
                    if not min_version(wp_version, wp_cli_min_version):
                        options.scan_plugins = False
                        options.scan_themes = False
                        print "wp-cli plugin and theme scans require WP version %s - you have %s"% (wp_cli_min_version, wp_version)
                if options.print_version:
                    print tw.get_webapp_details()
                    if options.scan_plugins:
                        print 'Plugins:'
                        for p in get_wp_plugins(fs_path):
                            print '%s:\t%s'% (p[0], p[3])
                    if options.scan_themes:
                        print 'Themes:'
                        for t in get_wp_themes(fs_path):
                            print '%s:\t%s'% (t[0], t[3])
                if options.scan_plugins:
                    scan_wp_plugins(fs_path)
                if options.scan_themes:
                    scan_wp_themes(fs_path)
            tw = WordpressTripwire(fs_path, ignore_files=ignore_files, verbose=options.verbose, exclude_files=options.whitelist_files, check_changed_files=options.find_changed_files, check_new_files=options.find_new_files, webapp_name=webapp_name)
            for f, error in tw.scan_core().iteritems():
                print '%s %s'% (error, f)

