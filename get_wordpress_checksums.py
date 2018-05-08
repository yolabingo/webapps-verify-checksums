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

# ignore_dirs = ['.git', '.svn', 'wp-content']
# WP comes with preinstalled themes and plugins but we need to let plugins/themes scanners check those
ignore_dirs = ['.git', '.svn' 'twentyten', 'twentyeleven', 'twentytwelve', 'twentythirteen', 'twentyfourteen', 'twentyfifteen', 'twentysixteen', 'twentyseventeen', 'twentyeighteen', 'twentynineteen', 'twentytwenty', 'akismet']
ignore_files = ['wp-config.php',]
webapp_name = 'wordpress-core'

def get_wp_api_versions():
    '''
    Query api.wordpress.org for current releases
    '''
    wp_url = 'https://api.wordpress.org/core/version-check/1.7/'
    handler = urllib2.urlopen( urllib2.Request(wp_url) )
    if not handler.getcode() == 200:
        raise Exception('error retrieving ' + wp_url)
    version_data_json = handler.read()
    return json.JSONDecoder().decode(version_data_json)['offers']
  
def get_download_urls(version=False):
    '''
    Get download URLs for a specific requested WP version, or for 
    the few most current releases via api.wordpress.org
    '''
    download_files = {}
    try:
        archived_versions = [k for k in sums[webapp_name].keys()]
    except KeyError:
        sums[webapp_name] = {}
        archived_versions = sums
    if version:
        # get requested version
        url = 'https://downloads.wordpress.org/release/wordpress-%s.zip'% (version,)
        # sanity check should they change this URL
        try:
            handler = urllib2.urlopen( urllib2.Request(url) )
        except urllib2.HTTPError:
            print 'Unable to open URL ' + url
            sys.exit()
        if not handler.getcode() == 200:
            raise Exception('error retrieving ' + url)
        download_files = {version: url} 
    else:
        # get list of recent releases
        for v in get_wp_api_versions():
            version = v['version']
            if version not in archived_versions:
                download_files[version] = v['download']
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
            print 'Added md5 checksums for %s version %s to webapp_checksums.py'% (webapp_name, version,)

def listdir_fullpath(d):
    for (dirpath, dirnames, filenames) in os.walk(d):
        pass
    return [os.path.join(d, f) for f in os.listdir(d)] 

