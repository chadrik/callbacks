from __future__ import absolute_import, print_function
import unittest

from callbacks import supports_callbacks, Event, ReturnEvent

called_with = []
def iter_callback(val):
    called_with.append(('iter', val))

def result_callback(val):
    called_with.append(('result', val))


@supports_callbacks('on_iteration', pass_args=True)
@supports_callbacks('on_return', ReturnEvent, pass_result=True)
def foo(num):
    result = []
    for i in range(num):
        foo.on_iteration.emit(i)
        result.append(i)
    foo.on_return.emit(target_result=result)
    return result


class TestEvents(unittest.TestCase):
    def setUp(self):
        while called_with:
            called_with.pop()
        foo.remove_callbacks()

    def test_options(self):
        self.assertEquals(foo.on_return.options,
                          {'pass_args': False, 'pass_result': True})

        self.assertEquals(foo.on_iteration.options,
                          {'pass_args': True})

        self.assertRaises(RuntimeError, Event, 'foo', options={'foo': 'bar'})

    def test_events(self):
        result = foo(2)
        self.assertEquals(result, [0, 1])
        self.assertEquals(len(called_with), 0)

        foo.on_return.add_callback(result_callback)

        result = foo(2)
        self.assertEquals(result, [0, 1])
        self.assertEquals(called_with, [('result', [0, 1])])

        foo.on_iteration.add_callback(iter_callback)

        result = foo(3)
        self.assertEquals(result, [0, 1, 2])
        self.assertEquals(called_with, [
            ('result', [0, 1]),
            ('iter', 0),
            ('iter', 1),
            ('iter', 2),
            ('result', [0, 1, 2]),
        ])
