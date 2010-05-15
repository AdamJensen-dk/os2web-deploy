#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Git checkout updating script.

Works together with a PHP script to update Git repositories based on pings
from github.com or similar git hosting services.

This is currently accomplished by way of the PHP script touch'ing files
when it receives a ping and this script looking for these pings via
inotify. This will be refactored to use named pipes instead when time permits.
"""

import logging
import logging.handlers
import os
import re
import socket
import stat
from subprocess import Popen, PIPE, STDOUT
from SocketServer import StreamRequestHandler, ThreadingUnixStreamServer

# Configure a little bit of logging so we can see what's going on.
HOME_PATH = os.path.abspath(os.path.expanduser('~'))
LOG_PATH = os.path.join(HOME_PATH, 'log')
SOCKET_FILENAME = '/tmp/gitte.sock'
INPUT_FILTER = re.compile('[^A-Za-z0-9_-]')

DIRNAMES = {
    'kkb': '/home/kkbdeploy/sites/kkb.dev.gnit.dk',
    'aakb': '/home/kkbdeploy/sites/aakb.dev.gnit.dk',
    'kolding': '/home/kkbdeploy/sites/kolding.dev.gnit.dk',
    'kbhlyd': '/home/kkbdeploy/sites/kbhlyd.dev.gnit.dk',
    'ding': ('/home/kkbdeploy/sites/ding6_api',
             '/home/kkbdeploy/sites/ding.dev.ting.dk',
             '/home/kkbdeploy/sites/ting012.dev.ting.dk'),
}

GIT_COMMANDS = (
    ('git', 'pull'),
    ('git', 'submodule', 'init'),
    ('git', 'submodule', 'update'),
)

class GitPingHandler(StreamRequestHandler):
    """
    Handles requests to the socket server.

    Recieves messages via socket from the PHP script that handles Github
    ping requests.
    """
    def handle(self):
        self.data = INPUT_FILTER.sub('', self.request.recv(256).strip())
        logger.info('Got message: %s' % self.data)

        if self.data in DIRNAMES:
            # Single dir for name, value is just a string.
            if isinstance(DIRNAMES[self.data], basestring):
                update_git_checkout(DIRNAMES[self.data])
            # If value is iterable, get each dirname and update it.
            elif hasattr(DIRNAMES[self.data], '__iter__'):
                for dirname in DIRNAMES[self.data]:
                    update_git_checkout(dirname)

        self.request.send('OK: %s' % self.data)


def configure_logging():
    """
    Set up a an instance of Python's standard logging utility.
    """
    logger = logging.getLogger('gitte')
    logger.setLevel(logging.INFO)

    if os.path.isdir(LOG_PATH):
        log_file = os.path.join(LOG_PATH, 'gitte.log')
        trfh = logging.handlers.TimedRotatingFileHandler(log_file, 'D', 1, 5)
        trfh.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        ))
        logger.addHandler(trfh)
    else:
        logger.error('Log dir does not exist: %s' % log_path)

    return logger

def update_git_checkout(dirname):
    """ Performs git update on given dirname """
    logger = logging.getLogger('gitte')
    for command in GIT_COMMANDS:
        proc = Popen(command, cwd=dirname, stdout=PIPE, stderr=STDOUT)
        message = proc.communicate()[0]

        if message:
            logger.info('%s: %s' % (dirname, message))

if __name__ == '__main__':
    logger = configure_logging()

    # Socket server creates its own socket file. Delete if it exists already.
    if os.path.exists(SOCKET_FILENAME):
        logger.warning('Unlinking existing socket: %s' % SOCKET_FILENAME)
        os.unlink(SOCKET_FILENAME)

    server = ThreadingUnixStreamServer(SOCKET_FILENAME, GitPingHandler)

    os.chmod(SOCKET_FILENAME, 0777)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        os.unlink(SOCKET_FILENAME)
        print "\nKeyboard interupt recieved, Gitte server stopping..."
