from __future__ import absolute_import, print_function

import types
from collections import defaultdict
from weakref import WeakKeyDictionary, proxy
import inspect
import sys

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

if PY3:
    def get_unbound_function(unbound):
        return unbound

    create_bound_method = types.MethodType
else:
    def get_unbound_function(unbound):
        return unbound.im_func

    def create_bound_method(func, obj):
        return types.MethodType(func, obj, obj.__class__)


class Event(object):
    """
    Holds a set of callbacks registered using `add_callback()` handles
    executing them when `emit()` is called.
    """
    def __init__(self, name, target_name):
        self.name = name
        self.target_name = target_name
        self._initialize()

    def _initialize(self):
        # mapping of id to callback info dict
        self.callbacks = defaultdict(dict)
        # mapping of priority to list of ids
        self._priorities = defaultdict(list)

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
        """
        for priority in sorted(self._priorities.keys(), reverse=True):
            for id in self._priorities[priority]:
                info = self.callbacks[id]
                yield (info['function'], id, info['extra'])

    def _add_callback(self, callback, priority, id, extra):
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
            'extra': extra or {}
        }
        self.callbacks[id] = entry
        self._priorities[priority].append(id)
        return id

    def add_callback(self, callback, priority=0, id=None,
                     takes_target_args=False):
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
                target function.
        Returns:
            id
        """
        return self._add_callback(
            callback=callback, priority=priority, id=id,
            extra={'takes_args': takes_target_args})

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

        for ids in self._priorities.values():
            if id in ids:
                ids.remove(id)

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
        for callback, id, extra in self._iter_callbacks():
            takes_target_args = extra['takes_args']
            if takes_target_args:
                results[id] = callback(*args, **kwargs)
            else:
                results[id] = callback()
        return results


class PostReturnEvent(Event):

    def add_callback(self, callback, priority=0, id=None,
                     takes_target_args=False, takes_target_result=False):
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
                target function.
            takes_target_result: If True, callback will be passed, as
                its first argument, the value returned from calling the
                target function.
        Returns:
            id
        """
        return self._add_callback(
            callback=callback, priority=priority, id=id,
            extra={'takes_args': takes_target_args,
                   'takes_result': takes_target_result})

    def emit(self, target_result, *args, **kwargs):
        results = {}
        for callback, id, extra in self._iter_callbacks():
            takes_target_args = extra['takes_args']
            takes_target_result = extra['takes_result']
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

    def add_callback(self, callback, priority=0, id=None,
                     takes_target_args=False, handles_exception=False):
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
                not be called.
        Returns:
            id
        """
        return self._add_callback(
            callback=callback, priority=priority, id=id,
            extra={'takes_args': takes_target_args,
                   'handles_exception': handles_exception})

    def emit(self, exception, *args, **kwargs):
        result = None
        for callback, id, extra in self._iter_callbacks():
            takes_target_args = extra['takes_args']
            handles_exception = extra['handles_exception']

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


class AbstractCallbackRegistry(object):
    """
    This decorator enables a function or a class/instance method to register
    callbacks.

    - Callbacks are organized by Event
    - A CallbackRegistry stores one or more events as attributes
    """

    def __init__(self, target):
        self.__name__ = target.__name__
        self.target = target
        if hasattr(target, '_argspec'):
            self._argspec = target._argspec
        else:
            self._argspec = inspect.getargspec(target)

        self._target_is_method = False
        self._events = []
        # this will hold the registries for instance method callbacks
        self._instance_registries = WeakKeyDictionary()
        self._initialize()
        # must occur after initialize:
        self._update_docstring(self.target)

    def _add_event(self, name, type=Event):
        """
        Add an Event to this registry.  Should be called from _initialize on
        sub-classes
        """
        event = type(name, self.__name__)
        self._events.append(event)
        return event

    def _initialize(self):
        pass

    def __call__(self, *args, **kwargs):
        print('self %s %s' % (self, self.target))
        return self.target(*args, **kwargs)

    def __get__(self, obj, obj_type):
        # method is being called on the class instead of an instance
        if obj is None:
            # when target was decorated, it had not been bound yet, but now it
            # is, so update _target_is_method.
            self._target_is_method = True
            return self

        if obj not in self._instance_registries:
            callback_registry = self.__class__(self)
            callback_registry._target_is_method=True
            self._instance_registries[obj] = callback_registry
        else:
            callback_registry = self._instance_registries[obj]

        return create_bound_method(callback_registry, obj)

    @property
    def _callbacks_info(self):
        extra_ids = set()
        for event in self._events:
            for info in event.callbacks.values():
                extra_ids.update(info['extra'].keys())
        extra_ids = sorted(extra_ids)
        format_extra = '  '.join(['{%s:<%d}' % (x, len(x))
                                  for x in extra_ids])

        format_string = ('{id:<38}  {priority:<9}  {order:<6}  {type:<15}  '
                         '{extra}')
        lines = []
        lines.append(
            format_string.format(id='Label', priority='Priority',
                                 order='Order', type='Event',
                                 extra=format_extra.format(
                                     **{x : x.replace('_', ' ').capitalize()
                                        for x in extra_ids})))

        def format_val(v):
            if v is True:
                return 'true'
            if v is False:
                return 'false'
            return v

        for event in self._events:
            for id, info in sorted(event.callbacks.items()):
                order = event._priorities[info['priority']].index(id)
                extra = info['extra']
                lines.append(
                    format_string.format(id=id, priority=info['priority'],
                                         order=order, type=event.name,
                                         extra=format_extra.format(
                                             **{x : format_val(extra.get(x, 'N/A'))
                                                for x in extra_ids})).rstrip())

        return '\n'.join(lines)

    def list_callbacks(self):
        """
        List all of the callbacks registered to this function or method.
        """
        print(self._callbacks_info)

    def remove_callback(self, id):
        for event in self._events:
            try:
                event.remove_callback(id)
            except RuntimeError:
                continue
            else:
                return
        raise

    def remove_callbacks(self):
        """
        Remove callbacks from all events
        """
        for event in self._events:
            event.remove_callbacks()
        # FIXME: should we also wipe _instance_registries?

    @property
    def num_callbacks(self):
        """
        Returns the number of callbacks that have been registered on this
        function/method.  If called on an instance-method then it will also
        add the number of class-level callbacks.

        Returns:
            num_callbacks
            -or-
            num_class_level_callbacks + num_instance_level_callbacks
        """
        num = sum(len(event.callbacks) for event in self._events)
        if isinstance(self.target, self.__class__):
            return self.target.num_callbacks + num
        else:
            return num

    def _update_docstring(self, target):
        old_docstring = target.__doc__
        if old_docstring is None:
            old_docstring = '<No docstring was previously set>'

        lines = ["This %s supports callbacks:"]
        for event in self._events:
            lines.append('  {}.add_callback(callable) -> id'.format(event.name))
            lines.append('  {}.remove_callback(id)'.format(event.name))
        lines.extend(
            [
                '  remove_callbacks()',
                '  list_callbacks()'
            ]
        )
        # TODO: smarter entabbing
        lines = ["    " + line for line in lines]
        self.__doc__ = old_docstring + '\n'.join(lines)


