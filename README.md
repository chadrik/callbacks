Callbacks lets you use decorator syntax to set callbacks on methods or functions.

```python
from callbacks import supports_callbacks

def callback():
    print "Polly!"

@supports_callbacks
def target():
    print "hello",

target.add_callback(callback)

target() # prints "hello Polly!"
```

When called with no arguments `@supports_callbacks` sets up three callback events
which are automatically fired when your function is called:
- `on_call`
- `on_return`
- `on_exeception`

This is great if you don't want to modify existing code to support callbacks,
but if you need more control over when events are fired, or you want to create
your own events, you can do that too:


```python
from callbacks import supports_callbacks, ReturnEvent

def iter_callback(i):
    print i

def result_callback(result):
    print result 

@supports_callbacks('on_iteration', pass_args=True)
@supports_callbacks('on_return', ReturnEvent, pass_result=True)
def pair_range(num):
    result = []
    for i in range(num):
        pair_range.on_iteration.emit(i)
        result.append((i, i + 1))
    pair_range.on_return.emit(target_result=result)
    return result

pair_range.on_iteration.add_callback(iter_callback)
pair_range.on_return.add_callback(result_callback)
pair_range()
```


[![Build Status](https://secure.travis-ci.org/davidlmorton/callbacks.svg?branch=master)](https://travis-ci.org/davidlmorton/callbacks)
[![Coverage Status](https://img.shields.io/coveralls/davidlmorton/callbacks.svg)](https://coveralls.io/r/davidlmorton/callbacks)
