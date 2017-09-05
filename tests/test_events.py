from __future__ import absolute_import, print_function
import pytest
from callbacks import supports_callbacks, Callbacks, Event, ReturnEvent
from callbacks.registry import _get_events


class Tracker(object):
    def __init__(self):
        self.called_with = []

    def iter_callback(self, val):
        self.called_with.append(('iter', val))

    def result_callback(self, val):
        self.called_with.append(('result', val))


@pytest.fixture
def cb():
    yield Tracker()


class Custom(Callbacks):
    on_iteration = Event(options={'pass_args': True})
    on_return = ReturnEvent(options={'pass_result': True})
    unused = ReturnEvent()


@supports_callbacks(Custom)
def foo(num):
    result = []
    for i in range(num):
        foo.on_iteration.emit(i)
        result.append(i)
    foo.on_return.emit(target_result=result)
    return result


@pytest.fixture
def func():
    yield foo
    foo.remove_callbacks()


def test_event_copy():
    e = Event()
    assert type(e.counter) is int
    assert e.callbacks is None
    e1 = e.copy()
    assert e1.counter == e.counter
    assert e1.callbacks is None
    e2 = e.copy(target_name='foo')
    assert e2.counter == e.counter
    assert e2.callbacks is not None


def test_event_counter():
    assert type(Custom.on_iteration.counter) is int
    assert type(Custom.on_return.counter) is int
    assert type(Custom.unused.counter) is int
    assert Custom.on_iteration.counter < Custom.on_return.counter
    assert Custom.on_return.counter < Custom.unused.counter


def test_registry():
    def f():
        return

    cls_events = _get_events(Custom)
    assert [e.name for e in cls_events] == ['on_iteration', 'on_return', 'unused']
    reg = Custom(f)
    assert [e.name for e in reg._events] == ['on_iteration', 'on_return', 'unused']
    assert len([e for e in reg._events if e.callbacks is not None]) == 3
    assert reg.on_iteration is reg._events[0]
    assert reg.on_return is reg._events[1]
    assert reg.on_iteration.callbacks is not None
    assert reg.on_iteration.parents() == []
    assert list(reg.on_iteration._iter_callbacks()) == []


def test_decorator():
    @supports_callbacks(Custom)
    def f():
        pass

    assert type(f) is Custom


def test_options(func):
    assert func.on_return.options == {'pass_args': False, 'pass_result': True}

    assert func.on_iteration.options == {'pass_args': True}

    with pytest.raises(RuntimeError):
        Event('foo', options={'foo': 'bar'})


def test_events(func, cb):
    result = func(2)
    assert result == [0, 1]
    assert len(cb.called_with) == 0

    func.on_return.add_callback(cb.result_callback)

    result = func(2)
    assert result == [0, 1]
    assert cb.called_with == [('result', [0, 1])]

    func.on_iteration.add_callback(cb.iter_callback)

    result = func(3)
    assert result == [0, 1, 2]
    assert cb.called_with == [
        ('result', [0, 1]),
        ('iter', 0),
        ('iter', 1),
        ('iter', 2),
        ('result', [0, 1, 2]),
    ]
