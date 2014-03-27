"""
Poor WSGI connector for Python

Current Contents:
   
    #!text
    * request - Headers, Request and FieldStorage classes, which
                is used for managing requests.

    * results - default result handlers of connector like: directory index,
                send_file, SERVER_RETURN, redirect, servers errors or debug
                output handler.

    * session - self-contained cookie based session class

    * state   - constants like http status code, log levels and method types

    * wsgi    - main application function, and functions for working with
                dispatch table
"""

from request import FieldStorage

from results import redirect, SERVER_RETURN

from state import __author__, __date__, __version__

from wsgi import application, app
