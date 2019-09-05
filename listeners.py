"""
Things that should somehow interact with the events, but are too simple to
merit a complete entity
"""

from bear_hug.bear_utilities import BearLayoutException
from bear_hug.ecs_widgets import ScrollableECSLayout
from bear_hug.event import BearEvent
from bear_hug.widgets import Listener


class ScrollListener(Listener):
    """
    A listener that keeps ScrollableECSLayout focused on an entity.
    Keeps a ScrollableECSLayout reference and an entity ID.
    Orders Layout view to move, if possible, whenever the entity in question
    gets too close to left or right edge.
    Ordering is done via events; in general, this listener uses Layout reference
    only to collect data (eg check if entity IDs are valid or get current
    viewport), but all activity is performed via 'ecs_*' events
    
    Reacts to the following events:
    `BearEvent(event_type='brut_focus', event_value=entity_id)`:
    focus on a given entity so that a screen will track its movements. Can
    accept the IDs of entities that don't currently exist, but will not scroll
    until the entity with this ID does a movement.
    
    `BearEvent(event_type='brut_temporary_focus', event_value=entity_id)`:
    focus on a given entity so that a screen will track its movements; when it
    is destroyed (as evidenced by 'ecs_destroy' event), returns focus to
    whatever it was focused on before and scroll back to wherever the screen was
    before initiating temporary focus. Does not support recursive re-focusing;
    if temporary focus is called while already in temporary focusing mode, the
    screen will track a new target, but upon entity destruction it will return
    to the original target and position, not to the previous temporary one.
    
    `BearEvent(event_type='ecs_destroy')` and `BearEvent(event_type='ecs_move')`
     are necessary for this Listener to work, but should not be used to interact
     with it.
    """
    #TODO: remove distinction between brut_focus and brut_temporary_focus
    # Brut_focus will get stuck if the focused entity is destroyed; it is
    # probably better to have only brut_temporary_focus, but extend it with
    # potentially infinite chain of old targets a-la call stack
    def __init__(self, *args, layout=None, distance=10, **kwargs):
        super().__init__(*args, **kwargs)
        self._entity_id = None
        if not layout or not isinstance(layout, ScrollableECSLayout):
            raise BearLayoutException('ScrollListener should be initiated with the layout')
        if not isinstance(distance, int) or distance < 0:
            raise BearLayoutException('ScrollListener distance should be a non-negative int')
        self.layout = layout
        self.distance = distance
        self.old_target = None
        self.old_pos = None
        
    @property
    def target_entity(self):
        return self._entity_id
    
    @target_entity.setter
    def target_entity(self, value):
        if not isinstance(value, str):
            raise BearLayoutException('ScrollListener can only focus with EntityID')
        self._entity_id = value
        
    def on_event(self, event):
        if event.event_type == 'brut_focus':
            self.target_entity = event.event_value
        elif event.event_type == 'brut_temporary_focus':
            # Set focus on the entity; when this entity is removed, return it to
            # whatever was focused on before
            if not self.old_target:
                self.old_target = self.target_entity
            self.target_entity = event.event_value
            self.old_pos = [x for x in self.layout.view_pos]
        elif event.event_type == 'ecs_destroy' and  \
                    event.event_value == self.target_entity \
                    and self.old_target is not None:
            # Return focus to the old target and scroll back to it
            self.target_entity = self.old_target
            self.old_target = None
            return BearEvent(event_type='ecs_scroll_to',
                             event_value=(self.old_pos))
        elif event.event_type == 'ecs_move' and event.event_value[0] == self.target_entity:
            # There is no support for y-scrolling because this is a
            # side-scrolling (sic) beat'em'up. If this piece of code makes idt to
            # bear_hug or other project, it would be trivial to add by replacing
            # some [0]s with [1]s and x's with y's
            x = event.event_value[1]
            if x <= self.layout.view_pos[0] + self.distance:
                return BearEvent(event_type='ecs_scroll_by',
                                 event_value=(x - self.distance - self.layout.view_pos[0], 0))
            elif x >= self.layout.view_pos[0] + self.layout.view_size[0] \
                       - self.layout.entities[self.target_entity].widget.size[0] \
                       - self.distance:
                return BearEvent(event_type='ecs_scroll_by',
                                 event_value=(x + self.layout.entities[self.target_entity].widget.size[0] \
                                              - self.layout.view_pos[0] + self.distance \
                                                - self.layout.view_size[0],
                                              0))


# Copypasting SO is the only correct way to program
# https://stackoverflow.com/questions/6760685/creating-a-singleton-in-python
class Singleton(type):
    _instances = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args,
                                                                 **kwargs)
        return cls._instances[cls]


class EntityTracker(Listener, metaclass=Singleton):
    """
    Listens to the ecs_add and ecs_destroy events and keeps track of all the
    currently existing entities.
    
    This tracker is used for entity lookup, eg by Components that need to find
    all possible entities that fulfill certain criteria
    """
    def __init__(self):
        super().__init__()
        self.entities = {}
        
    def on_event(self, event):
        if event.event_type == 'ecs_create':
            self.entities[event.event_value.id] = event.event_value
        elif event.event_type == 'ecs_destroy':
            del self.entities[event.event_value]
            
    def filter_entities(self, key=lambda x: x):
        """
        Return all entities for which key evaluates to True.
        
        Note that this method returns entity objects themselves, not the IDs.
        :param key: A single-arg callable
        :return:
        """
        if not hasattr(key, '__call__'):
            raise ValueError('EntityTracker requires callable for a key')
        for entity_id in self.entities:
            if key(self.entities[entity_id]):
                yield self.entities[entity_id]


class SavingListener(Listener):
    """
    A Listener class that waits for a signal (currently keypress 'TK_F5') and,
    upon getting this signal, attempts to serialize all entities available
    from EntityTracker()
    """

    def on_event(self, event):
        if event.event_type == 'key_down' and event.event_value == 'TK_F5':
            with open('save.json', mode='w') as savefile:
                for entity in EntityTracker().filter_entities():
                    print(repr(entity), file=savefile)
