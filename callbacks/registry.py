from __future__ import absolute_import, print_function

import types
from weakref import WeakKeyDictionary
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


class CallbackRegistry(object):
    """
    This decorator enables a function or a class/instance method to register
    callbacks.

    - Callbacks are organized by Event
    - A CallbackRegistry stores one or more events as attributes
    """

    def __init__(self, target, events):
        self.target = target
        if hasattr(target, '_argspec'):
            self._argspec = target._argspec
        else:
            self._argspec = inspect.getargspec(target)

        self._events = []
        [self._add_event(event) for event in events]
        # this will hold the registries for instance method callbacks
        self._instance_registries = WeakKeyDictionary()
        self._update_docstring(self.target)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.target)

    def _make_child(self, target):
        events = [event._make_child() for event in self._events]
        return self.__class__(target, events)

    def _add_event(self, event):
        event.target_name = self.target.__name__
        if hasattr(self, event.name):
            raise RuntimeError('Event "%s" already registered.' % event.name)
        setattr(self, event.name, event)
        self._events.append(event)

    def __call__(self, *args, **kwargs):
        # print('self %s %s' % (self, self.target))
        return self.target(*args, **kwargs)

    def __get__(self, instance, obj_type):
        # method is being called on the class instead of an instance
        if instance is None:
            return self

        if instance not in self._instance_registries:
            target = create_bound_method(self.target, instance)
            callback_registry = self._make_child(target)
            self._instance_registries[instance] = callback_registry
        else:
            callback_registry = self._instance_registries[instance]

        return callback_registry

    @property
    def _callbacks_info(self):
        option_labels = set()
        for event in self._events:
            for info in event.callbacks.values():
                option_labels.update(info['options'].keys())
        option_labels = sorted(option_labels)
        format_options = '  '.join(['{%s:<%d}' % (x, len(x))
                                  for x in option_labels])

        format_string = ('{id:<38}  {priority:<9}  {order:<6}  {type:<15}  '
                         '{options}')
        lines = []
        lines.append(
            format_string.format(id='Label', priority='Priority',
                                 order='Order', type='Event',
                                 options=format_options.format(
                                     **{x : x.replace('_', ' ').capitalize()
                                        for x in option_labels})))

        def format_val(v):
            if v is True:
                return 'true'
            if v is False:
                return 'false'
            return v

        for event in self._events:
            for order, (id, info) in enumerate(event._iter_callbacks()):
                options = info['options']
                lines.append(
                    format_string.format(id=id, priority=info['priority'],
                                         order=order, type=event.name,
                                         options=format_options.format(
                                             **{x : format_val(options.get(x, 'N/A'))
                                                for x in option_labels})).rstrip())

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
                # success
                return
        raise

    def remove_callbacks(self):
        """
        Remove callbacks from all events.

        Note, for instances, this does not affect callbacks registered at the
        class level.
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
        return sum(len(list(event._iter_callbacks()))
                   for event in self._events)

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

