from transitions.extensions import LockedHierarchicalGraphMachine as Machine
from transitions.extensions.nesting import NestedState as State
from transitions.extensions.factory import NestedGraphTransition as Transition

import importlib
import logging
import inspect
import threading
from six import string_types

import rsb
import rsb.converter

logging.getLogger("rsb").setLevel(logging.WARNING)
logging.getLogger("rst").setLevel(logging.ERROR)
logging.getLogger("rstsandbox").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

import rst
import rstsandbox


class RSBTransition(Transition):

    def __init__(self, *args, **kwargs):
        self._scope = kwargs.pop('scope', None)
        msg_type = kwargs.pop('type', None)

        super(RSBTransition, self).__init__(*args, **kwargs)
        self._listener = None

        if not self._scope:
            return
        self._func = lambda: True
        if isinstance(msg_type, string_types):
            logger.info('register trype %s' % msg_type)
            cls_name = msg_type.split('.')[-1]
            x = importlib.import_module(msg_type + "_pb2")
            cls = getattr(x, cls_name)
            self.converter = rsb.converter.ProtocolBufferConverter(messageClass=cls)
            rsb.converter.registerGlobalConverter(self.converter, True)

    def _change_state(self, event_data):
        tmp = event_data.machine.current_state
        for ev in event_data.machine.events.values():
            while tmp.parent and tmp.name not in ev.transitions:
                tmp = tmp.parent
            if tmp.name in ev.transitions:
                arg = ev.transitions[tmp.name]
                t = threading.Thread(target=RSBTransition.deactivate_all,
                                     args=(arg,))
                t.start()
        super(RSBTransition, self)._change_state(event_data)
        tmp = event_data.machine.current_state
        for ev in event_data.machine.events.values():
            if tmp.name in ev.transitions:
                for e in ev.transitions[event_data.machine.current_state.name]:
                    e.activate(ev.trigger)

    @staticmethod
    def deactivate_all(transitions):
        for e in transitions:
            e.deactivate()

    def activate(self, func):
        if self._scope:
            logger.info("activate logger for scope %s" % self._scope)
            self._listener = rsb.createListener(self._scope)
            self._func = func
            self._listener.addHandler(self._on_msg)

    def deactivate(self):
        if self._scope:
            if hasattr(self, '_listener') and self._listener:
                logger.info("deactivate logger for scope %s" % self._scope)
                del self._listener

    def _on_msg(self, rsb_event):
        self._func(data=rsb_event.data)


class RSBState(State):

    def __init__(self, *args, **kwargs):
        action = kwargs.pop('action', None)
        super(RSBState, self).__init__(*args, **kwargs)
        self.action_cls = None
        self.action = None
        if action is not None:
            if isinstance(action, basestring):
                cls_name = action.split('.')[-1]
                x = importlib.import_module(action.lower()) # stick with module naming conventions
                cls = getattr(x, cls_name)
                self.action_cls = cls
            if inspect.isclass(action):
                self.action_cls = action

    def enter(self, event_data):
        super(RSBState, self).enter(event_data)
        if self.action_cls:
            self.action = self.action_cls(model=event_data.model)
            event_data.machine.callback(self.action.enter, event_data)

    def exit(self, event_data):
        if self.action:
            self.action.exit()
            del self.action
            self.action = None
        super(RSBState, self).exit(event_data)


class RSBHierarchicalStateMachine(Machine):

    @staticmethod
    def _create_state(*args, **kwargs):
        return RSBState(*args, **kwargs)

    @staticmethod
    def _create_transition(*args, **kwargs):
        return RSBTransition(*args, **kwargs)

    def shut_down(self):
        for ev in self.events.values():
            for trans_list in ev.transitions.values():
                for trans in trans_list:
                    trans.deactivate()

