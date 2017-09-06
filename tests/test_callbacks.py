from __future__ import absolute_import, print_function
import unittest

from callbacks import supports_callbacks

called_with = []
def callback(*args, **kwargs):
    called_with.append((args, kwargs))

@supports_callbacks
def foo(bar, baz='bone'):
    return (bar, baz)

called_order = []
def cb1(*args, **kwargs):
    called_order.append('cb1')
def cb2(*args, **kwargs):
    called_order.append('cb2')
def cb3(*args, **kwargs):
    called_order.append('cb3')

class TestCallbackDecorator(unittest.TestCase):
    def setUp(self):
        while called_with:
            called_with.pop()
        while called_order:
            called_order.pop()
        foo.remove_callbacks()

    def test_with_defaults(self):
        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_with), 0)

        foo.on_return.add_callback(callback, takes_target_args=False)

        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_with), 1)
        self.assertEquals(called_with[0], (tuple(), {}))

        result = foo(10, baz=20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_with), 2)
        self.assertEquals(called_with[1], (tuple(), {}))

    def test_raises(self):
        self.assertRaises(ValueError, foo.on_return.add_callback, callback, priority='boo')

    def test_duplicate_id(self):
        foo.on_return.add_callback(callback, id='a', takes_target_args=False)
        self.assertRaises(RuntimeError, foo.on_return.add_callback, callback, id='a')

    def test_remove_raises(self):
        foo.on_return.add_callback(callback, takes_target_args=False)
        foo.on_return.add_callback(callback, id='good_id',
                                   takes_target_args=False)

        self.assertRaises(RuntimeError, foo.on_return.remove_callback, 'bad_id')
        self.assertRaises(RuntimeError, foo.on_return.remove_callbacks, ['bad_id', 'good_id'])
        self.assertEqual(len(foo.on_return.callbacks), 1)

    def test_callbacks_info(self):
        foo.on_call.add_callback(callback, id='a', takes_target_args=False)
        foo.on_call.add_callback(callback, id='b', takes_target_args=True)
        foo.on_return.add_callback(callback, id='c', priority=1.1,
                                   takes_target_args=False,
                                   takes_target_result=True)
        foo.on_exception.add_callback(callback, id='d', takes_target_args=False)
        expected_string = '''\
Label                                   Priority   Order   Event            Handles exception  Pass args  Pass result
a                                       0.0        0       on_call          N/A                false      N/A
b                                       0.0        1       on_call          N/A                true       N/A
c                                       1.1        0       on_return        N/A                false      true
d                                       0.0        0       on_exception     false              false      N/A'''
        print(foo._callbacks_info)
        self.assertEquals(expected_string, foo._callbacks_info)

    def test_with_takes_target_args(self):
        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_with), 0)

        foo.on_return.add_callback(callback, takes_target_args=True)

        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_with), 1)
        self.assertEquals(called_with[0], ((10, 20), {}))

        result = foo(10, baz=20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_with), 2)
        self.assertEquals(called_with[1], ((10, ), {'baz':20}))

    def test_with_takes_target_result(self):
        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_with), 0)

        foo.on_return.add_callback(callback, takes_target_args=False,
                                   takes_target_result=True)

        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_with), 1)
        self.assertEquals(called_with[0], (((10, 20), ), {}))

        result = foo(10, baz=20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_with), 2)
        self.assertEquals(called_with[1], (((10, 20), ),  {}))

    def test_with_takes_target_result_and_args(self):
        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_with), 0)

        foo.on_return.add_callback(callback, takes_target_result=True,
                                   takes_target_args=True)

        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_with), 1)
        self.assertEquals(called_with[0], (((10, 20), 10, 20), {}))

        result = foo(10, baz=20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_with), 2)
        self.assertEquals(called_with[1], (((10, 20), 10),  {'baz':20}))

    def test_before(self):
        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_with), 0)

        foo.on_call.add_callback(callback, takes_target_args=False)

        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_with), 1)
        self.assertEquals(called_with[0], (tuple(), {}))

        result = foo(10, baz=20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_with), 2)
        self.assertEquals(called_with[1], (tuple(), {}))

    def test_before_with_target_args(self):
        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_with), 0)

        foo.on_call.add_callback(callback, takes_target_args=True)

        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_with), 1)
        self.assertEquals(called_with[0], ((10, 20), {}))

        result = foo(10, baz=20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_with), 2)
        self.assertEquals(called_with[1], ((10, ), {'baz': 20}))

    def test_multiple_before(self):
        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_order), 0)

        foo.on_call.add_callback(cb1, takes_target_args=False)
        foo.on_call.add_callback(cb2, takes_target_args=False)
        foo.on_call.add_callback(cb3, takes_target_args=False)

        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(called_order, ['cb1', 'cb2', 'cb3'])

    def test_multiple_before_priority(self):
        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_order), 0)

        foo.on_call.add_callback(cb1, takes_target_args=False)
        foo.on_call.add_callback(cb2, priority=1, takes_target_args=False)
        foo.on_call.add_callback(cb3, priority=1, takes_target_args=False)

        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(called_order, ['cb2','cb3','cb1'])

    def test_multiple(self):
        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_order), 0)

        foo.on_return.add_callback(cb1, takes_target_args=False)
        foo.on_return.add_callback(cb2, takes_target_args=False)
        foo.on_return.add_callback(cb3, takes_target_args=False)

        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(called_order, ['cb1','cb2','cb3'])

    def test_multiple_priority(self):
        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_order), 0)

        foo.on_return.add_callback(cb1, takes_target_args=False)
        foo.on_return.add_callback(cb2, priority=1, takes_target_args=False)
        foo.on_return.add_callback(cb3, priority=1, takes_target_args=False)

        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(called_order, ['cb2','cb3','cb1'])

    def test_remove_callback(self):
        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_order), 0)

        foo.on_return.add_callback(cb1, takes_target_args=False)
        id = foo.on_return.add_callback(cb2, takes_target_args=False)
        foo.on_return.add_callback(cb3, takes_target_args=False)

        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(called_order, ['cb1','cb2','cb3'])

        foo.remove_callback(id)

        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(called_order, ['cb1','cb2','cb3', 'cb1', 'cb3'])

    def test_remove_callbacks_by_id(self):
        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_order), 0)

        l1 = foo.on_return.add_callback(cb1, takes_target_args=False)
        l2 = foo.on_return.add_callback(cb2, takes_target_args=False)
        foo.on_return.add_callback(cb3, takes_target_args=False)

        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(called_order, ['cb1', 'cb2', 'cb3'])

        foo.on_return.remove_callbacks([l1, l2])

        # only cb3 remains
        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(called_order, ['cb1', 'cb2', 'cb3', 'cb3'])

    def test_remove_callbacks_without_id(self):
        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_order), 0)

        foo.on_return.add_callback(cb1, takes_target_args=False)
        foo.on_return.add_callback(cb2, takes_target_args=False)
        foo.on_return.add_callback(cb3, takes_target_args=False)

        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(called_order, ['cb1', 'cb2', 'cb3'])

        foo.on_return.remove_callbacks([cb1, cb2])

        # only cb3 remains
        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(called_order, ['cb1', 'cb2', 'cb3', 'cb3'])

    def test_remove_all_callbacks(self):
        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_order), 0)

        foo.on_return.add_callback(cb1, takes_target_args=False)
        foo.on_return.add_callback(cb2, takes_target_args=False)
        foo.on_return.add_callback(cb3, takes_target_args=False)

        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(called_order, ['cb1', 'cb2', 'cb3'])

        foo.on_return.remove_callbacks()

        # no callbacks remain
        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(called_order, ['cb1', 'cb2', 'cb3'])

    def test_ids(self):
        result = foo(10, 20)
        self.assertEquals(result, (10, 20))
        self.assertEquals(len(called_order), 0)

        l1 = foo.on_return.add_callback(cb1, id=1, takes_target_args=False)
        l2 = foo.on_call.add_callback(cb2, id=2, takes_target_args=False)
        l3 = foo.on_return.add_callback(cb3, takes_target_args=False)

        self.assertEquals(l1, 1)
        self.assertEquals(l2, 2)
        # value returned by id() in cpython is int, in pypy is long
        self.assertEquals(type(l3), type(id(None)))
