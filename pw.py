#!/usr/bin/env python
from collections import namedtuple
import os
import optparse
import signal
import subprocess
import sys
import blessings
import yaml

try:
  import xerox
except ImportError:
  xerox = False

def main():
  VERSION = '%prog 0.3.0'
  DATABASE_PATH = os.path.join('~', '.passwords.yaml.asc')
  T = blessings.Terminal()

  # install silent Ctrl-C handler
  def handle_sigint(*_):
    print
    sys.exit(1)
  signal.signal(signal.SIGINT, handle_sigint)

  # color wrappers
  color_match = T.bold_yellow
  color_password = T.bold_red
  color_success = T.bold_reverse_green

  # parse command-line options
  parser = optparse.OptionParser(usage='Usage: %prog [options] [[userquery@]pathquery]', version=VERSION)
  parser.add_option('-E', '--echo', default=bool(xerox), action='store_true', help='echo passwords on console (default, if xerox unavailable)')
  parser.add_option('-s', '--strict', action='store_true', help='fail if password should be copied to clipboard but more than one result has been found')
  opts, args = parser.parse_args()

  # verify that database file is present
  database_path = os.path.expanduser(DATABASE_PATH)
  if not os.path.exists(database_path):
    print 'Error: Password safe not found at %s.' % database_path
    sys.exit(-1)

  # read master password and open database
  popen = subprocess.Popen(["gpg", "--use-agent", "--no-tty", "-qd", database_path], stdout=subprocess.PIPE)
  output,_ = popen.communicate()
  if popen.returncode:
    sys.exit(-1)

  # parse YAML
  root_node = yaml.load(output)

  # create list of entries
  Entry = namedtuple('Entry', ['normalized_path', 'user', 'password', 'link', 'notes'])
  entries = []

  def normalize_path(path):
    return path.replace(' ', '_').lower()

  def collect_entry(node, path):
    # expand password-only nodes
    if type(node) != dict:
      node = {'P': node}

    # add entry
    entry = Entry(
      normalized_path=normalize_path(path),
      user=unicode(node.get('U', None)),
      password=str(node.get('P', '')),
      link=node.get('L', None),
      notes=node.get('N', None)
    )
    entries.append(entry)

  def collect_entries(node, path):
    # list of accounts for the same path?
    if type(node) == list:
      for n in node:
        collect_entry(n, path)
    elif type(node) == dict:
      # account or subtree?
      if node.has_key('P'):
        collect_entry(node, path)
      else:
        for (key,value) in node.iteritems():
          collect_entries(value, path + '.' + key if path else key)
    else:
      collect_entry(node, path)

  collect_entries(root_node, '')

  # sort entries according to normalized path (stability of sorted() ensures that the order of accounts for a given path remains untouched)
  entries = sorted(entries, key=lambda e: e.normalized_path)

  # perform query
  if args and args[0].find('@') != -1:
    query_user, query_path = map(normalize_path, args[0].split('@'))
  elif args:
    query_user, query_path = '', normalize_path(args[0])
  else:
    query_user, query_path = '', ''
  results = [e for e in entries if e.normalized_path.find(query_path) != -1 and ((not query_user) or (e.user and e.user.find(query_user) != -1))]

  # print results
  if len(results) == 0:
    print 'no record found'
    sys.exit(-2)

  if len(results) > 1 and not opts.echo and opts.strict:
    print 'multiple records found'
    sys.exit(-3)

  for idx, entry in enumerate(results):
    # mark up result
    path = entry.normalized_path
    user = entry.user if entry.user else ''
    if query_path:
      path = color_match(query_path).join(path.split(query_path))
    if query_user:
      user = color_match(query_user).join(user.split(query_user))
    if user:
      print '%s: %s' % (path,user),
    else:
      print path,

    # only result?
    if len(results) == 1:
      # display entry in expanded mode
      print
      if not xerox or opts.echo:
        print '  ', color_password(entry.password)
      else:
        xerox.copy(entry.password)
        print '  ', color_success('*** PASSWORD COPIED TO CLIPBOARD ***')
      if entry.link:
        print '  ', entry.link
      if entry.notes:
        print '  ', entry.notes
    else:
      # otherwise abbreviate results
      if not xerox or opts.echo:
        print '|', color_password(entry.password),
      elif xerox and idx == 0:
        xerox.copy(entry.password)
        print color_success('*** PASSWORD COPIED TO CLIPBOARD ***'),
      if entry.link or entry.notes:
        print '[...]',
      print