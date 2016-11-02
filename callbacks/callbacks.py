from __future__ import absolute_import, print_function

import types
from collections import defaultdict
from weakref import WeakKeyDictionary, proxy
import uuid
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


class AbstractCallbackRegistry(object):
    '''
        This decorator enables a function or a class/instance method to register
    callbacks.  Callbacks can be registered to be run before or after the
    target function (or after the target function raises an exception).
    See the docstring for add_*_callback for more information.
    '''
    def __init__(self, target, target_is_method=False):
        self.id = uuid.uuid4()

        self.target = target
        self.__name__ = target.__name__
        if hasattr(target, '_argspec'):
            self._argspec = target._argspec
        else:
            self._argspec = inspect.getargspec(target)

        self._target_is_method = target_is_method
        self._initialize()

    @property
    def num_callbacks(self):
        """
            Retuns the number of callbacks that have been registered on this
        function/method.  If called on an instance-method then it will also
        return the number of class-level callbacks.

        Returns:
            num_callbacks
            -or-
            (num_class_level_callbacks, num_instance_level_callbacks)
        """
        num = len(self.callbacks)
        if isinstance(self.target, self.__class__):
            return self.target.num_callbacks, num
        else:
            return num

    def _initialize(self):
        # this will hold the registries for instance method callbacks
        self._callback_registries = WeakKeyDictionary()

        # this holds the callback functions and how they should be called
        self.callbacks = defaultdict(dict)
        self._priorities = defaultdict(lambda: defaultdict(list))

    def _iter_callbacks(self, type):
        '''
        Iterate over callbacks in order of priority.
        '''
        for priority in sorted(self._priorities[type].keys(), reverse=True):
            for label in self._priorities[type][priority]:
                info = self.callbacks[label]
                yield (info['function'], info['extra'])

    @property
    def _callbacks_info(self):
        extra_labels = set()
        for info in self.callbacks.values():
            extra_labels.update(info['extra'].keys())
        extra_labels = sorted(extra_labels)
        format_extra = '  '.join(['{%s:<%d}' % (x, len(x))
                                  for x in extra_labels])
        format_string = '{label:<38}  {priority:<9}  {order:<6}  {type:<10}  {extra}'
        lines = []
        lines.append(
            format_string.format(label='Label', priority='Priority',
                                 order='Order', type='Type',
                                 extra=format_extra.format(
                                     **{x : x.replace('_', ' ').capitalize()
                                        for x in extra_labels})))

        for label, info in sorted(self.callbacks.items()):
            order = self._priorities[info['type']][info['priority']].index(label)
            extra = info['extra']
            lines.append(
                format_string.format(label=label, priority=info['priority'],
                                     order=order, type=info['type'],
                                     extra=format_extra.format(
                                         **{x : extra.get(x, 'N/A')
                                            for x in extra_labels})).rstrip())

        return '\n'.join(lines)

    def list_callbacks(self):
        '''
            List all of the callbacks registered to this function or method.
        '''
        print(self._callbacks_info)

    def _add_callback(self, callback, priority, label, type, extra):
        try:
            priority = float(priority)
        except:
            raise ValueError('Priority could not be cast into a float.')

        if label is None:
            label = uuid.uuid4()

        if label in self.callbacks.keys():
            raise RuntimeError('Callback with label="%s" already registered.'
                               % label)

        entry = {
            'function': callback,
            'priority': priority,
            'type': type,
            'extra': extra or {}
        }
        self.callbacks[label] = entry
        self._priorities[type][priority].append(label)
        return label

    def remove_callback(self, label):
        '''
        Unregisters the callback from the target.

        Inputs:
            label: The name of the callback.  This was either supplied as a
                keyword argument to add_callback or was automatically generated
                and returned from add_callback. If label is not valid a
                RuntimeError is raised.
        Returns:
            None
        '''
        if label not in self.callbacks:
            raise RuntimeError(
                'No callback with label "%s" attached to function "%s"' %
                (label, self.target.__name__))

        for priomap in self._priorities.values():
            for priority in priomap.keys():
                if label in priomap[priority]:
                    priomap[priority].remove(label)

        del self.callbacks[label]

    def remove_callbacks(self, labels=None):
        '''
        Unregisters callback(s) from the target.

        Inputs:
            labels: A list of callback labels.  If empty, all callbacks will
                be removed.
        Returns:
            None
        '''
        if labels is not None:
            bad_labels = []
            for label in labels:
                try:
                    self.remove_callback(label)
                except RuntimeError:
                    bad_labels.append(label)
                    continue
            if bad_labels:
                raise RuntimeError(
                    'No callbacks with labels %s attached to function %s' %
                    (bad_labels, self.target.__name__))
        else:
            self._initialize()


