"""PoorSession self-contained cookie class.

:Classes:   NoCompress, PoorSession
:Functions: hidden
"""
from hashlib import sha512
from time import time
from pickle import dumps, loads
from base64 import b64decode, b64encode

import bz2
import logging as log

from http.cookies import SimpleCookie


def hidden(text, passwd):
    """(en|de)crypt text with sha hash of passwd via xor.

    Arguments:
        text : str
            raw data to (en|de)crypt. Could be str, or bytes
        passwd : str
            password
    """
    if isinstance(passwd, bytes):
        passwd = sha512(passwd).digest()
    else:
        passwd = sha512(passwd.encode("utf-8")).digest()
    passlen = len(passwd)

    # text must be bytes
    if isinstance(text, str):
        text = text.encode("utf-8")

    if isinstance(text, str):       # text is str, we are in python 2.x
        retval = ''
        for i in range(len(text)):
            retval += chr(ord(text[i]) ^ ord(passwd[i % passlen]))
    else:                           # text is bytes, we are in python 3.x
        retval = bytearray()
        for i in range(len(text)):
            retval.append(text[i] ^ passwd[i % passlen])

    return retval


class SessionError(RuntimeError):
    """Base Exception for Session"""


class NoCompress:
    """Fake compress class/module whith two static method for PoorSession.

    If compress parameter is None, this class is use.
    """

    @staticmethod
    def compress(data, compresslevel=0):
        """Get two params, data, and compresslevel. Method only return data."""
        return data

    @staticmethod
    def decompress(data):
        """Get one parameter data, which returns."""
        return data


class PoorSession:
    """Self-contained cookie with session data.

    You cat store or read data from object via PoorSession.data variable which
    must be dictionary. Data is stored to cookie by pickle dump, and next
    hidden with app.secret_key. So it must be set on Application object or with
    poor_SecretKey environment variable. Be careful with stored object. You can
    add object with little python trick:

    .. code:: python

        sess = PoorSession(req)

        sess.data['class'] = obj.__class__          # write to cookie
        sess.data['dict'] = obj.__dict__.copy()

        obj = sess.data['class']()                  # read from cookie
        obj.__dict__ = sess.data['dict'].copy()

    Or for beter solution, you can create export and import methods for you
    object like that:

    .. code:: python

        class Obj(object):
            def import(self, d):
                self.attr1 = d['attr1']
                self.attr2 = d['attr2']

            def export(self):
                d = {'attr1': self.attr1, 'attr2': self.attr2}
                return d

        obj = Obj()
        sess = PoorSession(req)

        sess.data['class'] = obj.__class__          # write to cookie
        sess.data['dict'] = obj.export()

        obj = sess.data['class']()                  # read from cookie
        obj.import(sess.data['dict'])
    """

    def __init__(self, req, expires=0, max_age=None, domain=False, path='/',
                 secure=False, same_site=False, compress=bz2, SID='SESSID'):
        """Constructor.

        Arguments:
            expires : int
                Cookie ``Expires`` time in seconds, if it 0, no expire is set
            max_age : int
                Cookie ``Max-Age`` attribute. If both expires and max-age are
                set, max_age has precedence.
            domain : str
                Cookie ``Host`` to which the cookie will be sent.
            path : str
                Cookie ``Path`` that must exist in the requested URL.
            secure : bool
                If ``Secure`` cookie attribute will be sent.
            same_site: str
                The ``SameSite`` attribute. When is set could be one of
                ``Strict|Lax|None``. By default attribute is not set which is
                ``Lax`` by browser.
            compress : compress module or class.
                Could be ``bz2``, ``gzip.zlib``, or any other, which have
                standard compress and decompress methods. Or it could be
                ``None`` to not use any compressing method.
            SID : str
                Cookie key name.
        """
        if req.secret_key is None:
            raise SessionError("poor_SecretKey is not set!")

        self.__secret_key = req.secret_key
        self.__SID = SID
        self.__expires = expires
        self.__max_age = max_age
        self.__domain = domain
        self.__path = path
        self.__secure = secure
        self.__same_site = same_site
        self.__cps = compress if compress is not None else NoCompress

        # data is session dictionary to store user data in cookie
        self.data = {}
        self.cookie = SimpleCookie()
        self.cookie[SID] = None

        raw = None

        if req.cookies and SID in req.cookies:
            raw = req.cookies[SID].value

        if raw:
            try:
                self.data = loads(hidden(self.__cps.decompress
                                         (b64decode(raw.encode())),
                                         self.__secret_key))
            except Exception as err:
                log.info(err.__repr__())
                raise SessionError("Bad session data.")

            if not isinstance(self.data, dict):
                raise SessionError("Cookie data is not dictionary!")

            if 'expires' in self.data and self.data['expires'] < int(time()):
                log.info('Session was expired, generating new.')
                self.data = {}

    def renew(self):
        """Renew cookie, in fact set expires to next time if it set."""
        if self.__expires:
            self.data['expires'] = int(time()) + self.__expires
            return

        if 'expires' in self.data:
            self.data.pop('expires')

    def write(self):
        """Store data to cookie value.

        This method is called automatically in header method.
        """
        raw = b64encode(self.__cps.compress(hidden(dumps(self.data),
                                                   self.__secret_key), 9))
        raw = raw if isinstance(raw, str) else raw.decode()
        self.cookie[self.__SID] = raw
        self.cookie[self.__SID]['HttpOnly'] = True

        if self.__domain:
            self.cookie[self.__SID]['Domain'] = self.__domain
        if self.__path:
            self.cookie[self.__SID]['path'] = self.__path
        if self.__secure:
            self.cookie[self.__SID]['Secure'] = True
        if self.__same_site:
            self.cookie[self.__SID]['SameSite'] = self.__same_site
        if self.__expires:
            self.data['expires'] = int(time()) + self.__expires
            self.cookie[self.__SID]['expires'] = self.__expires
        if self.__max_age is not None:
            self.data['expires'] = int(time()) + self.__max_age
            self.cookie[self.__SID]['Max-Age'] = self.__max_age

        return raw

    def destroy(self):
        """Destroy session. In fact, set cookie expires value to past (-1)."""
        self.data = {}
        self.data['expires'] = -1
        self.cookie[self.__SID]['expires'] = -1
        if self.__max_age is not None:
            self.cookie[self.__SID]['Max-Age'] = -1
        self.cookie[self.__SID]['HttpOnly'] = True
        if self.__secure:
            self.cookie[self.__SID]['Secure'] = True

    def header(self, headers=None):
        """Generate cookie headers and append it to headers if it set.

        Returns list of cookie header pairs.

        :headers:   Headers or Response object, which is used
                    to write header directly.
        """
        self.write()
        cookies = self.cookie.output().split('\r\n')
        retval = []
        for cookie in cookies:
            var = cookie[:10]   # Set-Cookie
            val = cookie[12:]   # SID=###; expires=###; Path=/
            retval.append((var, val))
            if headers:
                headers.add_header(var, val)
        return retval