def get_md5sums(directory):
    strip_chars = len(directory) + 1
    s = {}
    # these are lingering on quite a few sites
    comment = '# files lingering from old WP versions #'
    empty_file_sums = [comment, '96137494913a1f730a592e8932af394e', 'fc6d4a63d1362e49feddcb621a9f0b00', 
			'32c101e865d8c2c2aaadeb5cc6c16f67', '862dec5c27142824a394bc6464928f48']
    backward_compat_sums = {
	'wp-app.php': 		empty_file_sums + ['7615cae3d7b9d250c77a7100d7f25643', '790ca6e3319be86f1feec84ce82b0d95',
				 '862582af648e46a11b125fbd6582885e', 'cf892337fc983cf52f0e4c4b8ca70a08',
				 'f9325a411fbbae3350efb5cc29a1b238'],
	'wp-atom.php':     	empty_file_sums + ['7ff0df5d421f07e0d289933fa61a2f15', '41ee2f11d9757ec2659052eed3173df0', 
				 '4c9918dd470acdbef6d9fde9e1e54491'],
    	'wp-commentsrss2.php': 	empty_file_sums + ['27fc5177624504c738c7acb24efb32ae', 'fc053ca6e39ab0d4a216fe86c6e77ca8', 
				 '96d5824afd7896c0913b9c43de4dd067'],
	'wp-feed.php':      empty_file_sums + ['5b29757ae79246933a5793b5bdfc5090', 'd6ab3ec9c37be35fce9706559a825bd3', 
			     'ec83d6f441482af4d1fae9cbb59df43e', 'f025f09a9970eb3c8fa01fbf4acc665c'],
        'wp-pass.php':      empty_file_sums + ['4765b38c6a2b3b17da080049489923ee', '9e71ca9b665afc1c4804b60a8cec4e50', 
			     'b2d13ddac2f77eaeb09717da09b21e53'],
        'wp-register.php':  empty_file_sums + ['847e389ea06211783efef2245948a9b6', '287dc5ab04cb97e1a45873f1c87525ca', 
			     'd09916236fec6752c45c52499d6e2afb', 'efab873ea26cfa56e6f4aa4c3eaa988b'],
	'wp-rdf.php':       empty_file_sums + ['efab873ea26cfa56e6f4aa4c3eaa988b', 'fe32d8c9f43141154b734c7bfd6049c8', 
			     '366997f14f51587e104becf290cea514', 'd41d8cd98f00b204e9800998ecf8427e',  
			     '287dc5ab04cb97e1a45873f1c87525ca'],
	'wp-rss.php':       empty_file_sums + ['afa3f623e58e064ee758281009ad0971', 'fed187a5047c2a2240204c9975d99582', 
			     '6e22f880b0db7beababe042e995cea43'],
	'wp-rss2.php':      empty_file_sums + ['8b44c1f3b0f7aab1f6ab2c11d15d9ae2', '2e0c91f0a744fb21cc0f422a6305fc64', 
			     'ec83d6f441482af4d1fae9cbb59df43e'],
        'wp-admin/js/utils.js':  empty_file_sums + ['284f0a2c317e3e094f08677e1b451c8a', '549df3fa634602b63688d98547c6f452',
                                  'e102613271d205d357aa317ee6c8f32b'],
        'wp-includes/js/tinymce/utils/form_utils.js':  empty_file_sums + ['13541f120c5fa567e36f8e10d6ddcfed', 
                                                        '337d7e2efe224c1c7da72d40b612d0a6', 
                                                        'a32d1bbc44057b7dd0d2776ba2826b7c',
                                                        'e33f3bde78ed04cd3039cd41c669f0c7',
                                                        'f9c61354383f5a50a9a77b902dfdae7f'],
        'wp-includes/js/utils.js': empty_file_sums + ['01b7f89601bfa36ffee09f056f2cc38a',
                                    'a5f4880c9cca30561e9290f0dafda128', 
                                    'b59e4faadb8e122faa031d99f1966ea4'],
        'wp-includes/class-wp-atom-server.php': empty_file_sums + ['3b5db0512c358ecdf1b0200cb750bde9',
                                                 'e6e3267096e302682bb221b33939a48f'],
	'wp-content/advanced-cache.php': empty_file_sums + ['567c4d364fb682c764b37112a9197f05'],
	'wp-content/plugins/index.php': empty_file_sums,
	'wp-content/themes/index.php':  empty_file_sums,
	'wp-content/index.php':  empty_file_sums,
	'wp-admin/index.php':    empty_file_sums,
	# this thing is such a pain
	'wp-content/plugins/hello.php':     empty_file_sums + ['29e34b280a057483545b48e1d3770760', '46786b52f0e2b975500800dae922b038'],
	'index.php':  empty_file_sums + ['96137494913a1f730a592e8932af394e']
    }

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
            s[f] = backward_compat_sums[f] + [s[f]]
        except KeyError:
            s[f] = backward_compat_sums[f]
    return s

def update():
    '''
    Create md5 checksums for any wp tarball or zip files found
    '''
    wp_archive = re.compile( r'wordpress-([0-9RC.-]+)\.(tar\.gz|zip)$')
    wps = [w for w in (listdir_fullpath('.')) if re.search(wp_archive, w)]
    for wp in wps:
        call(['rm', '-rf', 'wordpress']) == 0
        wp_version =  re.search(wp_archive, wp).group(1)
        archive_type =  re.search(wp_archive, wp).group(2)
        if archive_type == 'tar.gz':
            unpack = ['tar', 'xf', wp]
        elif archive_type == 'zip':
            unpack = ['unzip', '-qq',  wp]
        else:
            raise Exception('This should not happen')
        assert call(unpack) == 0
        sums.setdefault(webapp_name, {})
        sums[webapp_name][wp_version] = {}
        sums[webapp_name][wp_version] = get_md5sums('wordpress')
        assert call(['rm', '-rf', 'wordpress']) == 0

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
Download WP source from api.wordpress.org and generate md5 checksums for each file,
to be used by our webapp integrity checker.

With no arguments, just fetch the most current few versions available.

Or specify specific versions needed.
    '''
    parser = OptionParser()
    parser = OptionParser(usage=usage)
    parser.add_option("-k", "--keep-files", dest="keep_files", action="store_true", default=False,
                      help="Keep WP archive files - default is to remove them after use")
    (options, args) = parser.parse_args()
    if len(args):
        for version in args:
            add_checksums(version, options.keep_files)
    else:
        add_checksums(None, options.keep_files)
