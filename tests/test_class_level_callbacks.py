from __future__ import absolute_import, print_function
import unittest

from callbacks import supports_callbacks

class TestClassLevel(unittest.TestCase):
    def test_registries_are_separate(self):

        def callback():
            pass
        class ExampleClass(object):
            @supports_callbacks
            def method(self):
                pass

        e = ExampleClass()
        self.assertEquals(ExampleClass.method.num_callbacks, 0)
        self.assertEquals(e.method.num_callbacks, 0)

        ExampleClass.method.on_return.add_callback(callback, id='foo')
        self.assertEquals(ExampleClass.method.num_callbacks, 1)
        self.assertEquals(e.method.num_callbacks, 1)

        e.method.on_return.add_callback(callback, id='foo')
        self.assertEquals(ExampleClass.method.num_callbacks, 1)
        self.assertEquals(e.method.num_callbacks, 2)

        e.method.on_return.remove_callback(id='foo')
        self.assertEquals(ExampleClass.method.num_callbacks, 1)
        self.assertEquals(e.method.num_callbacks, 1)

    def test_class_level_callbacks_fire_on_instances(self):
        called_with = []
        def callback(value):
            called_with.append(value)

        class ExampleClass(object):
            @supports_callbacks
            def method(self, value):
                pass

        # registered before instance is created
        ExampleClass.method.on_return.add_callback(callback, takes_target_args=True)
        self.assertEquals(ExampleClass.method.num_callbacks, 1)

        e = ExampleClass()
        self.assertEquals(e.method.num_callbacks, 1)

        e.method(1234)
        self.assertEquals(called_with, [1234])

    def test_instance_level_callbacks_do_NOT_fire_on_other_instances(self):
        called_with = []
        def callback(value):
            called_with.append(('inst', value))

        def class_callback(value):
            called_with.append(('cls', value))

        class ExampleClass(object):
            @supports_callbacks
            def method(self, value):
                pass

        a = ExampleClass()
        b = ExampleClass()

        ExampleClass.method.on_return.add_callback(class_callback, takes_target_args=True)
        a.method.on_return.add_callback(callback, takes_target_args=True)

        self.assertEquals(ExampleClass.method.num_callbacks, 1)

        self.assertEquals(a.method.num_callbacks, 2)
        self.assertEquals(b.method.num_callbacks, 1)

        a.method(1234)
        self.assertEquals(called_with, [('cls', 1234), ('inst', 1234)])

        b.method(4321)
        self.assertEquals(called_with, [('cls', 1234), ('inst', 1234), ('cls', 4321)])
