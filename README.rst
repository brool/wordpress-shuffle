Setting Up
----------

Assuming that your blog is set up at http://www.yourblog.com (you can create an account at wordpress.com to test this out), all you'll need to do is::

    -- make a directory for the blog
    mkdir blog
    chdir blog

    -- download everything
    python wp.py --user=yourname --password=yourpass --url=http://www.yourblog.com/xmlrpc.php init
    (wait a bit)

    -- now set up so we don't have to specify --user, --password, and --url every time (optional)
    python wp.py --user=yourname --password=yourpass --url=http://www.yourblog.com/xmlrpc.php defaults
    -- you can skip specifying the password, and it'll prompt you when you run it 

The files are downloaded in the appropriate YYYY/MM directories, with the draft directory being used for all of your unpublished drafts.

Pages (whether draft or not) are stored in a directory named "pages."

All the drafts are stored in plain text, but you'll see some lines starting with periods -- these are various Wordpress variables that are associated with the file.  You can change them, as well;  for example, to change the title of the post, just change the line that begins with ".title". 

Seeing What's Different
-----------------------

You can use the status command to see differences between the local file system and your blog.

::

    python wp.py status

Note that only the most recent files are checked.  If you want to really check every single file for changes, do::

    python wp.py status all

You can also use the --diff command line option to see the differences between local and server::

    python wp.py --diff status all

Updating From The Blog
----------------------

If you've made changes through the web interface and you'd like to bring them down, you don't have to download everything again, but can instead just update.

::

    python wp.py pull

Again, only the most recent changes are brought down.  If you want to check every post on the blog, do::

    python wp.py pull all

Posting To The Blog
-------------------

If you've made changes to files and you'd like to post them back, do::

    python wp.py push

To push everything (and not just the most recent files), do::

    python wp.py push all

Note that push only changes those files that exist in both spots.  If you're adding a new post, use the "add" command.

Posting/Editing
---------------

If you'd like to add a new post, put it in the drafts or pages folder,
as appropriate, and then do::

    python wp.py add drafts/filename

Note that add can actually take existing posts, as well -- it just
forces an update of that one file, rather than running through all
changes like push.

Publishing
----------

To publish a file, just change the .post_status field from 'draft' to
'published'.  Note that doing this will cause a copy to move from the
drafts folder to the appropriate year/month.

Gotchas
-------

There are some gotchas due to the fact that the filename can change on you.  There are cases where the filename that will be brought down is different then the one that you send up:

- You post a file without a .title or .wp_slug line
- You post a file with a different file name than the slug that is generated (i.e., "my-first-draft" when the title is actually "my final draft")

Troubleshooting
---------------

You may experience some difficulties if your Wordpress installation is not generating proper XML responses. If this is the case, and you are getting errors like, "XML Parsing Error: XML or text declaration not at start of entity at line 3 col 0", then you may try the following patch to your wordpress /xmlrpc.php file:

Wrap the wp-load.php include in PHP output buffer.

      ob_start();
      include('./wp-load.php');
      ob_end_clean();

This will prevent any output from being rendered before the XML is sent in the response.



