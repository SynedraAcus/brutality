"""
Things that should somehow interact with the events, but are too simple to
merit a complete entity, or to complicated to be limited to one.
"""

from collections import namedtuple
from json import dump, load

from bear_hug.bear_utilities import BearLayoutException, rectangles_collide, \
    copy_shape
from bear_hug.ecs import EntityTracker, Singleton
from bear_hug.ecs_widgets import ScrollableECSLayout
from bear_hug.event import BearEvent
from bear_hug.sound import SoundListener
from bear_hug.widgets import Widget, Listener, MenuWidget

from widgets import TypingLabelWidget


class ScrollListener(Listener, metaclass=Singleton):
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
     with it directly.

     This Listener is a singleton, and creating more than one is impossible.
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
        elif event.event_type == 'tick':
            # Each tick, check that the tracked entity does not happen to be
            # outside the screen. This can happen, for example, after loading
            # the game from save, where view is set to the default position of 0
            # regardless of where it has been before. Or after processing some
            # 'ecs_scroll*' events coming from outside this class.
            try:
                x = EntityTracker().entities[self.target_entity].position.x
                xsize = EntityTracker().entities[self.target_entity].widget.width
            except KeyError:
                # Do nothing if entity no longer exists (possible when PC is
                # destroyed and leaves a corpse)
                return
            if x + xsize <= self.layout.view_pos[0]:
                x_scroll = x - self.distance - self.layout.view_pos[0]
                if abs(x_scroll) > self.layout.view_pos[0]:
                    x_scroll = -1 * self.layout.view_pos[0]
                return BearEvent(event_type='ecs_scroll_by',
                                 event_value=(x_scroll, 0))
            elif x >= self.layout.view_pos[0] + self.layout.view_size[0] \
                       - self.layout.entities[self.target_entity].widget.size[0]:
                return BearEvent(event_type='ecs_scroll_by',
                                 event_value=(x + self.layout.entities[self.target_entity].widget.size[0] \
                                              - self.layout.view_pos[0] + self.distance \
                                              - self.layout.view_size[0],
                                              0))
        elif event.event_type == 'ecs_move' and event.event_value[0] == self.target_entity:
            # Routine scrolling is done here and not in tick, because otherwise
            # it causes following bug: character is moved 2 chars to the right
            # by step, the game moves him 2 chars relative to the monitor, then
            # on the next tick this class notices the need to scroll and moves
            # view 2 chars right, thus needing to move character to the left
            # relative to the monitor. Thus ugly stuttering. This does not
            # happen when this class gets its 'tick' event before the ECSLayout,
            # but I can't have something dependent on the order in which things
            # process the same event.
            x = event.event_value[1]
            # There is no support for y-scrolling because this is a sidescroller
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


# This data class contains all information about what should be spawned and when
# Attributes are: `item` (str) for item type, `pos` (tuple of ints) for upper
# left corner of region where a player must walk to trigger this item, `size`
# (tuple of ints) for the size of this region, and `kwargs` (dict) for any
# kwargs that should be passed to factory during item creation
SpawnItem = namedtuple('SpawnItem', ('item', 'pos', 'size', 'kwargs'))


class SpawningListener(Listener, metaclass=Singleton):
    """
    Spawns items when player walks into a predefined area.

    :param player_entity: Str. Player entity ID; this Listener will create
    entities when this entity walks into predefined areas

    :param factory: MapObjectFactory instance

    :param spawns: an iterable of SpawnItem instances
    """
    def __init__(self, player_entity_id,
                 factory=None, spawns=None, **kwargs):
        super().__init__(**kwargs)
        self.spawns = []
        if spawns:
            for item in self.spawns:
                if not isinstance(item, SpawnItem):
                    raise TypeError(f'{type(item)} supplied to SpawningListener instead of SpawnItem')
                self.spawns.append(item)
        self.factory = factory
        self.player_id = player_entity_id
        # To be set during the first event
        self.player_entity = None

    def set_player(self, value):
        """
        Set tracked entity ID to `value`.

        This method assumes that entity already exists and is known to
        EntityTracker when it is called.
        :param value:
        :return:
        """
        entity = EntityTracker().entities[value]
        self.player_id = entity
        self.player_entity = entity

    def add_spawn(self, item):
        """
        Add a single SpawnItem to this Listener

        :param item: SpawnItem
        :return:
        """
        if not isinstance(item, SpawnItem):
            raise TypeError(f'{type(item)} supplied to SpawningListener instead of SpawnItem')
        self.spawns.append(item)

    def add_spawns_iterable(self, spawns):
        """
        Add a group of SpawnItems to this listener
        :param spawns: an iterable of SpawnItem
        :return:
        """
        for item in spawns:
            self.add_spawn(item)

    def remove_spawns(self, filter=lambda x: True):
        """
        Remove all spawns for which filter returns True-ish value

        :param filter: callable which accepts a single argument
        :return:
        """
        # Copy list to avoid all weirdness caused by changing list while
        # iterating over it
        tmp_list = [x for x in self.spawns]
        for spawn in tmp_list:
            if filter(spawn):
                self.spawns.remove(spawn)

    def on_event(self, event):
        if event.event_type == 'ecs_move' and \
                    event.event_value[0] == self.player_id:
            if not self.player_entity:
                self.player_entity = EntityTracker().entities[self.player_id]
            for spawn in self.spawns:
                try:
                    if rectangles_collide(spawn.pos, spawn.size,
                                          self.player_entity.position.pos,
                                          self.player_entity.widget.size):
                        self.factory.create_entity(spawn.item,
                                                   # Spawn in the middle
                                                   (int(spawn.pos[0]+spawn.size[0]/2),
                                                    int(spawn.pos[1]+spawn.size[1]/2)),
                                                   **spawn.kwargs)
                        self.spawns.remove(spawn)
                except AttributeError:
                    # Sometimes it interacts with half-destroyed entities during
                    # level switch process. 
                    pass


