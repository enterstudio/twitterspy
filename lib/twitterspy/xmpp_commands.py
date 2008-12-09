import sys
import time
import types
import datetime
import re
import sre_constants
import urlparse

from twisted.words.xish import domish
from twisted.web import client
from twisted.internet import reactor
from sqlalchemy.orm import exc

import models

all_commands={}

class CountingFile(object):
    """A file-like object that just counts what's written to it."""
    def __init__(self):
        self.written=0
    def write(self, b):
        self.written += len(b)
    def close(self):
        pass
    def open(self):
        pass
    def read(self):
        return None

class BaseCommand(object):
    """Base class for command processors."""

    def __get_extended_help(self):
        if self.__extended_help:
            return self.__extended_help
        else:
            return self.help

    def __set_extended_help(self, v):
        self.__extended_help=v

    extended_help=property(__get_extended_help, __set_extended_help)

    def __init__(self, name, help=None, extended_help=None):
        self.name=name
        self.help=help
        self.extended_help=extended_help

    def __call__(self, user, prot, args, session):
        raise NotImplementedError()

    def is_a_url(self, u):
        try:
            parsed = urlparse.urlparse(str(u))
            return parsed.scheme in ['http', 'https'] and parsed.netloc
        except:
            return False

class ArgRequired(BaseCommand):

    def __call__(self, user, prot, args, session):
        if self.has_valid_args(args):
            self.process(user, prot, args, session)
        else:
            prot.send_plain(user.jid, "Arguments required for %s:\n%s"
                % (self.name, self.extended_help))

    def has_valid_args(self, args):
        return args

    def process(self, user, prot, args, session):
        raise NotImplementedError()

class StatusCommand(BaseCommand):

    def __init__(self):
        super(StatusCommand, self).__init__('status', 'Check your status.')

    def __call__(self, user, prot, args, session):
        rv=[]
        rv.append("Jid:  %s" % user.jid)
        rv.append("Jabber status:  %s" % user.status)
        rv.append("Twitterspy status:  %s"
            % {True: 'Active', False: 'Inactive'}[user.active])
        rv.append("You are currently tracking %d topics." % len(user.tracks))
        prot.send_plain(user.jid, "\n".join(rv))

class HelpCommand(BaseCommand):

    def __init__(self):
        super(HelpCommand, self).__init__('help', 'You need help.')

    def __call__(self, user, prot, args, session):
        rv=[]
        if args:
            c=all_commands.get(args.strip().lower(), None)
            if c:
                rv.append("Help for %s:\n" % c.name)
                rv.append(c.extended_help)
            else:
                rv.append("Unknown command %s." % args)
        else:
            for k in sorted(all_commands.keys()):
                rv.append('%s\t%s' % (k, all_commands[k].help))
        prot.send_plain(user.jid, "\n".join(rv))

class OnCommand(BaseCommand):
    def __init__(self):
        super(OnCommand, self).__init__('on', 'Enable tracks.')

    def __call__(self, user, prot, args, session):
        user.active=True
        prot.send_plain(user.jid, "Enabled tracks.")

class OffCommand(BaseCommand):
    def __init__(self):
        super(OffCommand, self).__init__('off', 'Disable tracks.')

    def __call__(self, user, prot, args, session):
        user.active=False
        prot.send_plain(user.jid, "Disabled tracks.")

for __t in (t for t in globals().values() if isinstance(type, type(t))):
    if BaseCommand in __t.__mro__:
        try:
            i = __t()
            all_commands[i.name] = i
        except TypeError:
            # Ignore abstract bases
            pass