class SingleEvent(AbstractCallbackRegistry):
    def _initialize(self):
        self.event = self._add_event('event', Event)
        self.add_callback = self.event.add_callback


class AutoCallbacks(AbstractCallbackRegistry):
    """

    This is a decorator.  Once a function/method is decorated, callbacks can
    be registered to be run before or after the target function (or after the
    target function raises an exception).

    to register callbacks:
        <target>.on_call.add_callback(callback) -> id
        <target>.on_return.add_callback(callback) -> id
        <target>.on_exception.add_callback(callback) -> id
    where <target> is the function/method that was decorated.

    To remove a callback you use:
        <target>.remove_callback(id)

    To remove all callbacks use:
        <target>.remove_callbacks()

    To print a list of callbacks use:
        <target>.list_callbacks()

    """
    def _initialize(self):
        self.on_call = self._add_event('on_call', Event)
        self.on_return = self._add_event('on_return', PostReturnEvent)
        self.on_exception = self._add_event('on_exception', ExceptionEvent)

    def __call__(self, *args, **kwargs):
        print('self %s %s' % (self, self.target))
        if self._target_is_method:
            cb_args = args[1:]  # skip over 'self' arg
        else:
            cb_args = args

        self.on_call.emit(*cb_args, **kwargs)
        try:
            target_result = self.target(*args, **kwargs)
        except Exception as e:
            target_result = self.on_exception.emit(e, *cb_args, **kwargs)
        self.on_return.emit(target_result, *cb_args, **kwargs)
        return target_result

    # -- wrappers, for backward compatibility

    def add_pre_callback(self, callback, priority=0, label=None,
                         takes_target_args=False):
        """
        Registers the callback to be called before the target.

        Inputs:
            callback: The callback function that will be called before
                the target function is run.
            priority: Number. Higher priority callbacks are run first,
                ties are broken by the order in which callbacks were added.
            label: A name to call this callback, must be unique (and hashable)
                or None, if non-unique a RuntimeError will be raised.
                If None, a unique label will be automatically generated.
                NOTE: Callbacks can be removed using their label.
                      (see remove_callback)
            takes_target_args: If True, callback function will be passed the
                arguments and keyword arguments that are supplied to the
                target function.
        Returns:
            label
        """
        return self.on_call.add_callback(
            callback=callback, priority=priority, id=label,
            takes_target_args=takes_target_args)

    def add_post_callback(self, callback, priority=0, label=None,
                          takes_target_args=False,
                          takes_target_result=False):
        """
            Registers the callback to be called after the target is called.

        Inputs:
            callback: The callback function that will be called after
                the target is called.
            priority: Number. Higher priority callbacks are run first,
                ties are broken by the order in which callbacks were added.
            label: A name to call this callback, must be unique (and hashable)
                or None, if non-unique a RuntimeError will be raised.
                If None, a unique label will be automatically generated.
                NOTE: Callbacks can be removed using their label.
                      (see remove_callback)
            takes_target_args: If True, callback function will be passed the
                arguments and keyword arguments that are supplied to the
                target function.
            takes_target_result: If True, callback will be passed, as
                its first argument, the value returned from calling the
                target function.
        Returns:
            label
        """
        return self.on_return.add_callback(
            callback=callback, priority=priority, id=label,
            takes_target_args=takes_target_args,
            takes_target_result=takes_target_result)

    # alias
    add_callback = add_post_callback

    def add_exception_callback(self, callback, priority=0, label=None,
                               takes_target_args=False,
                               handles_exception=False):
        """
            Registers the callback to be called after the target raises an
        exception.  Exception callbacks are called in priority order and can
        handle the exception if they register with <handles_exception>.

        Inputs:
            callback: The callback function that will be called after
                the target function raises an exception.
            priority: Number. Higher priority callbacks are run first,
                ties are broken by the order in which callbacks were added.
            label: A name to call this callback, must be unique (and hashable)
                or None, if non-unique a RuntimeError will be raised.
                If None, a unique label will be automatically generated.
                NOTE: Callbacks can be removed using their label.
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
                not be called.
        Returns:
            label
        """
        return self.on_exception.add_callback(
            callback=callback, priority=priority, id=label,
            takes_target_args=takes_target_args,
            handles_exception=handles_exception)


supports_callbacks = AutoCallbacks