class SavingListener(Listener):
    """
    A Listener class that waits for a ''brut_save_game'' event and saves

    Serializes all existing entities, LevelSwitchListener state and spawns in
    the SpawnListener.
    """
    def on_event(self, event):
        if event.event_type == 'brut_save_game':
            r = {}
            # Saving entities
            r['entities'] = [repr(entity) for entity in EntityTracker().entities.values()]
            # Saving listeners
            r['level_switch_state'] = LevelSwitchListener().get_state()
            r['current_level'] = LevelSwitchListener().current_level
            # Loading spawns from SpawnListener
            r['spawns'] = SpawningListener().spawns
            r['bg_sound'] = SoundListener().bg_sound
        dump(r, open(event.event_value, mode='w'))


class LoadingListener(Listener):
    """
    A Listener class that waits for a 'brut_load_game' event and loads

    Deserializes stuff from a file and sets attributes for various listeners.
    """
    def __init__(self, dispatcher, factory, levelgen, loop, **kwargs):
        super().__init__(**kwargs)
        self.dispatcher = dispatcher
        self.factory = factory
        self.levelgen = levelgen
        self.loop = loop

    def on_event(self, event):
        if event.event_type == 'brut_load_game':
            self.levelgen.destroy_current_level(destroy_player=True)
            # creating variables for the singletons to avoid running through
            # object creation when they are used
            level_switch = LevelSwitchListener()
            spawner = SpawningListener()
            spawner.player_entity = None
            level_switch.player_entity = None
            level_switch.player_id = None
            save = load(open(event.event_value))
            for line in save['entities']:
                self.factory.load_entity_from_JSON(line)
            # Make all entities available for EntityTracker
            self.loop._run_iteration(0)
            for attr in save['level_switch_state']:
                level_switch.__dict__[attr] = save['level_switch_state'][attr]
            self.levelgen.current_level = save['current_level']
            spawner.spawns = [SpawnItem(*x) for x in save['spawns']]
            # Fixes and workarounds to display everything correctly on the first
            # frame
            self.dispatcher.add_event(BearEvent('brut_focus', 'cop_1'))
            # Set correct z-order for the cop
            cop_entity = EntityTracker().entities['cop_1']
            z = cop_entity.position.y + cop_entity.widget.height
            cop_entity.widget.widget.z_level = z
            # Pseudo-events to redraw items in the HUD
            left_item = cop_entity.hands.left_item
            right_item = cop_entity.hands.right_item
            EntityTracker().entities[left_item].hiding.hide()
            EntityTracker().entities[right_item].hiding.hide()
            self.dispatcher.add_event(
                BearEvent('brut_pick_up',
                          ('cop_1', 'left', f'{left_item}_pseudo')))
            self.dispatcher.add_event(
                BearEvent('brut_pick_up',
                          ('cop_1', 'right', f'{right_item}_pseudo')))
            self.dispatcher.add_event(BearEvent('set_bg_sound',
                                                save['bg_sound']))
            # Make sure all fixes got processed
            self.loop._run_iteration(0)


