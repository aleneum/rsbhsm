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

# used in dynamic rst message generation
import rst
import rstsandbox

logging.getLogger("rsb").setLevel(logging.WARNING)
logging.getLogger("rst").setLevel(logging.ERROR)
logging.getLogger("rstsandbox").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class RSBEvent(Event):

    def __init__(self, *args, **kwargs):
        self.scope = None
        self.listener = None
        super(RSBEvent, self).__init__(*args, **kwargs)

    def set_rsb(self, scope, msg_type=None):
        if self.scope and scope is not self.scope:
            raise ValueError('Scope has been set already and cannot be reassigned')
        self.scope = scope
        if isinstance(msg_type, string_types):
            logger.info('register trype %s' % msg_type)
            cls_name = msg_type.split('.')[-1]
            x = importlib.import_module(msg_type + "_pb2")
            cls = getattr(x, cls_name)
            converter = rsb.converter.ProtocolBufferConverter(messageClass=cls)
            rsb.converter.registerGlobalConverter(converter, True)

    def activate(self):
        if self.scope is not None and self.listener is None:
            logger.info("activate logger for scope %s" % self.scope)
            self.listener = rsb.createListener(self.scope)
            self.listener.addHandler(self._on_msg)

    def deactivate(self):
        if self.listener is not None:
            logger.info("deactivate logger for scope %s" % self.scope)
            self.listener, tmp = None, self.listener
            del tmp

    def _on_msg(self, rsb_event):
        for model in self.machine.models:
            self.trigger(model, data=rsb_event.data)


class RSBTransition(Transition):

    def __init__(self, *args, **kwargs):
        super(RSBTransition, self).__init__(*args, **kwargs)

    def _change_state(self, event_data):
        trigger_src = event_data.machine.get_triggers(self.source)
        trigger_dst = event_data.machine.get_triggers(self.dest)

        evs = []
        for t in trigger_src:
            if t not in trigger_dst:
                evs.append(event_data.machine.events[t])

        threading.Thread(target=RSBTransition.deactivate,
                         args=(evs,)).start()

        super(RSBTransition, self)._change_state(event_data)
        for t in trigger_dst:
            event_data.machine.events[t].activate()

    @staticmethod
    def deactivate(events):
        for e in events:
            e.deactivate()


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

    def add_transition(self, *args, **kwargs):
        scope = kwargs.pop('scope', None)
        msg_type = kwargs.pop('type', None)
        super(RSBHierarchicalStateMachine, self).add_transition(*args, **kwargs)
        trigger_name = kwargs['trigger'] if 'trigger' in kwargs else args[0]
        self.events[trigger_name].set_rsb(scope, msg_type)

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
