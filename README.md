# rsb-transitions
Hierarchical state machine with [RSB](https://pypi.python.org/pypi/rsb-python/0.12.1) support based on [transitions](https://github.com/tyarkoni/transitions) (version >= 0.4.0).

Features include:
* full lifecycle state management
* automatic listener management for transitions
* and much [more](https://github.com/tyarkoni/transitions)

The basic usage of `rsbhsm` does not differ much from other transition state machines.

```python
from rsbhsm import RSBHierarchicalStateMachine as Machine

class Model(object):
    def well_trained():
        return True

model = Model()

states = ['stand', 'walk', 'run'] # state as strings
transitions = [
    ['acc', 'stand', 'walk'], # array transition
    {'trigger':'acc', 'source':'walk', 'dest': 'run'}, # or dictionary
    # with conditions and/or unless
    {'trigger': 'spring', 'source':'stand', 'dest': 'run', 'conditions':'well_trained'},
    # also direct function pointers
    {'trigger': 'break_required', 'source':'run', 'dest': 'stand', 'unless':model.well_trained},
    # chained processing; since previous transitions fails, this one will be executed
    {'trigger': 'break_required', 'source':'run', 'dest': 'walk'}
]

machine = Machine(model, states=states, transitions=transitions)
```

### Added features

The additional keyword for `RSBState` is `action`:

```python

states = [
    {'name': 'run', 'action':'my.action.class'}
]

```

If an `RSBState` is entered, an object of 'my.action.class' is created and destroyed whenever it is exited.
This class *must* implement an `enter` and `exit` method which will be called according to the event.

A minimal action can look like this:

```python
class BaseAction(object):

    def __init__(self, *args, **kwargs):
        self.model = kwargs['model']

    def enter(self, *args, **kwargs):
        pass

    def exit(self, *args, **kwargs):
        pass
```

The additional keywords for `RSBTransition` are `scope` and `type`:


```python
transitions = [
    {'trigger':'acc', 'source':'stand', 'dest':'walk', 'scope':'/foo/bar/baz', 'type': 'rst.generic.Value'}
]
```

`scope` defines the RSB scope and `type` the [RST](http://docs.cor-lab.org/rst-manual/trunk/html/index.html)
message type as a string. If a native type is required, use `'type':str` or similar.
A listener on this scope will be created *if and only if the transition is possible from the current state*.
Additionally, the listener will be destroyed if the transition is no longer valid.