class SupportsCallbacks(AbstractCallbackRegistry):
    def _initialize(self):
        super(SupportsCallbacks, self)._initialize()
        self._update_docstring(self.target)
        # alias
        self.add_callback = self.add_post_callback

    def __get__(self, obj, obj_type=None):
        """
            To allow each instance of a class to have different callbacks
        registered we store a callback registry on the instance itself.
        Keying off of the id of the decorator allows us to have multiple
        methods support callbacks on the same instance simultaneously.
        """
        # method is being called on the class instead of an instance
        if obj is None:
            # when target was decorated, it had not been bound yet, but now it
            # is, so update _target_is_method.
            self._target_is_method = True
            return self

        if obj not in self._callback_registries:
            callback_registry = self.__class__(
                self, target_is_method=True)
            self._callback_registries[obj] = proxy(callback_registry)
        else:
            callback_registry = self._callback_registries[obj]

        return create_bound_method(callback_registry, obj)

    def __call__(self, *args, **kwargs):
        print('self %s %s' % (self, self.target))
        if self._target_is_method:
            cb_args = args[1:]  # skip over 'self' arg
        else:
            cb_args = args

        self._call_pre_callbacks(*cb_args, **kwargs)
        try:
            target_result = self.target(*args, **kwargs)
        except Exception as e:
            target_result = self._call_exception_callbacks(e, *cb_args, **kwargs)
        self._call_post_callbacks(target_result, *cb_args, **kwargs)
        return target_result

    def add_pre_callback(self, callback, priority=0, label=None,
                         takes_target_args=False):
        '''
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
        '''
        return self._add_callback(
            callback=callback, priority=priority, label=label, type='pre',
            extra={'takes_args': takes_target_args})

    def add_post_callback(self, callback, priority=0, label=None,
                          takes_target_args=False,
                          takes_target_result=False):
        '''
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
        '''
        return self._add_callback(
            callback=callback, priority=priority, label=label, type='post',
            extra={'takes_args': takes_target_args,
                   'takes_result': takes_target_result})

    def add_exception_callback(self, callback, priority=0, label=None,
                               takes_target_args=False,
                               handles_exception=False):
        '''
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
        '''
        return self._add_callback(
            callback=callback, priority=priority, label=label, type='exception',
            extra={'takes_args': takes_target_args,
                   'handles_exception': handles_exception})

    def _call_pre_callbacks(self, *args, **kwargs):
        for callback, extra in self._iter_callbacks('pre'):
            takes_target_args = extra['takes_args']
            if takes_target_args:
                callback(*args, **kwargs)
            else:
                callback()

    def _call_post_callbacks(self, target_result, *args, **kwargs):
        for callback, extra in self._iter_callbacks('post'):
            takes_target_args = extra['takes_args']
            takes_target_result = extra['takes_result']
            if takes_target_args and takes_target_result:
                callback(target_result, *args, **kwargs)
            elif takes_target_result:
                callback(target_result)
            elif takes_target_args:
                callback(*args, **kwargs)
            else:
                callback()

    def _call_exception_callbacks(self, exception, *args, **kwargs):
        result = None
        for callback, extra in self._iter_callbacks('exception'):
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

    def _update_docstring(self, target):
            method_or_function = {True: 'method',
                                  False: 'function'}
            old_docstring = target.__doc__
            if old_docstring is None:
                old_docstring = '<No docstring was previously set>'

            docstring = '''
        %s%s
    %s

    This %s supports callbacks.
      %s.add_pre_callback(callback)          returns: label
      %s.add_post_callback(callback)         returns: label
      %s.add_exception_callback(callback)    returns: label
      %s.remove_callback(label)              removes a single callback
      %s.remove_callbacks()                  removes all callbacks
      %s.list_callbacks()                    prints callback information
    ''' % (target.__name__,
           inspect.formatargspec(*self._argspec),
           old_docstring,
           method_or_function[self._target_is_method],
           target.__name__,
           target.__name__,
           target.__name__,
           target.__name__,
           target.__name__,
           target.__name__)

            self.__doc__ = docstring


def supports_callbacks(target=None):
    """
        This is a decorator.  Once a function/method is decorated, you can
    register callbacks:
        <target>.add_pre_callback(callback)        returns: label
        <target>.add_post_callback(callback)       returns: label
        <target>.add_exception_callback(callback)  returns: label
    where <target> is the function/method that was decorated.

    To remove a callback you use:
        <target>.remove_callback(label)

    To remove all callbacks use:
        <target>.remove_callbacks()

    To print a list of callbacks use:
        <target>.list_callbacks()
    """
    if callable(target):
        # this support bare @supports_callbacks syntax (no calling brackets)
        return SupportsCallbacks(target)
    else:
        return SupportsCallbacks
