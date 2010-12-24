#!/usr/bin/env python
import getpass
import os.path
import optparse
import pyperclip
import signal
import subprocess
import sys
import yaml


VERSION = '%prog 0.1 alpha'
DATABASE_PATH = '~/.passwords.asc'

# install silent Ctrl-C handler
def handle_sigint(*_):
  print
  sys.exit(1)
signal.signal(signal.SIGINT, handle_sigint)

# parse command-line options
parser = optparse.OptionParser(usage='Usage: %prog [options] [query]', version=VERSION)
parser.add_option('-d', '--display', action='store_true', help='display passwords on console (as opposed to copying them to the clipboard)')
opts, args = parser.parse_args()

# verify that database file is present
database_path = os.path.expanduser(DATABASE_PATH)
if not os.path.exists(database_path):
  print 'Error: KeePass database not found at %s.' % DATABASE_PATH
  sys.exit(1)

# read master password and open database
master_password = getpass.getpass()
popen = subprocess.Popen("gpg -qd --no-tty --passphrase '%s' '%s'" % (master_password,database_path), shell=True, stdout=subprocess.PIPE)
output,_ = popen.communicate()
if popen.returncode:
  sys.exit(1)

# parse YAML
root_node = yaml.load(output)

# create list of entries sorted by their canonical path
def make_canonical_path(path):
  return path.replace(' ', '_').lower()

entries = []

def collect_entry(node, path):
  if type(node) != dict:
    node = {'P':node}
  else:
    if node.has_key('U') and type(node['U']) == int:
      node['U'] = str(node['U'])
  node['canonical_path'] = make_canonical_path(path)
  entries.append(node)

def collect_entries(node, path):
  if type(node) == list:
    for n in node:
      collect_entry(n, path)
  elif type(node) == dict:
    if node.has_key('P'):
      collect_entry(node, path)
    else:
      for (key,value) in node.iteritems():
        collect_entries(value, path + '.' + key if path else key)
  else:
    collect_entry(node, path)

collect_entries(root_node, '')

entries = sorted(entries, key=lambda e: e['canonical_path'])

# perform query
if args and args[0].find(':') != -1:
  query_path, query_user = [make_canonical_path(q) for q in args[0].split(':')]
elif args:
  query_path, query_user = make_canonical_path(args[0]), ''
else:
  query_path, query_user = '', ''
results = [e for e in entries if e['canonical_path'].find(query_path) != -1 and ((not query_user) or (e.has_key('U') and e['U'].find(query_user) != -1))]

# print results
if len(results) == 0:
  print 'no record found'
  sys.exit(0)

for e in results:
  # mark up result
  title = e['canonical_path']
  user = e['U'] if e.has_key('U') else ''
  if query_path:
    title = ('\x1b[33m' + query_path + '\x1b[0m').join(title.split(query_path))
  if query_user:
    user = ('\x1b[33m' + query_user + '\x1b[0m').join(user.split(query_user))
  if user:
    print '%s: %s' % (title,user),
  else:
    print title,

  # display password or copy to clipboard (if only match)
  if opts.display:
    print '| \x1b[31m%s\x1b[0m' % e['P'],
  elif len(results) == 1:
    pyperclip.setcb(e['P'])
    print '| \x1b[32mpassword copied to clipboard\x1b[0m',

  # display url and notes
  if e.has_key('L') and len(results) > 1:
    print '| %s' % e['L'],
  if e.has_key('N') and len(results) > 1:
    print '| ...',
  print

  if e.has_key('L') and len(results) == 1:
    print '  %s' % e['L']
  if e.has_key('N') and len(results) == 1:
    print '  %s' % e['N']