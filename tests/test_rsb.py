try:
    from builtins import object
except ImportError:
    pass

import logging
import rsb
import rst

from rst.generic.Value_pb2 import Value
import time
from rsbhsm import RSBHierarchicalStateMachine as Machine
from rsbhsm import RSBState as State
from .utils import Stuff
from .test_threading import TestLockedHierarchicalTransitions as TestThreadedHSM
from .test_threading import heavy_processing

try:
    from unittest.mock import MagicMock
except ImportError:
    from mock import MagicMock


def condition_check(data):
    return data > 1


def condition_check_rst(data):
    return data.int > 1


class TestTransitions(TestThreadedHSM):
    TEST_SCOPE = '/test/transitions'

    def setUp(self):
        states = ['A', 'B', {'name': 'C', 'children': ['1', '2', {'name': '3', 'children': ['a', 'b', 'c']}]},
                  'D', 'E', 'F']
        self.stuff = Stuff(states, machine_cls=Machine)
        self.stuff.heavy_processing = heavy_processing
        self.stuff.machine.add_transition('process', '*', 'B', before='heavy_processing')
        self.stuff.informer = rsb.createInformer(self.TEST_SCOPE, dataType=int)
        converter = rsb.converter.ProtocolBufferConverter(messageClass=Value)
        rsb.converter.registerGlobalConverter(converter, True)
        self.stuff.informer_rst = rsb.createInformer(self.TEST_SCOPE, dataType=Value)

    def tearDown(self):
        del self.stuff.informer
        del self.stuff.informer_rst
        self.stuff.machine.shut_down()

    def test_rsb(self):
        mock = MagicMock()
        with rsb.createListener(self.TEST_SCOPE) as listener:
            listener.addHandler(mock)
            self.stuff.informer.publishData(0)
            time.sleep(0.1)
        self.assertTrue(mock.called)

    def test_condition_called(self):
        self.stuff.machine.add_transition('advance', 'A', 'B', conditions='test_condition', type=int, scope=self.TEST_SCOPE)
        self.stuff.to_A()
        self.stuff.test_condition = MagicMock()
        self.stuff.informer.publishData(0)
        time.sleep(0.1)
        self.assertTrue(self.stuff.test_condition.called)
        self.stuff.to_B()

    def test_shutdown(self):
        self.stuff.machine.add_transition('advance', 'A', 'B', conditions='test_condition', type=int, scope=self.TEST_SCOPE)
        self.stuff.to_A()
        self.stuff.machine.shut_down()

    def test_listener_init(self):
        self.stuff.machine.add_transition('advance', 'A', 'B', conditions='test_condition', type=int, scope=self.TEST_SCOPE)
        self.stuff.to_C()
        self.stuff.test_condition = MagicMock()
        self.stuff.informer.publishData(1)
        time.sleep(0.1)
        self.assertFalse(self.stuff.test_condition.called)
        self.stuff.to_B()
        self.stuff.informer.publishData(1)
        time.sleep(0.1)
        self.assertFalse(self.stuff.test_condition.called)
        self.stuff.to_A()
        self.stuff.informer.publishData(1)
        time.sleep(0.1)
        self.assertTrue(self.stuff.test_condition.called)
        self.stuff.to_B()
        self.stuff.informer.publishData(1)
        time.sleep(0.1)
        self.assertEqual(self.stuff.test_condition.call_count, 1)

    def test_listener_transition(self):
        self.stuff.condition_check = condition_check
        self.stuff.machine.add_transition('advance', 'A', 'B', conditions='condition_check', scope=self.TEST_SCOPE)
        self.stuff.to_A()
        self.stuff.informer.publishData(0)
        time.sleep(0.1)
        self.assertTrue(self.stuff.machine.is_state('A'))
        self.stuff.informer.publishData(2)
        time.sleep(0.1)
        self.assertTrue(self.stuff.machine.is_state('B'))
        self.stuff.to_C()

    def test_listener_rst(self):
        self.stuff.condition_check_rst = condition_check_rst
        val = Value()
        val.type = val.INT
        val.int = 0
        self.stuff.machine.add_transition('advance', 'A', 'B', conditions='condition_check_rst', type='rst.generic.Value', scope=self.TEST_SCOPE)
        self.stuff.to_A()
        self.stuff.informer_rst.publishData(val)
        time.sleep(0.1)
        self.assertTrue(self.stuff.machine.is_state('A'))
        val.int = 2
        self.stuff.informer_rst.publishData(val)
        time.sleep(0.1)
        self.assertTrue(self.stuff.machine.is_state('B'))
        self.stuff.to_C()

    def test_rsb_state(self):
        state = State('X', action=MagicMock)
        self.stuff.machine.add_state(state)
        self.assertIsNone(state.action)
        self.assertIsNotNone(state.action_cls)
        self.stuff.to_X()
        self.assertIsNotNone(state.action)
        self.assertEqual(state.action.enter.call_count, 1)
        self.assertFalse(state.action.exit.called)
        self.stuff.to_A()
        self.assertIsNone(state.action)
        states = [{'name': 'Y',
                  'action': MagicMock}]
        machine = Machine(states=states)

    def test_rsb_action_string(self):
        state = State('X', action='mock.MagicMock')
        self.stuff.machine.add_state(state)
        self.assertIsNone(state.action)
        self.assertIsNotNone(state.action_cls)
        self.stuff.to_X()
        self.assertIsNotNone(state.action)
        self.assertEqual(state.action.enter.call_count, 1)
        self.assertFalse(state.action.exit.called)
        states = [{'name': 'Y',
                  'action': 'mock.MagicMock'}]
        machine = Machine(states=states)

    def test_custom_state(self):

        class StateAction(object):

            def __init__(self, model):
                self.model = model

            def enter(self, foo):
                print foo
                if not isinstance(self.model, Stuff) or 'foo' not in foo:
                    raise ValueError

            def exit(self):
                self.model.is_exited = True

        state = State('X', action=StateAction)
        self.stuff.machine.add_state(state)
        self.stuff.machine.add_transition('foo', '*', 'X')
        self.stuff.foo('foo')
        self.stuff.to_A()
        with self.assertRaises(ValueError):
            self.stuff.foo('bar')
        self.stuff.to_A()
        self.assertTrue(self.stuff.is_exited)

    def test_pickle(self):
        pass
