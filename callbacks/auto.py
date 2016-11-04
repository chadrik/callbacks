from __future__ import absolute_import, print_function
from callbacks.registry import CallbackRegistry
from callbacks.events import Event, ReturnEvent, ExceptionEvent


class AutoCallbacks(CallbackRegistry):
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

    def __init__(self, target, events=None):
        if events is None:
            events = [
                Event('on_call'),
                ReturnEvent('on_return'),
                ExceptionEvent('on_exception')
            ]
        super(AutoCallbacks, self).__init__(target, events)

    def __call__(self, *args, **kwargs):
        print('self %s %s' % (self, self.target))

        self.on_call.emit(*args, **kwargs)
        try:
            target_result = self.target(*args, **kwargs)
        except Exception as e:
            target_result = self.on_exception.emit(e, *args, **kwargs)
        self.on_return.emit(target_result, *args, **kwargs)
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


def supports_callbacks(event_or_target=None, event_type=Event, **options):
    if event_or_target is None:
        # @supports_callbacks()
        # def foo(...)
        assert not options, \
            "automatic callbacks do not support keyword options"
        return AutoCallbacks
    elif callable(event_or_target):
        # @supports_callbacks
        # def foo(...)
        assert not options, \
            "automatic callbacks do not support keyword options"
        return AutoCallbacks(event_or_target)
    else:
        # @supports_callbacks('event1')
        # @supports_callbacks(ReturnEvent('event3'))
        # def foo(...)
        event = event_or_target
        def decorator(target):
            if isinstance(target, CallbackRegistry):
                reg = target
            else:
                reg = CallbackRegistry(target, [])
            reg._add_event(event_type(event, options=options))
            return reg

        return decorator
