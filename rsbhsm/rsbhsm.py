from transitions.extensions import LockedHierarchicalGraphMachine as Machine
from transitions.extensions.nesting import NestedState as State
from transitions.extensions.factory import NestedGraphTransition as Transition
from transitions.extensions.factory import LockedNestedEvent as Event

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

# used in dynamic rst message generation
import rst
import rstsandbox


class RSBEvent(Event):

    def __init__(self, *args, **kwargs):
        super(RSBEvent, self).__init__(*args, **kwargs)
        self._listeners = {}

    def activate(self, scope):
        if scope not in self._listeners:
            logger.info("activate logger for scope %s" % scope)
            self._listeners[scope] = rsb.createListener(scope)
            self._listeners[scope].addHandler(self._on_msg)

    def deactivate(self, scope=None):
        if scope is None:
            for s, listener in self._listeners.items():
                logger.info("deactivate logger for scope %s" % s)
                l = self._listeners.pop(s, None)
                if l:
                    del l
        elif scope in self._listeners:
            logger.info("deactivate logger for scope %s" % scope)
            l = self._listeners.pop(scope, None)
            if l:
                del l

    def _on_msg(self, rsb_event):
        self.trigger(data=rsb_event.data)


class RSBTransition(Transition):

    def __init__(self, *args, **kwargs):
        self.scope = kwargs.pop('scope', None)
        msg_type = kwargs.pop('type', None)

        super(RSBTransition, self).__init__(*args, **kwargs)
        self._listener = None

        if not self.scope:
            return
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
                                     args=(arg, ev))
                t.start()
        super(RSBTransition, self)._change_state(event_data)
        tmp = event_data.machine.current_state
        for ev in event_data.machine.events.values():
            if tmp.name in ev.transitions:
                trans = ev.transitions[tmp.name]
                for t in trans:
                    if t.scope:
                        ev.activate(t.scope)

    @staticmethod
    def deactivate_all(transitions, event):
        for e in transitions:
            event.deactivate(e.scope)


class RSBState(State):

    def __init__(self, *args, **kwargs):
        action = kwargs.pop('action', None)
        super(RSBState, self).__init__(*args, **kwargs)
        self.action_cls = None
        self.action = None
        if action is not None:
            if isinstance(action, basestring):
                arr = action.split('.')
                cls_name = arr[-1]
                module_name = '.'.join(arr[:-1])
                module = importlib.import_module(module_name.lower())  # stick with module naming conventions
                cls = getattr(module, cls_name)
                self.action_cls = cls
            if inspect.isclass(action):
                self.action_cls = action

    def enter(self, event_data):
        super(RSBState, self).enter(event_data)
        if self.action_cls:
            self.action = self.action_cls(model=event_data.model)
            event_data.machine._callback(self.action.enter, event_data)

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

    @staticmethod
    def _create_event(*args, **kwargs):
        return RSBEvent(*args, **kwargs)

    def shut_down(self):
        for ev in self.events.values():
            ev.deactivate()

