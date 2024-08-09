# -*- coding: utf-8 -*-

# Python Imports

# Third-Party Imports

# Local Imports

# Constants

if __name__ == "__main__":
    from sys import path
    from os.path import dirname, realpath
    from importlib import import_module
    
    # Ensures that the current directory is in the path so that module imports work
    # correctly when running the application
    _file: str = dirname(realpath(__file__))
    if _file not in path:
        path.append(_file)
    del _file
    
    import_module("app")