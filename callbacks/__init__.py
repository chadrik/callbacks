"""
Register callbacks on functions using decorators.
"""

from .auto import supports_callbacks, AutoCallbacks, SingleCallback
from .events import Event, ReturnEvent, ExceptionEvent
from .registry import Callbacks

# aliases
auto = AutoCallbacks
event = SingleCallback

__version__ = '0.2.0'

