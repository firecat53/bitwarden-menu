"""Read, type and edit Bitwarden vault entries using dmenu or rofi

"""
from contextlib import closing
import multiprocessing
from multiprocessing.managers import BaseManager
import os
from os.path import exists, expanduser
import random
import socket
import string
from subprocess import call
import sys

import bwm
from bwm.bwm import DmenuRunner
from bwm.menu import dmenu_err


def find_free_port():
    """Find random free port to use for BaseManager server

    Returns: int Port

    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(('127.0.0.1', 0))  # pylint:disable=no-member
        return sock.getsockname()[1]  # pylint:disable=no-member


def random_str():
    """Generate random auth string for BaseManager

    Returns: string

    """
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(15))


def get_auth():
    """Generate and save port and authkey to ~/.cache/.bwm-auth

    Returns: int port, bytestring authkey

    """
    auth = bwm.configparser.ConfigParser()
    if not exists(bwm.AUTH_FILE):
        fdr = os.open(bwm.AUTH_FILE, os.O_WRONLY | os.O_CREAT, 0o600)
        with open(fdr, 'w', encoding=bwm.ENC) as a_file:
            auth.set('DEFAULT', 'port', str(find_free_port()))
            auth.set('DEFAULT', 'authkey', random_str())
            auth.write(a_file)
    try:
        auth.read(bwm.AUTH_FILE)
        port = auth.get('DEFAULT', 'port')
        authkey = auth.get('DEFAULT', 'authkey').encode()
    except (bwm.configparser.NoOptionError,
            bwm.configparser.MissingSectionHeaderError,
            bwm.configparser.ParsingError,
            multiprocessing.context.AuthenticationError):
        os.remove(bwm.AUTH_FILE)
        dmenu_err("Cache file was corrupted. Stopping all instances. Please try again")
        call(["pkill", "bwm"])  # Kill all prior instances as well
        return None, None
    return int(port), authkey


def client():
    """Define client connection to server BaseManager

    Returns: BaseManager object
    """
    port, auth = get_auth()
    mgr = BaseManager(address=('', port), authkey=auth)
    mgr.register('set_event')
    mgr.connect()
    return mgr


class Server(multiprocessing.Process):
    """Run BaseManager server to listen for dmenu calling events

    """
    def __init__(self):
        multiprocessing.Process.__init__(self)
        self.port, self.authkey = get_auth()
        self.start_flag = multiprocessing.Event()
        self.kill_flag = multiprocessing.Event()
        self.cache_time_expired = multiprocessing.Event()
        self.start_flag.set()

    def run(self):
        _ = self.server()
        self.kill_flag.wait()

    def server(self):
        """Set up BaseManager server

        """
        mgr = BaseManager(address=('127.0.0.1', self.port),
                          authkey=self.authkey)
        mgr.register('set_event', callable=self.start_flag.set)
        mgr.start()  # pylint: disable=consider-using-with
        return mgr


def run():
    """Main entrypoint. Start the background Manager and Dmenu runner processes.

    """
    server = Server()
    dmenu = DmenuRunner(server)
    dmenu.daemon = True
    server.start()
    dmenu.start()
    server.join()
    if exists(expanduser(bwm.AUTH_FILE)):
        os.remove(expanduser(bwm.AUTH_FILE))


def main():
    """CLI entrypoint

    """
    if len(sys.argv) > 1:
        print("See `man bwm` for help")
        sys.exit()
    try:
        manager = client()
        manager.set_event()  # pylint: disable=no-member
    except ConnectionRefusedError:
        run()


if __name__ == '__main__':
    main()

# vim: set et ts=4 sw=4 :
