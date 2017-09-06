from __future__ import absolute_import, print_function

import sys
import types
import operator
from collections import OrderedDict

from typing import *

EventT = TypeVar('EventT', bound='Event')
HashableT = TypeVar('HashableT', bound=Hashable)
CallableT = TypeVar('CallableT', bound=Callable)
Options = Dict[str, Any]
Entry = NamedTuple('Entry', [
    ('function', Callable),
    ('priority', float),
    ('options', Options)
])


def _merge_options(default_options, sparse_options):
    # type: (Dict, Mapping) -> Dict
    invalid = set(sparse_options.keys()).difference(default_options.keys())
    if invalid:
        raise RuntimeError("Invalid option(s): %s. Please provide one of %s" %
                           (invalid, default_options.keys()))
    result = default_options.copy()
    for key, value in sparse_options.items():
        if value is not None:
            result[key] = value
    return result


class Event(Generic[CallableT]):
    """
    Holds a set of callbacks registered using `add_callback()` and handles
    executing them when `emit()` is called.
    """
    cls_counter = 0  # type: ClassVar[int]

    options = {
        'pass_args': True,
    }  # type: Options

    def __init__(self, name=None, options=None, target_name=None):
        # type: (Optional[str], Optional[Options], Optional[str]) -> None
        """
        Parameters
        ----------
        name : str
        target_name : Optional[str]
        options : Options
            Default options for the event.  Can be overridden per-callback
            via add_callback()
        """
        self.parent = None  # type: Event
        self.counter = None
        self.target_name = target_name
        self.callbacks = None  # type: OrderedDict[Hashable, Entry]
        if target_name is None:
            # class-level instantiation
            Event.cls_counter += 1
            self.counter = Event.cls_counter
        else:
            self._initialize()
        self.name = name

        self.options = _merge_options(type(self).options, options or {})

    def _initialize(self):
        # mapping of id to callback info dict
        self.callbacks = OrderedDict()

    def copy(self, include_callbacks=False, target_name=None):
        # type: (EventT, bool, Optional[str]) -> EventT
        e = self.__class__(self.name, self.options,
                           target_name or self.target_name)
        e.parent = self.parent
        e.counter = self.counter
        if include_callbacks:
            e.callbacks = self.callbacks.copy()
        return e

    def parents(self):
        # type: () -> List[Event]
        """
        Returns
        -------
        List[Event]
        """
        parents = []
        p = self.parent
        while p:
            parents.append(p)
            p = p.parent
        return parents

    @staticmethod
    def _callback_id(target):
        # type: (CallableT) -> Union[int, Tuple[int, int]]
        """
        Given a listener object, return the key that would be used to identify
        it for the purposes of event registration.

        Parameters
        ----------
        target : CallableT

        Returns
        -------
        Union[int, Tuple[int, int]]
        """
        if isinstance(target, types.MethodType):
            if sys.version_info[0] >= 3:
                return id(target.__self__), id(target.__func__)
            else:
                return id(target.im_self), id(target.im_func)
        return id(target)

    def _iter_callbacks(self):
        # type: () -> Iterator[Tuple[Hashable, Entry]]
        """
        Iterate over callbacks in order of priority.

        Returns
        -------
        Iterator[Tuple[Hashable, Entry]]
            (id, entry)
        """
        # consider all parents when ordering based on priority
        parents = self.parents()
        callbacks = []  # type: List[Tuple[Tuple[float, int], Hashable, Entry]]
        for depth, event in enumerate([self] + parents):
            for id, entry in event.callbacks.items():
                callbacks.append(((entry.priority, depth), id, entry))
        callbacks.sort(key=operator.itemgetter(0), reverse=True)

        for _, id, entry in callbacks:
            yield (id, entry)

    def _add_callback(self, callback, priority, id, options):
        try:
            priority = float(priority)
        except ValueError:
            raise ValueError('Priority could not be cast into a float.')

        if id is None:
            id = self._callback_id(callback)

        if id in self.callbacks.keys():
            raise RuntimeError('Callbacks with id="%s" already registered.'
                               % id)

        entry = Entry(
            function=callback,
            priority=priority,
            options=_merge_options(self.options, options or {})
        )
        self.callbacks[id] = entry
        return id

    def add_callback(self, callback, priority=0.0, id=None,
                     takes_target_args=None):
        # type: (CallableT, float, Optional[Hashable], bool) -> Hashable
        """
        Registers the callback.

        Parameters
        ----------
        callback : CallableT
            The callback function that will be called
            before the target function is run.
        priority : float
            Higher priority callbacks are run first,
            ties are broken by the order in which callbacks were added.
        id : Optional[Hashable]
            A name to call this callback, must be unique (and hashable)
            or None, if non-unique a RuntimeError will be raised.
            If None, a unique id will be automatically generated.
            NOTE: Callbacks can be removed using their id or the original
            callable. (see remove_callback)
        takes_target_args : bool
            If True, callback function will be passed the
            arguments and keyword arguments that are supplied to the
            target function. If None, defaults to the event's default.

        Returns
        -------
        Hashable
        """
        return self._add_callback(
            callback=callback, priority=priority, id=id,
            options={'pass_args': takes_target_args})

    def remove_callback(self, id):
        # type: (Hashable) -> None
        """
        Unregisters the callback.

        Parameters
        ----------
        id: Hashable
            The name of the callback (as supplied to add_callback),
            the id returned by add_callback, or the callback itself.

        Raises
        ------
        RuntimeError
            if the id is not valid.

        Returns
        -------
        None
        """
        if callable(id):
            # convert the original callable to an id
            id = self._callback_id(id)

        if id not in self.callbacks:
            raise RuntimeError(
                '%s: No callback with id "%s" attached to function "%s"' %
                (self.name, id, self.target_name))

        del self.callbacks[id]

    def remove_callbacks(self, ids=None):
        # type: (Optional[List[Hashable]]) -> None
        """
        Unregisters callback(s) from the target.

        Parameters
        ----------
        ids : Optional[List[Hashable]]
            A list of callback ids.  If None, all callbacks will
            be removed.

        Returns
        -------
        None
        """
        if ids is not None:
            bad_ids = []
            for id in ids:
                if callable(id):
                    id = self._callback_id(id)
                try:
                    self.remove_callback(id)
                except RuntimeError:
                    bad_ids.append(id)
                    continue
            if bad_ids:
                raise RuntimeError(
                    '%s: No callbacks with ids %s attached to function %s' %
                    (self.name, bad_ids, self.target_name))
        else:
            self._initialize()

    def emit(self, *args, **kwargs):
        # type: (Any, Any) -> Dict[Hashable, Any]
        """
        Call all of the callbacks registered with this event.

        Returns
        -------
        Dict[Hashable, Any]
            results of all the callbacks, keyed by id
        """
        results = {}
        for id, entry in self._iter_callbacks():
            callback = entry.function
            takes_target_args = entry.options['pass_args']
            if takes_target_args:
                results[id] = callback(*args, **kwargs)
            else:
                results[id] = callback()
        return results


