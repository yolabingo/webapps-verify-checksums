#!/usr/bin/env python2.7

import hashlib
import re
import subprocess
import sys
import os
from pwd import getpwuid
from types import *

class WebappTripwire(object):
    '''
    Compare checksums of web application core files with original versions
    Look for unexpected files interspersed with original web app files
    '''
    def __init__(self, docroot='/tmp', ignore_dirs=[], ignore_files=[], ignore_types=[], verbose=False, checksums={}, exclude_files=False, webapp_name='', check_changed_files=False, check_new_files=False):
        self.docroot = docroot
        self.checksums = checksums
        self.exclude_files = exclude_files
        self.whitelist = []
        self.whitelist_file = 'whitelist.py'
        self.suspect_files = {}
        self.ignore_dirs = ignore_dirs + ['.hg', '.git', '.svn', '.DS_Store', '.DS._Store']
        self.ignore_files = ignore_files + ['.DS_Store']

        self.ignore_types  =  ignore_types + ['.png', '.jpg', '.jpeg', '.gif', '.ico', '.flv', '.as'] 
        self.ignore_types +=  ['php.ini', '.xml.gz', '.svg', '.psd', '.css', '.json', '.m4v', '.swf']
        self.ignore_types +=  ['.tar.gz', '.sql', '.sql.gz', '.zip', '.bak', '.old', '.pdf', '.doc', ]
        self.ignore_types +=  ['.docx', '.xml', '.txt', '.htm', '.html', '.shtml', 'README', '.ftpquota']
        self.ignore_types +=  ['.GIF', '.PNG', '.JPG', '.db']

        self.ignore_globs =  [re.compile('^webhits-20[0-9]+\.html$'), re.compile('^google[a-z0-9]+\.html$'), re.compile('^sitemap\.xml')] 
        self.ignore_globs += [re.compile('^BingSiteAuth\.xml$'), re.compile('^\.htaccess'), re.compile('^robots\.txt$')]
        self.verbose = verbose
        self.webapp_name = webapp_name
        self.webapp_version = 'Unknown version'
        self.check_changed_files = check_changed_files
        self.check_new_files = check_new_files
        self.empty_file_md5 = 'd41d8cd98f00b204e9800998ecf8427e'
        self.get_whitelist()

    def get_username(self):
        index_file = os.path.join(self.docroot, 'index.php')
        return getpwuid(os.stat(index_file).st_uid).pw_name

    def get_webapp_details(self):
        return '%s looks like %s version %s'% (self.docroot, self.webapp_name, self.webapp_version)

    def check_file_sum(self, abs_path):
        original_md5 = self.get_original_md5(abs_path)
        try:
            curr_md5 = self.get_curr_md5(abs_path)
        except IOError:
            self.found_suspect_file(abs_path, 'Cannot read file', '# cannot read file #')
            return 
        if self.check_new_files and not original_md5: 
            self.found_suspect_file(abs_path, 'Unexpected file', curr_md5)
        elif self.check_changed_files and original_md5: 
            if isinstance(original_md5, StringTypes):
                if original_md5 != curr_md5:
                    self.found_suspect_file(abs_path, 'Modified file', curr_md5)
                    if self.verbose:
                        print "File modified: %s"% (abs_path,)
                elif self.verbose:
                    print "File not modified: %s"% (abs_path,)
            else:
                # iterate through multiple possible hashes
                sums_match = False
                for i in original_md5:
                    if i == curr_md5:
                        sums_match = True
                if not sums_match:
                    self.found_suspect_file(abs_path, 'Modified file', curr_md5)
                elif self.verbose:
                    print "File not modified: %s"% (abs_path,)

    def found_suspect_file(self, abs_path, reason, md5):
        if md5 == self.empty_file_md5:
            if self.verbose:
                print "Skipping empty file: %s"% (abs_path,)
        elif abs_path in self.whitelist:
            if self.whitelist[abs_path] != md5:
                reason = 'Whitelisted file modified'
                self.suspect_files[abs_path] = reason
                if self.verbose:
                    print "%s: %s"% (reason, abs_path,)
        else:
            self.suspect_files[abs_path] = reason
            if self.verbose:
                print "%s: %s"% (reason, abs_path,)

    def scan(self):
        suspect_files = {}
        if not (self.check_new_files or self.check_changed_files):
            print "No scan was selected (new files or changed files) so nothing to be done"
            return suspect_files 
        scanned_dirs = self.get_scanned_dirs()
        for root, dirs, files in os.walk(self.docroot):
            original_md5 = ''
            for d in self.ignore_dirs:
                if d in root.split('/'):    
                    if self.verbose:
                        print "Skipping ignored directory %s "% (root,)
                    files = ()
            if root not in scanned_dirs:
                if self.verbose:
                    print "Skipping directory %s "% (root,)
                files = ()
            for f in files:
                check_file = True
                abs_path = (os.path.join(root, f))
                if f in self.ignore_files:
                    check_file = False
                    if self.verbose:
                        print 'Skipping ignored file %s'% (abs_path,)
                for filetype in self.ignore_types:
                    if f.endswith(filetype):
                        check_file = False
                        if self.verbose:
                            print 'Skipping ignored file type "%s" %s'% (filetype, abs_path,)
                for glob in self.ignore_globs:
                    if re.search(glob, f):
                        check_file = False
                        if self.verbose:
                            print 'Skipping ignored file %s'% (abs_path,)
                if check_file:
                    self.check_file_sum(abs_path)
        if self.exclude_files:
            # add suspect files to permanent whitelist
            for abs_path in self.suspect_files.keys():
                self.add_to_whitelist(abs_path)
                del(self.suspect_files[abs_path])
                if self.verbose:
                    print 'Added to whitelist: %s'% (abs_path,)
        return self.suspect_files

    def get_curr_md5(self, filepath):
        file_to_check = open(filepath)
        data = file_to_check.read()    
        file_to_check.close()
        return hashlib.md5(data).hexdigest()

    def get_original_md5(self, filepath):
        # get fs path relative to wp install
        f = filepath.replace(self.docroot, '').strip('/')
        try:
            return self.checksums[f]
        except KeyError:
            pass
        return None
    
    def get_scanned_dirs(self):
        '''
        list of directories we have checksums for
        '''
        scanned_dirs = {self.docroot: ''}
        # sorry not sorry
        # strip filename from checksum file and prepend docroot
        # e.g. wp-admin/index.php -> /users/bubba/public_html/wp-admin
        # os.sep == '/' 
        relative_paths = ['/'.join(f.split('/')[:-1]) for f in self.checksums.keys() if '/' in f]
        for p in relative_paths:
            d = os.path.join(self.docroot, p)
            scanned_dirs[d] = ''
        return scanned_dirs.keys()
    
    def add_to_whitelist(self, filepath):
        try:
            self.whitelist[filepath] = self.get_curr_md5(filepath)
        except IOError:
            self.whitelist[filepath] = '# cannot read file #'
        self.update_whitelist_file()

    def get_whitelist(self):
        try:
            import whitelist
            self.whitelist = whitelist.wl
        except (AttributeError, ImportError) as e:
            self.whitelist = dict()
            self.update_whitelist_file()

    def remove_from_whitelist(self, filepath):
        for f in self.whitelist.keys():
            if filepath in f:
                del(self.whitelist[f])
                if self.verbose:
                    print "removed from whitelist %s"% (f,)
        self.update_whitelist_file()

    def update_whitelist_file(self):
        f = open(self.whitelist_file, 'w')
        f.write("""#!/usr/bin/env python
# Autogenerated by swcp webapp integrity checker
# Do not edit this file directly
wl = %s
# pretty printing options for the file
if __name__ == '__main__':
    for wl_file, checksum in wl.iteritems():
        print wl_file, 
        print '     ',
        print checksum
        """% (self.whitelist,))
        f.close()

