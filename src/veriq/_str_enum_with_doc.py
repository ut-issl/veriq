"""Module providing a base class for string enums with docstrings."""

from enum import StrEnum
from typing import Self


class StrEnumWithDoc(StrEnum):
    """Base class for string enums with docstrings.

    Implementation based on this article: https://guicommits.com/add-docstrings-python-enum-members/
    """

    def __new__(cls, value: str, doc: str = "") -> Self:
        """Create a new enum member with a docstring."""
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.__doc__ = doc
        return obj
