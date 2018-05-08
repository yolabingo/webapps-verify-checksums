#!/usr/bin/env python

import hashlib
import json
import os
import re
import sys
import urllib2
from subprocess import call
from optparse import OptionParser
try:
    import webapp_checksums 
    sums = webapp_checksums.sums
except (AttributeError, ImportError):
    sums = {}

class WpAddonChecksums(object):
    def __init__(self, addon_type, addon_name, addon_version, verbose=False):
        self.ignore_dirs = ['.git', '.svn']
        self.ignore_files = []
        self.addon_type = addon_type
        self.addon_name = addon_name
        self.addon_version = addon_version
        self.verbose = verbose
        self.addon_key = 'wordpress-%s-%s'% (addon_type, addon_name)

    def get_download_url(self):
        '''
        Get download URLs for a specific requested WP version, or for 
        the few most current releases via api.wordpress.org
        '''
        download_files = {}
        try:
            archived_versions = [k for k in sums[self.addon_key].keys()]
        except KeyError:
            sums[self.addon_key] = {}
            archived_versions = sums
        url = 'https://downloads.wordpress.org/%s/%s.%s.zip'% (self.addon_type, self.addon_name, self.addon_version)
        try:
            handler = urllib2.urlopen( urllib2.Request(url) )
        except urllib2.HTTPError:
            if self.verbose:
                print 'Unable to open URL ' + url
            return None
        if not handler.getcode() == 200:
            raise Exception('error retrieving ' + url)
        return url

    def add_checksums(self, keep_files=False, verbose=True):
        '''
        versions: dict of version, url 
        e.g.
        { '3.9.11': 'https://downloads.wordpress.org/release/wordpress-3.9.11.zip' }
        '''
        if not (self.addon_type and self.addon_name and self.addon_version):
            # this is non-public, home made, old, etc - not downloadable
            return 0
        url = self.get_download_url()
        if not url:
            return None
        archive_file = url.split('/')[-1]
        # don't allow wget to pick file name
        assert call(['wget', '-q', url, '-O', archive_file]) == 0
        self.update()
        try:
            # reload webapp_checksums.py if we just updated it
            reload(webapp_checksums)
        except NameError:
            # or initial import if file did not exist previously
            import webapp_checksums
        sums = webapp_checksums.sums
        if not keep_files:
            assert call(['rm', archive_file]) == 0
        if verbose: 
            print 'Added md5 checksums for wordpress %s %s version %s to webapp_checksums.py'% (self.addon_type, self.addon_name, self.addon_version)
        return 0


    def get_md5sums(self, directory):
        strip_chars = len(directory) + 1
        s = {}
        # these are lingering on quite a few sites
        note = '# files lingering from old WP versions #'
        for root, dirs, files in os.walk(directory):
            for d in root.split(os.sep):
                if d in self.ignore_dirs:
                    files = ()
            for f in files:
                if f in self.ignore_files:
                    continue
                aps_path = (os.path.join(root, f))
                file_to_check = open(aps_path) 
                data = file_to_check.read()    
                file_to_check.close() 
                md5_returned = hashlib.md5(data).hexdigest()
                if md5_returned:
                    s[aps_path[strip_chars:]] = md5_returned
#       backward_compat_sums = { }
#       for f, checksum in backward_compat_sums.iteritems():
#           try:
#               s[f]
#           except KeyError:
#               s[f] = backward_compat_sums[f]
        return s

    def update(self):
        '''
        Get md5 checksums 
        '''
        archive_file = self.get_download_url().split('/')[-1]
        call(['rm', '-rf', self.addon_type])
        call(['mkdir', self.addon_type]) == 0
        unpack = ['unzip', '-qq',  archive_file, '-d', self.addon_type]
        assert call(unpack) == 0
        sums.setdefault(self.addon_key, {})
        sums[self.addon_key][self.addon_version] = {}
        sums[self.addon_key][self.addon_version] = self.get_md5sums(os.path.join(self.addon_type, self.addon_name))
        call(['rm', '-rf', self.addon_type])

        f = open('webapp_checksums.py', 'w')
        f.write('sums = %s'% (sums,))
        # pretty printing options for the file
        f.write(""" 
if __name__ == '__main__':
    for webapp in sums.keys():
        print webapp
        for version in sums[webapp].keys():
            print version
            for f, md5sum in sums[webapp][version].iteritems():
                print '%s  %s  %s \t%s'% (webapp, version, f, md5sum)
        """)


if __name__ == '__main__':
    usage = '%s theme|plugin <name> <version> \n'% (os.path.basename(__file__),)
    usage += 'e.g. %s theme twentyfifteen 1.4 \n'% (os.path.basename(__file__),)
    usage += '''
Download sources from api.wordpress.org and generate md5 checksums for each file,
to be used by our webapp integrity checker.

Or specify specific versions needed.
    '''
    parser = OptionParser()
    parser = OptionParser(usage=usage)
    parser.add_option("-k", "--keep-files", dest="keep_files", action="store_true", default=False,
                      help="Keep WP archive files - default is to remove them after use")
    (options, args) = parser.parse_args()
    try:
        addon_type = args[0]
        addon_name = args[1] 
        addon_version = args[2] 
        # addon_key = 'wordpress'
    except Exception as e:
        parser.print_help()
        raise e
    WpAddonChecksums(addon_type, addon_name, addon_version).add_checksums(options.keep_files)
