# -*- coding: utf-8 -*-

# Python Imports
from collections.abc import Sequence
from typing import Any, NoReturn, Self, final

# Third-Party Imports

# Local Imports

# Constants


class Final(type):
    """
    Metaclass used to prevent inheritance.

    This metaclass is used to prevent inheritance of classes marked as final.

    Parameters
    ----------
    type : type
        the type to extend
    """

    def __new__(*args, **kwargs) -> Self | NoReturn:
        """
        Creates a new class instance.

        This method is used to create a new class instance and prevent inheritance of classes marked as final.

        Parameters
        ----------
        args : Tuple
            the arguments required to create a new class instance.
        kwargs : Dict
            the keyword arguments to pass to the new class instance

        Returns
        -------
        Self | NoReturn
            the new class instance or raises an exception if the class is marked as final
        """

        def is_final(cls: type) -> bool:
            for b in cls.__bases__:
                if b == Final:
                    return True
                if b.__bases__:
                    return is_final(b)
            return False

        if args and isinstance(args[0], type):
            for b in args[0].__bases__:
                if is_final(b):
                    raise TypeError(f"Type '{b.__name__}' is marked as a final type")
            return type.__new__(
                args[0],
                args[0].__name__,
                args[0].__bases__,
                dict(args[0].__dict__),
                *args,
                **kwargs,
            )
        raise TypeError(f"Unable to create a new class instance from '{args}'")


@final
class TypeUtils(Final):
    """
    Utility class for type checking and manipulation.

    This class provides a set of static methods for type checking and manipulation.

    Attributes
    ----------
    Final : type
        a metaclass used to prevent inheritance

    Methods
    -------
    is_iterable(obj: Any) -> bool
        Checks if an object is iterable
    """

    @staticmethod
    def is_iterable(obj: Any) -> bool:
        """
        Checks if an object is iterable.

        Tests whether the given object has an `__iter__` method and is not a string.

        Parameters
        ----------
        obj : Any
            the object to test

        Returns
        -------
        bool
            whether the object is iterable
        """

        if not obj and obj != []:
            return False
        return hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes))

    @staticmethod
    def is_callable(obj: Any) -> bool:
        """
        Checks if an object is callable.

        Tests whether the given object has a `__call__` method.

        Parameters
        ----------
        obj : Any
            the object to test

        Returns
        -------
        bool
            whether the object is callable
        """

        return hasattr(obj, "__call__")
