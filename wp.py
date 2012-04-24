#!/usr/bin/python

# Copyright (c) 2011, tim at brool period com
# Github: github.com/brool/git-wordpress
# Licensed under GPL version 3 -- see http://www.gnu.org/copyleft/gpl.txt for information

# todo: add page support?
# todo: fix slugify (make it match Wordpress's algorithm exactly)

"""wordpress-shuffle -- easy maintenance of WordPress."""

import sys
import os
import os.path
import getopt
import re
import xmlrpclib
try:
    import hashlib as md5
except Exception, e:
    import md5
import functools
import subprocess
import getpass
import tempfile
import itertools

# c.f. http://docs.python.org/library/itertools.html
def roundrobin(*iterables):
    "roundrobin('ABC', 'D', 'EF') --> A D E B F C"
    # Recipe credited to George Sakkis
    pending = len(iterables)
    nexts = itertools.cycle(iter(it).next for it in iterables)
    while pending:
        try:
            for next in nexts:
                yield next()
        except StopIteration:
            pending -= 1
            nexts = itertools.cycle(itertools.islice(nexts, pending))

class BlogXMLRPC:
    """BlogXMLRPC.  Wrapper for the XML/RPC calls to the blog."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.xrpc = xmlrpclib.ServerProxy(self.url)
        self.get_recent = functools.partial(self.xrpc.metaWeblog.getRecentPosts, 1, self.user, self.password, 5)
        self.new_post = functools.partial(self.xrpc.metaWeblog.newPost, 1, self.user, self.password)
    def get_all(self):
        posts = self.xrpc.metaWeblog.getRecentPosts(1, self.user, self.password, 20)
        pages = self.xrpc.wp.getPages(1, self.user, self.password, 20)
        for p in roundrobin(posts, pages):
            yield p
        for post in self.xrpc.wp.getPages(1, self.user, self.password, 32767)[20:]:
            yield post
        for post in self.xrpc.metaWeblog.getRecentPosts(1, self.user, self.password, 32767)[20:]:
            yield post
    def get_post(self, post_id): return self.xrpc.metaWeblog.getPost(post_id, self.user, self.password)
    def edit_post(self, post_id, post): return self.xrpc.metaWeblog.editPost(post_id, self.user, self.password, post, True)
    def get_page(self, page_id): return self.xrpc.wp.getPage(1, page_id, self.user, self.password)
    def edit_page(self, page_id, page): return self.xrpc.wp.editPage(1, page_id, self.user, self.password, page, True)
    def new_page(self, page): return self.xrpc.wp.newPage(1, self.user, self.password, page, True)
    def create(self, p):
        if p.is_page():
            return self.new_page(p.as_dict())
        else:
            return self.new_post(p.as_dict())
    def edit(self, p):
        fn = p.is_page() and self.edit_page or self.edit_post
        return fn(p.id(), p.as_dict())
        # return self.edit_post(p.id(), p.as_dict())

class Post:
    """Post.  A set of key => value pairs."""

    # fields that are ignored when comparing signatures
    ignore_fields = set([ 'custom_fields', 'sticky', 'date_created_gmt' ])

    # fields that need to be handled special when rendering
    special_fields = set([ 'description', 'mt_text_more' ])

    # fields that should not be edited locally
    read_only_fields = set([ 'dateCreated', 'date_created_gmt' ])

    def __init__(self, keys=None):
        self.post = keys and dict(keys) or None

        # make sure all values are in utf-8
        if self.post:
            for k in self.post:
                if isinstance(self.post[k], unicode):
                    self.post[k] = self.post[k].encode('utf8', 'replace')
        
    def __str__(self):
        buffer = []
        lst = self.post.keys()
        lst.sort()
        for key in lst:
            if key not in Post.ignore_fields and key not in Post.special_fields:
                buffer.append ( ".%s %s" % (key, self.post[key] ))
        buffer.append(self.post['description'].rstrip()) 
        if self.post.get('mt_text_more', ''):
            buffer.append('<!--more-->')
            buffer.append(self.post['mt_text_more'].lstrip())
        return '\n'.join(buffer)

    def parse(self, fname):
        is_page = os.path.split(os.path.abspath(fname))[0].endswith('/pages')

        self.post = {}

        dots = True
        description = []
        for line in file(fname, 'rt'):
            line = line.rstrip(os.linesep)
            if dots and line and line[0] == '.':
                pos = line.find(' ')
                if pos != -1:
                    key = line[1:pos]
                    if key not in Post.ignore_fields:
                        self.post[key] = line[pos+1:]
                else:
                    if key not in Post.ignore_fields:
                        self.post[line[1:]] = ''
            else:
                description.append(line)
                dots = False

        if is_page and 'page_status' not in self.post:
            self.post['page_status'] = 'draft'

        self.post['description'] = (os.linesep).join(description)
        return self

    def as_dict(self):
        d = dict(self.post)
        for key in Post.read_only_fields: 
            if key in d: del d[key]
        return d

    # Somewhat close to formatting.php/sanitize_title_with_dashes but without the accent handling
    @staticmethod
    def slugify(inStr):
        slug = re.sub(r'<.*?>', '', inStr)
        slug = re.sub(r'(%[a-fA-F0-9]{2})', '---\1---', slug)
        slug = re.sub(r'%', '', slug)
        slug = re.sub(r'---(%[a-fA-F0-9]{2})---', '\1', slug)
        # should remove accents here
        slug = slug.lower()
        slug = re.sub(r'&.+?;', '', slug)
        slug = re.sub(r'[^%a-z0-9 _-]', '', slug)
        slug = re.sub(r'\s+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        slug = slug.strip('-')

        return slug

    def filename(self):
        fname = self.post.get('wp_slug') or Post.slugify(self.post['title']) or str(self.post['postid'])
        created = str(self.post['dateCreated'])
        if 'page_id' in self.post:
            return os.path.join('pages', fname)
        elif self.post.get('post_status', 'draft') == 'draft':
            return os.path.join('draft', fname)
        else:
            return os.path.join(created[0:4], created[4:6], fname)

    def id(self):
        return int(self.post.get('postid', 0)) or int(self.post.get('page_id', 0))

    def signature(self):
        return md5.md5(str(self).strip()).digest()

    def write(self, writeTo=None):
        try:
            (dir, filename) = os.path.split(writeTo or self.filename())
            if not os.path.exists(dir): os.makedirs(dir)
            file(writeTo or self.filename(), 'wt').write(str(self))
        except Exception, e:
            print "wp:", e
            pass

    def is_page(self):
        return 'page_status' in self.post

def get_changed_files(basedir, xml, maxUnchanged=5):
    """Compare the local file system with the blog to see what files have changed.
    Check blog entries until finding maxUnchanged unmodified entries."""

    created = []
    changed = []

    unchanged = 0
    for post in xml.get_all():
        xml_post = Post(keys=post)
        fname = os.path.join(basedir, xml_post.filename())
        if os.path.exists(fname):
            local_post = Post().parse(fname)
            if xml_post.signature() != local_post.signature():
                changed.append(xml_post)
            else:
                unchanged += 1
                if unchanged > maxUnchanged: break
        else:
            created.append(xml_post)

    return (created, changed)

def download_files(xml):
    """Download all files for the given blog into the current directory."""

    for post in xml.get_all():
        p = Post(keys=post)
        print p.filename()
        if not os.path.exists(p.filename()):
            p.write()
        else:
            print "skipping %s, file in way" % p.filename()

def up_until(fn):
    """Walks up the directory tree until a function that takes a path name returns True."""
    curdir = os.getcwd()
    while True:
        if fn(curdir): return curdir
        newdir = os.path.normpath(os.path.join(curdir, os.path.pardir))
        if (newdir == curdir): return False
        curdir = newdir

if __name__ == "__main__":
    (options, args) = getopt.getopt(sys.argv[1:], "", [ 'diff', 'url=', 'user=', 'password=', 'local' ])
    options = dict(options)

    if len(args) == 0 or args[0] not in ['defaults', 'init', 'status', 'push', 'pull', 'add']:
        print "usage: wp [command]"
        print "where command is:"
        print "    init     -- download everything"
        print "    defaults -- write the defaults for --url, --user, and --password"
        print "    status   -- compare local filesystem vs. blog"
        print "    pull     -- bring down changes to local filesystem"
        print "    push     -- push changes back to the blog"
        print "    add      -- post articles to blog"
        print 
        sys.exit()

    basedir = os.getcwd()

    defaults = {}
    if args[0] != 'defaults':
        try:
            defaults = eval(file(os.path.join(basedir, '.defaults'), 'rt').read())
        except Exception, e:
            pass

    url = defaults.get('url', options.get('--url', None))
    user = defaults.get('user', options.get('--user', None))
    password = defaults.get('password', options.get('--password', None))

    if not url or not user:
        print "wp: need --url, --user"
        sys.exit(1)

    # need to handle defaults here so that password can be optional
    if args[0] == 'defaults':
        defaults = { 'url': url, 'user': user }
        if password: defaults['password'] = password
        file(os.path.join(basedir, '.defaults'), 'wt').write(str(defaults))
        print "wp: defaults written."
        sys.exit(0)

    if not password:
        password = getpass.getpass()

    xml = BlogXMLRPC(url=url, user=user, password=password)

    if args[0] == 'init':
        download_files(xml)

        # create an empty .defaults file to mark the base directory
        if not os.path.exists('.defaults'): file('.defaults', 'wt').write('')
        
    elif args[0] == 'status':
        numToCheck = 5
        if len(args) > 1:
            numToCheck = int(args[1]) if args[1] != 'all' else sys.maxint
        (created, changed) = get_changed_files(basedir, xml, maxUnchanged=numToCheck)

        for p in created:
            print "new on server: %s" % p.filename()
            if '--diff' in options:
                tfn = mktemp()
                p.write(tfn)
                os.system('diff %s %s' % (tfn, p.filename()))
        for p in changed:
            print "differ: %s" % p.filename()
            if '--diff' in options:
                tfn = tempfile.mktemp()
                p.write(tfn)
                os.system('diff %s %s' % (tfn, p.filename()))

    elif args[0] == 'push':
        numToCheck = 5
        if len(args) > 1:
            numToCheck = int(args[1]) if args[1] != 'all' else sys.maxint
        (created, changed) = get_changed_files(basedir, xml, maxUnchanged=numToCheck)

        for xml_post in changed:
            p = Post().parse(os.path.join(basedir, xml_post.filename()))
            xml.edit(p)
            print "local -> server: %s" % xml_post.filename()

    elif args[0] == 'pull': 
        numToCheck = 5
        if len(args) > 1:
            numToCheck = int(args[1]) if args[1] != 'all' else sys.maxint
        (created, changed) = get_changed_files(basedir, xml, maxUnchanged=numToCheck)
        
        for xml_post in created + changed:
            xml_post.write( os.path.join(basedir, xml_post.filename()) )
            print "server -> local: %s" % xml_post.filename()

    elif args[0] == 'add':
        for fname in args[1:]:
            try:
                p = Post().parse(fname)
                if p.id():
                    xml.edit(p)
                    print "edited on server: %s" % fname
                else:
                    post_id = xml.create( p )

                    # since it's a new post, get it back again and write it out
                    if p.is_page():
                        np = Post(keys = xml.get_page( post_id ))
                    else:
                        np = Post(keys = xml.get_post( post_id ))
                    newname = os.path.join( basedir, np.filename() )
                    np.write(newname)
                    print "posted: %s -> %s" % (fname, np.filename())
            except IOError:
                print "Couldn't open %s, continuing." % fname
            except Exception, e:
                print "wp:", e
                sys.exit(1)
