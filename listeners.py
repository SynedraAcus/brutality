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
    """
    
    def __init__(self, *args, layout=None, distance=10, **kwargs):
        super().__init__(*args, **kwargs)
        self._entity_id = None
        if not layout or not isinstance(layout, ScrollableECSLayout):
            raise BearLayoutException('ScrollListener should be initiated with the layout')
        if not isinstance(distance, int) or distance < 0:
            raise BearLayoutException('ScrollListener distance should be a non-negative int')
        self.layout = layout
        self.distance = distance
        
    @property
    def target_entity(self):
        return self._entity_id
    
    @target_entity.setter
    def target_entity(self, value):
        if not isinstance(value, str):
            raise BearLayoutException('ScrollListener can only focus with EntityID')
        # if not value not in self.layout.entities:
        #     raise BearECSException(f'ScrollListener attempted to focus on nonexistent entity {value}')
        self._entity_id = value
        
    def on_event(self, event):
        if event.event_type == 'brut_focus':
            self.target_entity = event.event_value
        elif event.event_type == 'ecs_move' and event.event_value[0] == self.target_entity:
            # There is no support for y-scrolling because this is a
            # side-scroller (sic) beat'em'up. If this piece of code makes it to
            # bear_hug or other project, it would be trivial to add by replacing
            # some [0]s with [1]s and x's with y's
            x = event.event_value[1]
            if x <= self.layout.view_pos[0] + self.distance:
                print('Scroll left')
                return BearEvent(event_type='ecs_scroll_by',
                                 event_value=(x - self.layout.view_pos[0], 0))
            elif x >= self.layout.view_pos[0] + self.layout.view_size[0] \
                       - self.layout.entities[self.target_entity].widget.size[0] \
                       - self.distance:
                print ('Scroll right')
                return BearEvent(event_type='ecs_scroll_by',
                                 event_value=(x + self.layout.entities[self.target_entity].widget.size[0] \
                                              - self.layout.view_pos[0] \
                                                - self.layout.view_size[0],
                                              0))
