from __future__ import absolute_import, print_function

import types
import operator
from collections import OrderedDict


class Event(object):
    """
    Holds a set of callbacks registered using `add_callback()` and handles
    executing them when `emit()` is called.
    """
    options = {
        'pass_args': False,
    }

    def __init__(self, name, target_name=None, parent=None, options=None):
        self.name = name
        self.target_name = target_name
        self.parent = parent
        self.options = options or self.__class__.options
        self._initialize()

    def _initialize(self):
        # mapping of id to callback info dict
        self.callbacks = OrderedDict()

    def parents(self):
        parents = []
        p = self.parent
        while p:
            parents.append(p)
            p = p.parent
        return parents

    def _merge_options(self, options):
        result = self.options.copy()
        for key, value in options.items():
            if value is not None:
                result[key] = value
        return result

    def _make_child(self):
        """
        Create a new event that is the child of this one.  Used to form a link
        between a class-level Event and an instance-level Event.

        Returns:
             Event
        """
        return self.__class__(self.name, self.target_name, parent=self,
                              options=self.options)

    @staticmethod
    def _callback_id(target):
        """
        Given a listener object, return the key that would be used to identify it
        for the purposes of event registration.
        """
        if isinstance(target, types.MethodType):
            return id(target.im_self), id(target.im_func)
        return id(target)

    def _iter_callbacks(self):
        """
        Iterate over callbacks in order of priority.

        Yields:
            (id, info)
        """
        # consider all parents when ordering based on priority
        parents = self.parents()
        callbacks = []
        for depth, event in enumerate([self] + parents):
            for id, info in event.callbacks.items():
                callbacks.append(((info['priority'], depth), id, info))
        callbacks.sort(key=operator.itemgetter(0), reverse=True)

        for key, id, info in callbacks:
            yield (id, info)

    def _add_callback(self, callback, priority, id, options):
        try:
            priority = float(priority)
        except:
            raise ValueError('Priority could not be cast into a float.')

        if id is None:
            id = self._callback_id(callback)

        if id in self.callbacks.keys():
            raise RuntimeError('Callback with id="%s" already registered.'
                               % id)

        entry = {
            'function': callback,
            'priority': priority,
            'options': options or {}
        }
        self.callbacks[id] = entry
        return id

    def add_callback(self, callback, priority=0, id=None,
                     takes_target_args=None):
        """
        Registers the callback.

        Inputs:
            callback: The callback function that will be called before
                the target function is run.
            priority: Number. Higher priority callbacks are run first,
                ties are broken by the order in which callbacks were added.
            id: A name to call this callback, must be unique (and hashable)
                or None, if non-unique a RuntimeError will be raised.
                If None, a unique id will be automatically generated.
                NOTE: Callbacks can be removed using their id.
                      (see remove_callback)
            takes_target_args: If True, callback function will be passed the
                arguments and keyword arguments that are supplied to the
                target function. If None, defaults to the event's default.
        Returns:
            id
        """
        return self._add_callback(
            callback=callback, priority=priority, id=id,
            options=self._merge_options({'pass_args': takes_target_args}))

    def remove_callback(self, id):
        """
        Unregisters the callback.

        Inputs:
            id: The name of the callback, the id returned by add_callback,
                or the callback itself.  This was either supplied as a
                keyword argument to add_callback or was automatically generated
                and returned from add_callback. If id is not valid a
                RuntimeError is raised.
        Returns:
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
        """
        Unregisters callback(s) from the target.

        Inputs:
            ids: A list of callback ids.  If empty, all callbacks will
                be removed.
        Returns:
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
        """
        Call all of the callbacks registered with this event.
        """
        results = {}
        for id, info in self._iter_callbacks():
            callback = info['function']
            takes_target_args = info['options']['pass_args']
            if takes_target_args:
                results[id] = callback(*args, **kwargs)
            else:
                results[id] = callback()
        return results


class ReturnEvent(Event):

    options = {
        'pass_args': False,
        'pass_result': False
    }

    def add_callback(self, callback, priority=0, id=None,
                     takes_target_args=None, takes_target_result=None):
        """
        Registers the callback to be called after the target is called.

        Inputs:
            callback: The callback function that will be called after
                the target is called.
            priority: Number. Higher priority callbacks are run first,
                ties are broken by the order in which callbacks were added.
            id: A name to call this callback, must be unique (and hashable)
                or None, if non-unique a RuntimeError will be raised.
                If None, a unique id will be automatically generated.
                NOTE: Callbacks can be removed using their id.
                      (see remove_callback)
            takes_target_args: If True, callback function will be passed the
                arguments and keyword arguments that are supplied to the
                target function.  If None, defaults to the event's default.
            takes_target_result: If True, callback will be passed, as
                its first argument, the value returned from calling the
                target function. If None, defaults to the event's default.
        Returns:
            id
        """
        return self._add_callback(
            callback=callback, priority=priority, id=id,
            options=self._merge_options({'pass_args': takes_target_args,
                                         'pass_result': takes_target_result}))

    def emit(self, target_result, *args, **kwargs):
        results = {}
        for id, info in self._iter_callbacks():
            callback = info['function']
            takes_target_args = info['options']['pass_args']
            takes_target_result = info['options']['pass_result']
            if takes_target_args and takes_target_result:
                results[id] = callback(target_result, *args, **kwargs)
            elif takes_target_result:
                results[id] = callback(target_result)
            elif takes_target_args:
                results[id] = callback(*args, **kwargs)
            else:
                results[id] = callback()
        return results


class ExceptionEvent(Event):

    options = {
        'pass_args': False,
        'handles_exception': False
    }

    def add_callback(self, callback, priority=0, id=None,
                     takes_target_args=None, handles_exception=None):
        """
        Registers the callback to be called after the target raises an
        exception.  Exception callbacks are called in priority order and can
        handle the exception if they register with <handles_exception>.

        Inputs:
            callback: The callback function that will be called after
                the target function raises an exception.
            priority: Number. Higher priority callbacks are run first,
                ties are broken by the order in which callbacks were added.
            id: A name to call this callback, must be unique (and hashable)
                or None, if non-unique a RuntimeError will be raised.
                If None, a unique id will be automatically generated.
                NOTE: Callbacks can be removed using their id.
                      (see remove_callback)
            takes_target_args: If True, callback function will be passed the
                arguments and keyword arguments that are supplied to the
                target function.
            handles_exception: If True, callback will be passed (as
                its first argument) the exception raised by the target function
                or a higher priority exception_callback which raised an
                exception.  If True, this function is responsible for
                handling the exception or reraising it!  NOTE: If True and
                the exception has already been handled, this callback will
                not be called. If None, defaults to the event's default.
        Returns:
            id
        """
        return self._add_callback(
            callback=callback, priority=priority, id=id,
            options=self._merge_options({'pass_args': takes_target_args,
                                         'handles_exception': handles_exception}))

    def emit(self, exception, *args, **kwargs):
        result = None
        for id, info in self._iter_callbacks():
            callback = info['function']
            takes_target_args = info['options']['pass_args']
            handles_exception = info['options']['handles_exception']

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

