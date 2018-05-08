#!/usr/bin/env python

import hashlib
import json
import os
import re
import sys
import urllib2
import joomla_download_urls
from subprocess import call
from optparse import OptionParser
try:
    import webapp_checksums 
    sums = webapp_checksums.sums
except ImportError:
    sums = {}

ignore_dirs = ['.git', '.svn']
ignore_files = ['htaccess.txt',]
webapp_name = 'drupal'

def get_download_urls(version=False):
    download_files = {}
    try:
        archived_versions = [k for k in sums[webapp_name].keys()]
    except KeyError:
        sums[webapp_name] = {}
        archived_versions = sums
    if version:
        url = 'https://ftp.drupal.org/files/projects/drupal-%s.tar.gz'% (version,)
        try:
            handler = urllib2.urlopen( urllib2.Request(url) )
        except urllib2.HTTPError:
            print "Unable to download %s version %s"% (webapp_name, version,)
            sys.exit()
        if not handler.getcode() == 200:
            raise Exception('error retrieving ' + url)
        download_files = {version: url} 
    else:
        print "Specify which version of %s you need"% (webapp_name,)
        sys.exit()
    return download_files

def add_checksums(versions=None, keep_files=False, verbose=True):
    '''
    versions: dict of version, url 
    e.g.
    { '3.9.11': 'https://downloads.wordpress.org/release/wordpress-3.9.11.zip' }
    '''
    urls = get_download_urls(versions)
    for version, url in urls.iteritems():
        archive_file = url.split('/')[-1]
        # don't allow wget to pick file name
        assert call(['wget', '-q', url, '-O', archive_file]) == 0
        update()  
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
            print 'Added md5 checksums for %s version %s to update_webapp_checksums.py'% (webapp_name, version,)

def listdir_fullpath(d):
    for (dirpath, dirnames, filenames) in os.walk(d):
        pass
    return [os.path.join(d, f) for f in os.listdir(d)] 

def get_md5sums(directory):
    strip_chars = len(directory) + 1
    s = {}
    backward_compat_sums = { }

    for root, dirs, files in os.walk(directory):
        for d in root.split(os.sep):
            if d in ignore_dirs:
                files = ()
        for f in files:
            if f in ignore_files:
                continue
            aps_path = (os.path.join(root, f))
            file_to_check = open(aps_path) 
            data = file_to_check.read()    
            file_to_check.close() 
            md5_returned = hashlib.md5(data).hexdigest()
            s[aps_path[strip_chars:]] = md5_returned
    for f, checksum in backward_compat_sums.iteritems():
        try:
            s[f]
        except KeyError:
            s[f] = backward_compat_sums[f]
    return s

def update():
    '''
    Create md5 checksums for any tarball or zip files found
    '''
    archive_re = re.compile( r'drupal-([0-9.]+)\.(tar\.bz2|tar\.gz)$')
    archives = [a for a in (listdir_fullpath('.')) if re.search(archive_re, a)]
    for archive in archives:
        version =  re.search(archive_re, archive).group(1)
        tmp_dir = 'drupal-%s'% (version,)  
        archive_type =  re.search(archive_re, archive).group(2)
        if archive_type.startswith('tar.'):
            unpack = ['tar', 'xf', archive]
        else:
            raise Exception('This should not happen')
        assert call(unpack) == 0
        sums.setdefault(webapp_name, {})
        sums[webapp_name][version] = {}
        sums[webapp_name][version] = get_md5sums(tmp_dir)
        assert call(['rm', '-rf', tmp_dir]) == 0

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
    usage = '%s [version] [version] \n'% (os.path.basename(__file__),)
    usage += 'e.g. %s 4.3.22 \n'% (os.path.basename(__file__),)
    usage += '''
Download Drupal source and generate md5 checksums for each file for use by our webapp integrity checker.
    '''
    parser = OptionParser()
    parser = OptionParser(usage=usage)
    parser.add_option("-k", "--keep-files", dest="keep_files", action="store_true", default=False,
                      help="Keep %s archive files - default is to remove them after use"% (webapp_name,))
    (options, args) = parser.parse_args()
    if len(args):
        for version in args:
            add_checksums(version, options.keep_files)
    else:
        add_checksums(None, options.keep_files)
