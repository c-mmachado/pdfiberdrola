# -*- coding: utf-8 -*-

# Python Imports
import json

from typing import AnyStr, Any

# Third-Party Imports

# Local Imports

# Constants


class JsonFormatMixin(object):
    """Representation strategies for an object.

    Strategy class designed to perform the basic representation operations on a
    python object by accessing and making use of the `__dict__` property
    contained in python objects. Uses all attributes present in an object to
    generate a string representation.
    """


    def __str__(self) -> AnyStr:
        """Return object string representation.

        Builds a string representation of this object.

        Returns
        -------
        AnyStr
            the string representation of self
        """
        return json.dumps({k: _jsonify(v) for k, v in self.__dict__.items()}, sort_keys = True, indent = 2, default=str)


    def __repr__(self) -> AnyStr:
        """Return object representation.

        Builds a representation of this object.

        Returns
        -------
        AnyStr
            the string representation of self
        """
        return str(self)


    def __unicode__(self) -> AnyStr:
        """Return object unicode string representation.

        Builds a unicode string representation of this object.

        Returns
        -------
        AnyStr
            the unicode string representation of self
        """
        return str(self)


class AttributeJsonFormatMixin(JsonFormatMixin):
    """Representation strategies for an object.

    Strategy class designed to perform the basic representation operations on a
    python object by accessing and making use of the `__dict__` property
    contained in python objects. Uses all public attributes present in an object
    to generate a string representation.
    """


    def __str__(self) -> AnyStr:
        return json.dumps({k: _jsonify(v) for k, v in self.__dict__.items() if not k.startswith('_')},
                          sort_keys = True,
                          indent = 2, 
                          default=str)


class PropertyJsonFormatMixin(JsonFormatMixin):
    """Representation strategies for an object.

    Strategy class designed to perform the basic representation operations on a
    python object by accessing and making use of the `__dict__` property
    contained in python classes. Uses all property decorated attributes to
    generate a string representation.
    """


    def __str__(self) -> AnyStr:
        properties = {}
        for kls in self.__class__.__mro__:
            properties.update({k: _jsonify(getattr(self, k))
                               for k, v in kls.__dict__.items() if isinstance(v, property)})
        return json.dumps(properties, sort_keys = True, indent = 2, default=str)


def _jsonify(obj: Any) -> Any:
    if obj is None:
        return None

    obj_str = str(obj)
    obj_str = obj_str[obj_str.index(':') + 1:] if obj_str.startswith('<class') and ':' in obj_str else obj_str
    try:
        return json.loads(obj_str)
    except Exception:
        return obj_str