class LevelSwitchListener(Listener, metaclass=Singleton):
    """
    Changes level when player walks into a predefined area.

    This Listener is a singleton, and creating more than one is impossible.

    Currently only able to switch them in a fixed sequence.
    """
    def __init__(self, player_id,  current_level=None,
                 level_manager=None, level_sequence={}, **kwargs):
        # This will permit multiple exits per level
        super().__init__(**kwargs)
        self.player_id = player_id
        self.player_entity = None
        # LevelManager type not checked to avoid circular import
        self.level_manager = level_manager
        self.current_level = current_level
        for x in level_sequence:
            if x not in self.level_manager.methods:
                raise ValueError(f'Invalid level {x} supplied to LevelSwitchListener')
        self.level_sequence = level_sequence
        self.enabled = True
        self.is_changing = False
        self.next_level = None

    def on_event(self, event):
        if not self.enabled:
            return
        if event.event_type == 'ecs_move' and \
                event.event_value[0] == self.player_id:
            if not self.player_entity:
                self.player_entity = EntityTracker().entities[self.player_id]
        # TODO: a delay between levels to let sound play out
        # maybe show something? Like an image? Lots of work to draw, though
        # Maybe some text re: objectives
        elif event.event_type == 'ecs_collision' and event.event_value[0] == self.player_id:
            if event.event_value[1] and 'level_switch' in event.event_value[1]:
                self.is_changing = True
                self.next_level = EntityTracker().entities[event.event_value[1]].level_switch.next_level
                return BearEvent('play_sound', 'drive')
        elif event.event_type == 'tick' and self.is_changing:
            self.is_changing = False
            # next_level = self.level_sequence[self.current_level]
            self.level_manager.set_level(self.next_level)
            self.next_level = None

    def disable(self):
        """
        Do not use LevelSwitchListener on current level
        """
        self.enabled = False

    def enable(self):
        """
        Use LevelSwitchListener on current level
        """
        self.enabled = True

    def get_state(self):
        return {'player_id': self.player_id,
                'switch_pos': self.switch_pos,
                'switch_size': self.switch_size,
                'level_sequence': self.level_sequence,
                'current_level': self.current_level,
                'enabled': self.enabled}


class MenuListener(Listener):
    """
    Responsible for showing the menu when need be.

    When activated, displays the menu widget on layer 3 and black screen under
    it on layer 2 (to help with transparency issues). Menu widget is also
    automatically subscribed to the
    ``['tick', 'service', 'key_down', 'misc_input']`` events. When menu is
    hidden, removes all the Widgets from terminal. MenuWidget is not destroyed,
    but is unsubscribed from all events.

    This listener is activated/inactivated either directly by ``'TK_ESCAPE'``
    keypress in a ``'key_down'`` event (which also has a delay of 0.1 sec
    between opening and closing a menu) or via ``'brut_open_menu'`` and
    ``'brut_close_menu'`` events, any number of which can be processed even in a
    single frame.
    """
    def __init__(self, dispatcher, terminal, menu_widget, *args,
                 menu_pos = (5,5), **kwargs):
        super().__init__(*args, **kwargs)
        self.dispatcher = dispatcher
        self.dispatcher.register_listener(self, 'key_down')
        self.terminal = terminal
        if not isinstance(menu_widget, MenuWidget):
            raise TypeError(f'{type(menu_widget)} supplied to MenuListener instead of MenuWidget')
        self.menu_widget = menu_widget
        screen_chars = [['\u2588' for x in range(self.menu_widget.width)]
                        for y in range(self.menu_widget.height)]
        screen_colors = copy_shape(screen_chars, 'black')
        self.screen_widget = Widget(screen_chars, screen_colors)
        self.menu_pos = menu_pos
        self.currently_showing = False
        self.input_delay = 0.3
        self.current_delay = 0

    def on_event(self, event):
        if event.event_type == 'tick' and self.current_delay <= self.input_delay:
            self.current_delay += event.event_value
        elif event.event_type == 'key_down' \
                and event.event_value == 'TK_ESCAPE' \
                and self.current_delay >= self.input_delay:
            self.current_delay = 0
            if not self.currently_showing:
                self.show_menu()
            else:
                self.hide_menu()
        elif event.event_type == 'brut_open_menu' and not self.currently_showing:
            self.show_menu()
        elif event.event_type == 'brut_close_menu' and self.currently_showing:
            self.hide_menu()

    def show_menu(self):
        self.terminal.add_widget(self.menu_widget, self.menu_pos, layer=3)
        self.terminal.add_widget(self.screen_widget, self.menu_pos, layer=2)
        self.dispatcher.register_listener(self.menu_widget,
                                          ['tick', 'service',
                                           'misc_input', 'key_down'])
        self.currently_showing = True
        self.dispatcher.add_event(BearEvent('play_sound', 'item_grab'))
        # Disabling character input
        try:
            EntityTracker().entities['cop_1'].controller.accepts_input = False
        except KeyError:
            pass

    def hide_menu(self):
        self.terminal.remove_widget(self.menu_widget)
        self.terminal.remove_widget(self.screen_widget)
        self.dispatcher.unregister_listener(self.menu_widget, 'all')
        self.currently_showing = False
        self.dispatcher.add_event(BearEvent('play_sound', 'item_drop'))
        for entity in EntityTracker().filter_entities(lambda x: x.id=='cop_1'):
            entity.controller.accepts_input = True


