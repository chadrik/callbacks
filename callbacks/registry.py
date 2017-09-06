from __future__ import absolute_import, print_function

import types
from weakref import WeakKeyDictionary
import sys
from typing import *

from .events import Event

CallableT = TypeVar('CallableT', bound=Callable)
T = TypeVar('T', bound='Callbacks')
EventT = TypeVar('EventT', bound=Event)

if TYPE_CHECKING:
    Registry = WeakKeyDictionary[object, T]

if sys.version_info[0] == 3:
    def get_unbound_function(unbound):
        return unbound

    create_bound_method = types.MethodType
else:
    def get_unbound_function(unbound):
        return unbound.im_func

    def create_bound_method(func, obj):
        return types.MethodType(func, obj, obj.__class__)


def _get_events(cls):
    # type: (type) -> Tuple[Event, ...]
    # don't check inherited attributes
    if '__callback_events__' in cls.__dict__:
        return cls.__callback_events__  # type: ignore

    ca_list = [(name, event)
               for name, event
               in cls.__dict__.items()
               if isinstance(event, Event)]

    for name, event in ca_list:
        if event.name is None:
            event.name = name

    non_super_events = [
        event
        for event_name, event
        in sorted(ca_list, key=lambda e: e[1].counter)
    ]

    super_cls = []  # type: List[Event]
    non_super_names = set(e.name for e in non_super_events)
    for c in reversed(cls.__mro__[1:-1]):
        sub_events = _get_events(c)
        if sub_events is not None:
            super_cls.extend(
                e for e in sub_events
                if e not in super_cls and e.name not in non_super_names
            )

    all_events = tuple(super_cls + non_super_events)
    cls.__callback_events__ = all_events  # type: ignore
    return all_events


class Callbacks(Generic[CallableT]):
    """
    Holds a target function or method and a set of events with callbacks.
    """

    def __init__(self, target):
        # type: (T, CallableT) -> None
        """
        Parameters
        ----------
        target : CallableT
        """
        self.target = target
        # this will hold the registries for instance method callbacks
        self._instance_registries = WeakKeyDictionary()  # type: Registry[T]
        cls_events = _get_events(self.__class__)
        self._events = tuple([e.copy(target_name=self.target.__name__)
                              for e in cls_events])
        # bind events to the instance
        for e in self._events:
            setattr(self, e.name, e)

        self._update_docstring(self.target)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self.target)

    def _make_child(self, target):
        # type: (T, CallableT) -> T
        child = self.__class__(target)
        for parent_event, child_event in zip(self._events, child._events):
            child_event.parent = parent_event
        return child

    def __call__(self, *args, **kwargs):
        return self.target(*args, **kwargs)

    def __get__(self, instance, obj_type):
        # type: (T, Optional[object], type) -> T
        if instance is None:
            # method is being called on the class instead of an instance
            return self

        if instance not in self._instance_registries:
            # FIXME: https://github.com/python/typeshed/issues/1378
            target = cast(CallableT,
                          create_bound_method(self.target, instance))
            instance_registry = self._make_child(target)
            self._instance_registries[instance] = instance_registry
        else:
            instance_registry = self._instance_registries[instance]

        return instance_registry

    @property
    def _callbacks_info(self):
        # type () -> str
        option_labels = set()
        for event in self._events:
            for entry in event.callbacks.values():
                option_labels.update(entry.options.keys())
        option_labels = sorted(option_labels)
        format_options = '  '.join(['{%s:<%d}' % (x, len(x))
                                    for x in option_labels])

        format_string = ('{id:<38}  {priority:<9}  {order:<6}  {type:<15}  '
                         '{options}')
        lines = []  # type: List[str]
        lines.append(
            format_string.format(id='Label', priority='Priority',
                                 order='Order', type='Event',
                                 options=format_options.format(
                                     **{x: x.replace('_', ' ').capitalize()
                                        for x in option_labels})))

        def format_val(v):
            if v is True:
                return 'true'
            if v is False:
                return 'false'
            return v

        for event in self._events:
            for order, (id, entry) in enumerate(event._iter_callbacks()):
                options = entry.options
                options_str = format_options.format(
                    **{x: format_val(options.get(x, 'N/A'))
                       for x in option_labels})
                lines.append(
                    format_string.format(
                        id=id, priority=entry.priority,
                        order=order, type=event.name,
                        options=options_str).rstrip())

        return '\n'.join(lines)

    def list_callbacks(self):
        # type: () -> None
        """
        List all of the callbacks registered to this function or method.
        """
        print(self._callbacks_info)

    def remove_callback(self, id):
        # type: (Hashable) -> None
        """
        Remove a callback from all events in this registry.

        Parameters
        ----------
        id : Hashable
        """
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
        # type: () -> None
        """
        Remove all callbacks from all events in this registry.

        Note, for instances, this does not affect callbacks registered at the
        class level.
        """
        for event in self._events:
            event.remove_callbacks()
        # FIXME: should we also wipe _instance_registries?

    @property
    def num_callbacks(self):
        # type: () -> int
        """
        Returns the number of callbacks that have been registered on this
        function/method.  If called on an instance-method then it will also
        add the number of class-level callbacks.

        Returns
        -------
        int
            num_callbacks or
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
            lines.append('  {}.add_callback(callable) -> id'
                         .format(event.name))
            lines.append('  {}.remove_callback(id)'
                         .format(event.name))
        lines.extend(
            [
                '  remove_callbacks()',
                '  list_callbacks()'
            ]
        )
        # TODO: smarter entabbing
        lines = ["    " + line for line in lines]
        self.__doc__ = old_docstring + '\n'.join(lines)
