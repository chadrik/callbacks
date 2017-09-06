from __future__ import absolute_import, print_function

import logging

from .registry import Callbacks
from .events import Event, ReturnEvent, ExceptionEvent
from typing import *

T = TypeVar('T', bound=Callable)
CallbacksT = TypeVar('CallbacksT', bound=Callbacks)
EventT = TypeVar('EventT', bound='Event')

logger = logging.getLogger(__name__)


class SingleCallback(Callbacks[T]):
    event = Event[T]()


class AutoCallbacks(Callbacks[T]):
    """
    Once a function/method is decorated with this clas, callbacks can
    be registered to be run before or after the target function (or after the
    target function raises an exception).

    to register callbacks:
        <target>.on_call.add_callback(callback) -> id
        <target>.on_return.add_callback(callback) -> id
        <target>.on_exception.add_callback(callback) -> id
    where <target> is the function/method that was decorated.

    To remove a callback you use:
        <target>.remove_callback(id)

    To remove a callback from a specific event:
        <target>.on_call.remove_callback(id)
        <target>.on_return.remove_callback(id)
        <target>.on_exception.remove_callback(id)

    To remove all callbacks use:
        <target>.remove_callbacks()

    To print a list of callbacks use:
        <target>.list_callbacks()

    """

    on_call = Event[T]()
    on_return = ReturnEvent[T]()
    on_exception = ExceptionEvent[T]()

    def __call__(self, *args, **kwargs):
        logger.debug('self %s %s' % (self, self.target))

        self.on_call.emit(*args, **kwargs)
        try:
            target_result = self.target(*args, **kwargs)
        except Exception as e:
            target_result = self.on_exception.emit(e, *args, **kwargs)
        self.on_return.emit(target_result, *args, **kwargs)
        return target_result

    # -- wrappers, for backward compatibility

    def add_pre_callback(self, callback, priority=0.0, label=None,
                         takes_target_args=False):
        # type: (T, float, Optional[Hashable], bool) -> Hashable
        """
        Registers the callback to be called before the target.

        Parameters
        ----------
        callback : T
            The callback function that will be called before
            the target function is run.
        priority : float
            Number. Higher priority callbacks are run first,
            ties are broken by the order in which callbacks were added.
        label : Optional[Hashable]
            A name to call this callback, must be unique (and hashable)
            or None, if non-unique a RuntimeError will be raised.
            If None, a unique label will be automatically generated.
            NOTE: Callbacks can be removed using their label.
                  (see remove_callback)
        takes_target_args : bool
            If True, callback function will be passed the
            arguments and keyword arguments that are supplied to the
            target function.

        Returns
        -------
        Hashable
        """
        return self.on_call.add_callback(
            callback=callback, priority=priority, id=label,
            takes_target_args=takes_target_args)

    def add_post_callback(self, callback, priority=0.0, label=None,
                          takes_target_args=False,
                          takes_target_result=False):
        # type: (T, float, Optional[Hashable], bool, bool) -> Hashable
        """
            Registers the callback to be called after the target is called.

        Parameters
        ----------
        callback : T
            The callback function that will be called after
            the target is called.
        priority : float
            Higher priority callbacks are run first,
            ties are broken by the order in which callbacks were added.
        label : Optional[Hashable]
            A name to call this callback, must be unique (and hashable)
            or None, if non-unique a RuntimeError will be raised.
            If None, a unique label will be automatically generated.
            NOTE: Callbacks can be removed using their label.
                  (see remove_callback)
        takes_target_args : bool
            If True, callback function will be passed the
            arguments and keyword arguments that are supplied to the
            target function.
        takes_target_result : bool
            If True, callback will be passed, as
            its first argument, the value returned from calling the
            target function.

        Returns
        -------
        Hashable
        """
        return self.on_return.add_callback(
            callback=callback, priority=priority, id=label,
            takes_target_args=takes_target_args,
            takes_target_result=takes_target_result)

    # alias
    add_callback = add_post_callback

    def add_exception_callback(self, callback, priority=0.0, label=None,
                               takes_target_args=False,
                               handles_exception=False):
        # type: (T, float, Optional[Hashable], bool, bool) -> Hashable
        """
            Registers the callback to be called after the target raises an
        exception.  Exception callbacks are called in priority order and can
        handle the exception if they register with <handles_exception>.

        Parameters
        ----------
        callback : T
            The callback function that will be called after
            the target function raises an exception.
        priority : float
            Higher priority callbacks are run first,
            ties are broken by the order in which callbacks were added.
        label : Optional[Hashable]
            A name to call this callback, must be unique (and hashable)
            or None, if non-unique a RuntimeError will be raised.
            If None, a unique label will be automatically generated.
            NOTE: Callbacks can be removed using their label.
                  (see remove_callback)
        takes_target_args : bool
            If True, callback function will be passed the
            arguments and keyword arguments that are supplied to the
            target function.
        handles_exception : bool
            If True, callback will be passed (as
            its first argument) the exception raised by the target function
            or a higher priority exception_callback which raised an
            exception.  If True, this function is responsible for
            handling the exception or reraising it!  NOTE: If True and
            the exception has already been handled, this callback will
            not be called.

        Returns
        -------
        Hashable
        """
        return self.on_exception.add_callback(
            callback=callback, priority=priority, id=label,
            takes_target_args=takes_target_args,
            handles_exception=handles_exception)


@overload
def supports_callbacks():
    # type: () -> Type[AutoCallbacks]
    pass


@overload
def supports_callbacks(cb):
    # type: (Type[CallbacksT]) -> Type[CallbacksT]
    pass


@overload
def supports_callbacks(func):
    # type: (T) -> AutoCallbacks[T]
    pass


def supports_callbacks(type_or_target=AutoCallbacks):
    if (isinstance(type_or_target, type) and
            issubclass(type_or_target, Callbacks)):
        # @supports_callbacks()
        # def foo(...)
        return type_or_target
    elif callable(type_or_target):
        # @supports_callbacks
        # def foo(...)
        return AutoCallbacks(type_or_target)
    else:
        raise TypeError(type_or_target)