class ItemDescriptionListener(Listener):
    """
    Waits for `brut_show_items` and `brut_close_menu` events. On former,
    displays TypingLabelWidget with item descriptions; on latter, hides it.

    Displays on Layer 4, above the menu
    :param Listener:
    :return:
    """
    def __init__(self, dispatcher, terminal,  tracked_entity='cop_1',
                 text_pos=(25, 12), **kwargs):
        self.register_terminal(terminal)
        self.dispatcher = dispatcher
        self.dispatcher.register_listener(self, ['brut_show_items',
                                                 'brut_close_menu'])
        self.tracked_entity = tracked_entity
        self.text_pos = text_pos
        self.text_mask = 'LEFT: {}\n\n{}\n\nRIGHT: {}\n\n{}'
        self.widget = None
        self.is_showing = False

    def on_event(self, event):
        if event.event_type == 'brut_show_items' and not self.is_showing:
            self.is_showing = True
            # Generating text
            try:
                e = EntityTracker().entities[self.tracked_entity]
                left = EntityTracker().entities[e.hands.left_item]
                right = EntityTracker().entities[e.hands.right_item]
                text = self.text_mask.format(left.item_behaviour.item_name,
                                             left.item_behaviour.item_description,
                                             right.item_behaviour.item_name,
                                             right.item_behaviour.item_description)
            except KeyError:
                # Probably tried to read the inventory from nonexistent entity
                # Ie the cop that was killed
                text = 'Corpses don\'t have any\nitems.'
            chars = [[' ' for _ in range(28)] for _ in range(23)]
            colors = copy_shape(chars, '#000000')
            self.widget = TypingLabelWidget(chars, colors,
                                            chars_per_second=40,
                                            text=text,
                                            just='left', color='white')
            self.terminal.add_widget(self.widget, self.text_pos, layer=4)
            self.dispatcher.register_listener(self.widget, 'tick')
        elif (event.event_type == 'brut_close_menu' or
              (event.event_type=='key_down' and event.event_value == 'TK_ESCAPE'))\
                and self.is_showing:
            # Menu is closed, hide this widget
            self.is_showing = False
            self.terminal.remove_widget(self.widget)
            self.dispatcher.unregister_listener(self.widget, 'all')


class ScoreListener(Listener):
    """
    A listener that keeps track of the score.

    It orders score_widget to redraw itself as necessary and emits healing
    events.
    """
    def __init__(self, *args, terminal,
                 dispatcher,
                 score_widget,
                 score=0,
                 player_entity='cop_1',
                 heal_frequency=50,
                 healing=1,
                 **kwargs):
        super().__init__()
        self.dispatcher = dispatcher
        self.terminal = terminal
        self.score_widget = score_widget
        self.player_entity = player_entity
        self.heal_frequency = heal_frequency
        self.healing = healing
        self.score = score
        self.last_heal = 0
        self.is_highlighting = False
        self.highlighted_for = 0

    def on_event(self, event):
        if event.event_type == 'brut_reset_score':
            self.score = event.event_value
            self.score_widget.score = self.score
            self.terminal.update_widget(self.score_widget)
        elif event.event_type == 'brut_score':
            self.score += event.event_value
            self.score_widget.score = self.score
            self.terminal.update_widget(self.score_widget)
            if self.score // self.heal_frequency > self.last_heal:
                self.last_heal = self.score // self.heal_frequency
                self.dispatcher.add_event(BearEvent('brut_heal',
                                                    (self.player_entity, 1)))
                # Blink score widget
                self.score_widget.colors = [['green' for _ in range(5)]]
                self.terminal.update_widget(self.score_widget)
                self.is_highlighting = True
                self.highlighted_for = 0
        elif event.event_type == 'tick' and self.is_highlighting:
            self.highlighted_for += event.event_value
            if self.highlighted_for >= 0.5:
                self.score_widget.colors = [['#9E9E9E' for _ in range(5)]]
                self.terminal.update_widget(self.score_widget)
                self.is_highlighting = False