class ReturnEvent(Event[CallableT]):

    options = {
        'pass_args': True,
        'pass_result': False
    }

    def add_callback(self, callback, priority=0.0, id=None,
                     takes_target_args=None, takes_target_result=None):
        # type: (CallableT, float, Optional[Hashable], bool, bool) -> Hashable
        """
        Registers the callback to be called after the target is called.

        Parameters
        ----------
        callback : CallableT
            The callback function that will be called
            after the target is called.
        priority : float
            Higher priority callbacks are run first,
            ties are broken by the order in which callbacks were added.
        id : Optional[Hashable]
            A name to call this callback, must be unique (and hashable)
            or None, if non-unique a RuntimeError will be raised.
            If None, a unique id will be automatically generated.
            NOTE: Callbacks can be removed using their id or the original
            callable (see remove_callback)
        takes_target_args : bool
            If True, callback function will be passed
            the arguments and keyword arguments that are supplied to the
            target function.  If None, defaults to the event's default.
        takes_target_result : bool
            If True, callback will be passed, as
            its first argument, the value returned from calling the
            target function. If None, defaults to the event's default.

        Returns
        -------
        Hashable
        """
        return self._add_callback(
            callback=callback, priority=priority, id=id,
            options={'pass_args': takes_target_args,
                     'pass_result': takes_target_result})

    def emit(self, target_result, *args, **kwargs):
        results = {}
        for id, entry in self._iter_callbacks():
            callback = entry.function
            takes_target_args = entry.options['pass_args']
            takes_target_result = entry.options['pass_result']
            if takes_target_args and takes_target_result:
                results[id] = callback(target_result, *args, **kwargs)
            elif takes_target_result:
                results[id] = callback(target_result)
            elif takes_target_args:
                results[id] = callback(*args, **kwargs)
            else:
                results[id] = callback()
        return results


class ExceptionEvent(Event[CallableT]):

    options = {
        'pass_args': True,
        'handles_exception': False
    }

    def add_callback(self, callback, priority=0.0, id=None,
                     takes_target_args=None, handles_exception=None):
        # type: (CallableT, float, Optional[Hashable], bool, bool) -> Hashable
        """
        Registers the callback to be called after the target raises an
        exception.  Exception callbacks are called in priority order and can
        handle the exception if they register with <handles_exception>.

        Parameters
        ----------
        callback : CallableT
            The callback function that will be called
            before the target function is run.
        priority : float
            Higher priority callbacks are run first,
            ties are broken by the order in which callbacks were added.
        id : Optional[Hashable]
            A name to call this callback, must be unique (and hashable)
            or None, if non-unique a RuntimeError will be raised.
            If None, a unique id will be automatically generated.
            NOTE: Callbacks can be removed using their id or the original
            callable. (see remove_callback)
        takes_target_args : bool
            If True, callback function will be passed the
            arguments and keyword arguments that are supplied to the
            target function. If None, defaults to the event's default.
        handles_exception : bool
            If True, callback will be passed (as
            its first argument) the exception raised by the target function
            or a higher priority exception_callback which raised an
            exception.  If True, this function is responsible for
            handling the exception or reraising it!  NOTE: If True and
            the exception has already been handled, this callback will
            not be called. If None, defaults to the event's default.

        Returns
        -------
        Hashable
        """
        return self._add_callback(
            callback=callback, priority=priority, id=id,
            options={'pass_args': takes_target_args,
                     'handles_exception': handles_exception})

    def emit(self, exception, *args, **kwargs):
        result = None
        for _, entry in self._iter_callbacks():
            callback = entry.function
            takes_target_args = entry.options['pass_args']
            handles_exception = entry.options['handles_exception']

            if handles_exception and exception is None:
                # exception has already been handled, only call callbacks
                # that don't handle exceptions
                continue

            if takes_target_args and handles_exception:
                try:
                    result = callback(exception, *args, **kwargs)
                    exception = None
                except Exception as exc:
                    exception = exc
                    continue
            elif handles_exception:
                try:
                    result = callback(exception)
                    exception = None
                except Exception as exc:
                    exception = exc
                    continue
            elif takes_target_args:
                callback(*args, **kwargs)
            else:
                callback()
        if exception is not None:
            raise exception
        else:
            return result
