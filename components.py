from collections import OrderedDict
from json import dumps, loads
from math import sqrt
from random import randint

from bear_hug.bear_utilities import BearECSException, rectangles_collide
from bear_hug.ecs import Component, PositionComponent, BearEvent, \
    WidgetComponent, Entity
from bear_hug.ecs_widgets import ScrollableECSLayout, ECSLayout
from bear_hug.widgets import SwitchingWidget

from listeners import EntityTracker


class WalkerComponent(PositionComponent):
    """
    A simple PositionComponent that can change x;y on keypress
    """
    
    def __init__(self, *args, direction='r', initial_phase='1', **kwargs):
        super().__init__(*args, **kwargs)
        self.dispatcher.register_listener(self, ['key_down', 'tick'])
        self.last_move = None
        self.direction = direction
        self.phase = initial_phase
        self.moved_this_tick = False
        
    def walk(self, move):
        if self.moved_this_tick:
            return
        self.relative_move(*move)
        self.last_move = move
        self.moved_this_tick = True
        if move[0] > 0:
            self.direction = 'r'
        elif move[0] < 0:
            self.direction = 'l'
        # If move[0] == 0, the direction stays whatever it was, move is vertical
        # TODO: Support more than two phases of movement
        if self.phase == '1':
            self.phase = '2'
        else:
            self.phase = '1'
        self.owner.widget.switch_to_image(f'{self.direction}_{self.phase}')
    
    def on_event(self, event):
        if event.event_type == 'tick':
            self.moved_this_tick = False
        return super().on_event(event)
            
    def __repr__(self):
        d = loads(super().__repr__())
        {}.update({'direction': self.direction,
                   'initial_phase': self.phase})
        return dumps(d)


class GravityPositionComponent(PositionComponent):
    """
    A PositionComponent that maintains a constant downward acceleration.

    accepts `acceleration` (in characters per second squared) as a kwarg.
    Defaults to 10.0
    """
    def __init__(self, *args, acceleration=10.0, have_waited=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.acceleration = acceleration
        self.update_freq = 1/acceleration
        self.have_waited = have_waited
        self.dispatcher.register_listener(self, 'tick')

    def on_event(self, event):
        if event.event_type == 'tick':
            self.have_waited += event.event_value
        if self.have_waited >= self.update_freq:
            self.vy += 1
            self.have_waited = 0
        return super().on_event(event)

    def __repr__(self):
        d = loads(super().__repr__())
        {}.update({'acceleration': self.acceleration,
                   'have_waited': self.have_waited})
        return dumps(d)


class CollisionComponent(Component):
    """
    A component responsible for processing collisions of this object
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, name='collision', **kwargs)
        self.dispatcher.register_listener(self, 'ecs_collision')

    def on_event(self, event):
        if event.event_type == 'ecs_collision':
            if event.event_value[0] == self.owner.id:
                self.collided_into(event.event_value[1])
            elif event.event_value[1] == self.owner.id:
                self.collided_by(event.event_value[0])

    def collided_into(self, entity):
        pass
    
    def collided_by(self, entity):
        pass


class WalkerCollisionComponent(CollisionComponent):
    """
    A collision component that, upon colliding into something impassable,
    moves the entity to where it came from. Expects both entities involved to
    have a PassabilityComponent
    """

    def collided_into(self, entity):
        if entity is not None:
            other = EntityTracker().entities[entity]
            if 'passability' in self.owner.__dict__ and 'passability' in other.__dict__:
                if rectangles_collide((self.owner.position.x + self.owner.passability.shadow_pos[0],
                                       self.owner.position.y + self.owner.passability.shadow_pos[1]),
                                      self.owner.passability.shadow_size,
                                      (other.position.x + other.passability.shadow_pos[0],
                                       other.position.y + other.passability.shadow_pos[1]),
                                      other.passability.shadow_size):
                    self.owner.position.relative_move(self.owner.position.last_move[0] * -1,
                                                      self.owner.position.last_move[1] * -1)
        else:
            # Processing collisions with screen edges without involving passability
            self.owner.position.relative_move(
                self.owner.position.last_move[0] * -1,
                self.owner.position.last_move[1] * -1)


class ProjectileCollisionComponent(CollisionComponent):
    """
    A collision component that damages whatever its owner is collided into
    """
    
    def __init__(self, *args, damage=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.damage = damage
        
    def collided_into(self, entity):
        if not entity:
            self.owner.destructor.destroy()
        elif hasattr(EntityTracker().entities[entity], 'collision'):
            self.dispatcher.add_event(BearEvent(event_type='brut_damage',
                                                event_value=(entity, self.damage)))
            self.owner.destructor.destroy()
        
    def __repr__(self):
        d = loads(super().__repr__())
        d['damage'] = self.damage
        return dumps(d)


class PassingComponent(Component):
    """
    A component responsible for knowing whether items can or cannot be walked
    through.
    
    Unlike collisions of eg projectiles, walkers can easily collide with screen
    items and each other provided they are "behind" or "ahead" of each other. To
    check for that, PassingComponent stores a sort of hitbox (basically the
    projection on the surface, something like lowest three rows for a
    human-sized object). Then, WalkerCollisionComponent uses those to define
    if walk attempt was unsuccessful.
    
    All entities that do not have this component are assumed to be passable.
    """
    def __init__(self, *args, shadow_pos=(0, 0), shadow_size=None, **kwargs):
        super().__init__(*args, name='passability', **kwargs)
        self.shadow_pos = shadow_pos
        self._shadow_size = shadow_size
            
    @property
    def shadow_size(self):
        #TODO: remove the ugly shadow size hack
        # The idea is that shadow size can be set to owner's widget size by
        # default. The only issue is that owner may not be set, or may not have
        # a widget yet, when this component is created. Thus, this hack.
        # Hopefully no one will try and walk into the object before it is shown
        # on screen. Alas, it requires calling a method for a frequently used
        # property and is generally pretty ugly. Remove this if I ever get to
        # optimizing and manage to think of something better.
        if self._shadow_size is None:
            self._shadow_size = self.owner.widget.size
        return self._shadow_size
    
    def __repr__(self):
        d = {'class': self.__class__.__name__,
             'shadow_size': self._shadow_size,
             'shadow_pos': self.shadow_pos}
        return dumps(d)
    
    
class HealthComponent(Component):
    """
    A component that monitors owner's health and updates whatever needs updating
    """
    def __init__(self, *args, hitpoints=3, **kwargs):
        super().__init__(*args, name='health', **kwargs)
        self.dispatcher.register_listener(self, 'brut_damage')
        self._hitpoints = hitpoints

    def on_event(self, event):
        if event.event_type == 'brut_damage' and event.event_value[0] == self.owner.id:
            self.hitpoints -= event.event_value[1]
        elif event.event_type == 'brut_damage' and event.event_value[0] == self.owner.id:
            self.hitpoints += event.event_value[1]

    @property
    def hitpoints(self):
        return self._hitpoints
    
    @hitpoints.setter
    def hitpoints(self, value):
        if not isinstance(value, int):
            raise BearECSException(f'Attempting to set hitpoints of {self.owner.id} to non-integer {value}')
        self._hitpoints = value
        if self._hitpoints < 0:
            self._hitpoints = 0
        self.process_hitpoint_update()
        
    def process_hitpoint_update(self):
        """
        :return:
        """
        raise NotImplementedError('HP update processing should be overridden')
    
    def __repr__(self):
        return dumps({'class': self.__class__.__name__,
                      'hitpoints': self.hitpoints})


class DestructorHealthComponent(HealthComponent):
    """
    Destroys entity upon reaching zero HP
    """
    def process_hitpoint_update(self):
        if self.hitpoints == 0 and hasattr(self.owner, 'destructor'):
            self.owner.destructor.destroy()


class VisualDamageHealthComponent(HealthComponent):
    """
    A health component for non-active objects.
    Tells the owner's widget to switch image upon reaching certain amounts of HP
    This should be in `widgets_dict` parameter to __init__ which is a dict from
    int HP to image ID. A corresponding image is shown while HP is not less than
    a dict key, but less than the next one (in increasing order).
    If HP reaches zero and object has a Destructor component, it is destroyed
    """
    def __init__(self, *args, widgets_dict={}, **kwargs):
        super().__init__(*args, **kwargs)
        self.widgets_dict = OrderedDict()
        for x in sorted(widgets_dict.keys()):
            # Int conversion useful when loading from JSON, where dict keys get
            # converted to str due to some weird bug. Does nothing during
            # normal Component creation
            self.widgets_dict[int(x)] = widgets_dict[x]
        
    def process_hitpoint_update(self):
        if self.hitpoints == 0 and hasattr(self.owner, 'destructor'):
            self.owner.destructor.destroy()
        for x in self.widgets_dict:
            if self.hitpoints >= x:
                self.owner.widget.switch_to_image(self.widgets_dict[x])
                
    def __repr__(self):
        d = loads(super().__repr__())
        d['widgets_dict'] = self.widgets_dict
        return dumps(d)
    
    
class SwitchWidgetComponent(WidgetComponent):
    """
    A widget component that supports SwitchingWidget
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not isinstance(self.widget, SwitchingWidget):
            raise BearECSException('SwitchWidgetComponent can only be used with SwitchingWidget')
        
    def switch_to_image(self, image_id):
        self.widget.switch_to_image(image_id)
        
    def validate_image(self, image_id):
        """
        Return True if image_id is a valid ID for its widget
        :param image_id:
        :return:
        """
        return image_id in self.widget.images


class SpawnerComponent(Component):
    """
    A component responsible for spawning stuff near its owner
    For projectiles and other such things
    """
    # TODO: overhaul spawner logic
    #  here and in SpawningItemBehaviourComponent
    def __init__(self, *args, factory=None, **kwargs):
        super().__init__(*args, name='spawner', **kwargs)
        self.factory = factory
        self.dispatcher.register_listener(self, 'key_down')

    def spawn(self, item, relative_pos, **kwargs):
        """
        Spawn item at self.pos+self.relative_pos
        :param item:
        :param relative_pos:
        :return:
        """
        self.factory.create_entity(item, (self.owner.position.x + relative_pos[0],
                                          self.owner.position.y + relative_pos[1]),
                                   **kwargs)


class FactionComponent(Component):
    """
    Stores the faction data to see who should attack whom.

    Currently just contains a single string, but later will probably be extended
    to allow for things such as alliances, varying levels of agression, etc.
    """
    
    def __init__(self, *args, faction='items', **kwargs):
        super().__init__(*args, name='faction', **kwargs)
        self.faction = faction
        
    def __repr__(self):
        return dumps({'class': self.__class__.__name__,
                      'faction': self.faction})
        
        
class InputComponent(Component):
    """
    A component that handles input.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, name='controller', **kwargs)
        self.dispatcher.register_listener(self, 'key_down')
        
    def on_event(self, event):
        #TODO: Support non-hardcoded actions and keys
        x = super().on_event(event)
        if isinstance(x, BearEvent):
            r = [x]
        elif isinstance(x, list):
            r = x
        else:
            r = []
        if event.event_type == 'key_down':
            moved = False
            if event.event_value == 'TK_Q':
                # left-handed punch
                self.owner.hands.use_left_hand()
            elif event.event_value == 'TK_E':
                # Right-handed attack
                self.owner.hands.use_right_hand()
            elif event.event_value == 'TK_SPACE':
                # Mostly debug. Eventually will be the rush or jump command
                pass
            elif event.event_value in ('TK_D', 'TK_RIGHT'):
                self.last_move = (2, 0)
                moved = True
            elif event.event_value in ('TK_A', 'TK_LEFT'):
                self.last_move = (-2, 0)
                moved = True
            elif event.event_value in ('TK_S', 'TK_DOWN'):
                self.last_move = (0, 2)
                moved = True
            elif event.event_value in ('TK_W', 'TK_UP'):
                self.last_move = (0, -2)
                moved = True
            elif event.event_value == 'TK_KP_6':
                r.append(BearEvent(event_type='ecs_scroll_by',
                                   event_value=(1, 0)))
            elif event.event_value == 'TK_KP_4':
                r.append(BearEvent(event_type='ecs_scroll_by',
                                   event_value=(-1, 0)))
            elif event.event_value == 'TK_KP_8':
                r.append(BearEvent(event_type='ecs_scroll_by',
                                   event_value=(0, -1)))
            elif event.event_value == 'TK_KP_2':
                r.append(BearEvent(event_type='ecs_scroll_by',
                                   event_value=(0, 1)))
            elif event.event_value == 'TK_KP_5':
                r.append(BearEvent(event_type='ecs_scroll_to',
                                   event_value=(0, 0)))
            if moved:
                self.owner.position.walk(self.last_move)
                r.append(BearEvent(event_type='play_sound',
                                   event_value='step'))
        return r


class MeleeControllerComponent(Component):
    """
    Looks for objects with factions different from its own, moves towards them,
    and when in range, punches them with whatever is in his right hand.
    
    Assumes that the owner has SpawnerComponent and WalkerComponent
    """
    def __init__(self, *args, action_delay=0.5, perception_distance=150, **kwargs):
        #TODO: separate cooldowns for move and attack(s)
        # Maybe this will not be necessary until I make attack class or smth
        super().__init__(*args, name='controller', **kwargs)
        self.dispatcher.register_listener(self, 'tick')
        self.action_delay = action_delay
        self.action_cooldown = 0
        self.perception_distance = perception_distance
        
    def on_event(self, event):
        if event.event_type == 'tick':
            # If on cooldown, be cooling down. Else, try and act
            if self.action_cooldown > 0:
                self.action_cooldown -= event.event_value
            if self.action_cooldown <= 0:
                enemies = list(EntityTracker().filter_entities(
                    lambda x: hasattr(x, 'faction') and x.faction.faction == 'police'))
                current_closest = None
                min_dist = None
                for enemy in enemies:
                    dx = self.owner.position.x - enemy.position.x
                    dy = self.owner.position.y - enemy.position.y
                    dist = sqrt(dx**2 + dy**2)
                    if (not min_dist or min_dist > dist) and dist < self.perception_distance:
                        current_closest = enemy
                if not current_closest:
                    return
                # Probably easier to recalculate for the selected enemy rather
                # than bother caching, creating the dict and all that
                target = current_closest
                dx = self.owner.position.x - enemy.position.x
                dy = self.owner.position.y - enemy.position.y
                dist = sqrt(dx**2 + dy**2)
                if abs(dx) <= 20 and abs(dy) <= 10:
                    self.owner.hands.use_right_hand()
                    self.action_cooldown = self.action_delay
                else:
                    i = randint(0, abs(dx) + abs(dy))
                    if i <= abs(dx):
                        self.owner.position.walk((dx < 0 and 1 or -1, 0))
                    else:
                        self.owner.position.walk((0, dy < 0 and 1 or -1))
                    self.action_cooldown = self.action_delay
                    
    def __repr__(self):
        return dumps({'class': self.__class__.__name__,
                      'action_delay': self.action_delay,
                      'perception_distance': self.perception_distance})
                

class RangedControlComponent(Component):
    """
    Looks for objects with factions different from its own, tries to establish
    a clear line of sight and shoots when it can. Does not move towards target
    along x; when dx is too small, tries to run away
    """
    # TODO: make a bottle punk controller
    pass


class DecayComponent(Component):
    """
    Attaches to an entity and destroys it when conditions are met.
    
    Currently supported destroy conditions are 'keypress' and 'timeout'. If the
    latter is set, you can supply the lifetime (defaults to 1.0 sec)
    """
    
    def __init__(self, *args, destroy_condition='keypress', lifetime=1.0, age=0,
                 **kwargs):
        super().__init__(*args, name='decay', **kwargs)
        if destroy_condition == 'keypress':
            self.dispatcher.register_listener(self, 'key_down')
        elif destroy_condition == 'timeout':
            self.dispatcher.register_listener(self, 'tick')
            self.lifetime = lifetime
            self.age = age
        else:
            raise ValueError(f'destroy_condition should be either keypress or timeout')
        self.destroy_condition = destroy_condition

    def on_event(self, event):
        if self.destroy_condition == 'keypress' and event.event_type == 'key_down':
            self.owner.destructor.destroy()
        elif self.destroy_condition == 'timeout' and event.event_type == 'tick':
            self.age += event.event_value
            if self.age >= self.lifetime:
                self.owner.destructor.destroy()

    def __repr__(self):
        return dumps({'class': self.__class__.__name__,
                      'destroy_condition': self.destroy_condition,
                      'lifetime': self.lifetime,
                      'age': self.age})


class HidingComponent(Component):
    """
    Hides the widget for a given entity on the condition, but does not
    destroy the entity itself.

    Expects owner to have PositionComponent and WidgetComponent
    """
    def __init__(self, *args, hide_condition='keypress',
                 lifetime=1.0, age=0, is_working=True,
                 **kwargs):
        super().__init__(*args, name='hiding', **kwargs)
        if hide_condition == 'keypress':
            self.dispatcher.register_listener(self, 'key_down')
        elif hide_condition == 'timeout':
            self.dispatcher.register_listener(self, 'tick')
            self.lifetime = lifetime
            self.age = age
        else:
            raise ValueError('hide_condition should be either keypress or timeout')
        # This is set to True whenever the owner's widget is actually shown, to
        # avoid triggering when the Entity is already hidden
        self.is_working = is_working
        self.hide_condition = hide_condition

    def hide(self):
        self.is_working = False
        self.dispatcher.add_event(BearEvent(event_type='ecs_remove',
                                            event_value=self.owner.id))

    def show(self):
        if not self.is_working:
            self.is_working = True
            self.dispatcher.add_event(BearEvent(event_type='ecs_add',
                                                event_value=(self.owner.id,
                                                             self.owner.position.x,
                                                             self.owner.position.y)))
            if self.hide_condition == 'timeout':
                self.age = 0

    def on_event(self, event):
        if not self.is_working:
            return
        if self.hide_condition == 'keypress' and event.event_type == 'key_down':
            self.hide()
        elif self.hide_condition == 'timeout' and event.event_type == 'tick':
            self.age += event.event_value
            if self.age >= self.lifetime:
                self.hide()

    def __repr__(self):
        return dumps({'class': self.__class__.__name__,
                      'hide_condition': self.hide_condition,
                      'lifetime': self.lifetime,
                      'age': self.age,
                      'is_working': self.is_working})
        

class HandInterfaceComponent(Component):
    """
    A Component that allows human characters to use hands.

    Shows the correct hand and calls the corresponding item when buttons are
    pressed. When created, requires two dicts:

    `hands_dict` should be a dict with the following
    keys: 'forward_l', 'forward_r', 'back_l', and 'back_r', which should have
    entity IDs as corresponding values. These should be the Entities with a
    foreground hand pointed left, foreground hand pointing right, background
    hand pointed left and a background hand pointed right (left, right, right
    and left hands of the character respectively). Other keys, if any, are
    ignored.  All hand entities are expected to have HidingComponent.

    `hands_offsets` should have the positions of these hands relative to the
    owner's widget, as a tuple of ints.

    Expects owner to have a PositionComponent.

    """
    #TODO: HandInterfaceComponent repr
    def __init__(self, *args, hand_entities, hands_offsets, item_offsets,
                 left_item=None,
                 right_item=None,
                 **kwargs):
        super().__init__(*args, name='hands', **kwargs)
        self.hand_entities = hand_entities
        # Offsets of hands relative to the character
        self.hand_offsets = hands_offsets
        # Offsets of items relative to the hand, ie the position of the
        # outer tip of the hand. For left-facing items, *right edge* of the item
        # should be at this position
        self.item_offsets = item_offsets
        self.left_item = left_item
        self.right_item = right_item

    def use_left_hand(self):
        # Move the appropriate left hand widget to a position and show it
        if self.owner.position.direction == 'r':
            hand = 'back_r'
        else:
            hand = 'forward_l'
        # Have to call the HidingComponent directly because show/hide logic does
        # not use the event for communication
        EntityTracker().entities[self.hand_entities[hand]].hiding.show()
        hand_x = self.owner.position.x + self.hand_offsets[hand][0]
        hand_y = self.owner.position.y + self.hand_offsets[hand][1]
        self.dispatcher.add_event(BearEvent(event_type='ecs_move',
                                            event_value=(self.hand_entities[hand],
                                                         hand_x, hand_y)))
        # TODO: communicate hands with items via events
        # Currently there are several ways in which HandInterfaceComponent
        # calls the methods of items directly. It may cause bugs later
        if self.left_item:
            item = EntityTracker().entities[self.left_item]
            item.widget.switch_to_image(self.owner.position.direction)
            item.hiding.show()
            item_x = hand_x + self.item_offsets[hand][0]
            item_y = hand_y + self.item_offsets[hand][1]
            if self.owner.position.direction == 'l':
                item_x -= item.widget.width
            EntityTracker().entities[self.left_item].position.move(item_x,
                                                                   item_y)
            self.dispatcher.add_event(BearEvent('brut_use_item', self.left_item))

    def use_right_hand(self):
        if self.owner.position.direction == 'r':
            hand = 'forward_r'
        else:
            hand = 'back_l'
        EntityTracker().entities[self.hand_entities[hand]].hiding.show()
        hand_x = self.owner.position.x + self.hand_offsets[hand][0]
        hand_y = self.owner.position.y + self.hand_offsets[hand][1]
        self.dispatcher.add_event(BearEvent(event_type='ecs_move',
                                            event_value=(
                                                self.hand_entities[hand],
                                                hand_x, hand_y)))
        if self.right_item:
            item = EntityTracker().entities[self.right_item]
            item.widget.switch_to_image(self.owner.position.direction)
            item.hiding.show()
            item_x = hand_x + self.item_offsets[hand][0]
            item_y = hand_y + self.item_offsets[hand][1]
            if self.owner.position.direction == 'l':
                item_x -= item.widget.width
            EntityTracker().entities[self.right_item].position.move(item_x,
                                                                   item_y)
            self.dispatcher.add_event(BearEvent('brut_use_item', self.right_item))

    def __repr__(self):
        d = loads(repr(super()))
        # To be implemented


class ItemBehaviourComponent(Component):
    """
    A component that makes its Entity an owned item.
    """

    def __init__(self, *args, owning_entity=None, **kwargs):
        super().__init__(*args, name='item_behaviour', **kwargs)
        # Actual entity (ie character) who uses the item. Not to be mistaken
        # for self.owner, which is item
        if isinstance(owning_entity, Entity):
            self.owning_entity = owning_entity
        elif isinstance(owning_entity, str):
            self.owning_entity = EntityTracker().entities[owning_entity]
        else:
            raise BearECSException(f'A {type(owning_entity)} used as an owning_entity for item')
        self.owning_entity = owning_entity
        self.dispatcher.register_listener(self, 'brut_use_item')

    def use_item(self):
        raise NotImplementedError('ItemBehaviourComponent.use_item should be overridden')

    def on_event(self, event):
        if event.event_type == 'brut_use_item' and event.event_value == self.owner.id:
            self.use_item()

    def __repr__(self):
        d = loads(repr(super()))
        d['owning_entity'] = self.owning_entity.id
        return dumps(d)


class SpawningItemBehaviourComponent(ItemBehaviourComponent):
    """
    An ItemBehaviour that uses the Spawner.

    Spawned entity inherits direction from self.owning_entity and therefore
    this class expects it to have PositionComponent.

    Expects owner to have PositionComponent and SpawnerComponent. Expects
    owner's widget to be SwitchWidgetComponent
    """
    def __init__(self, *args, spawned_item='bullet',
                 relative_pos={'r': (0, 0),
                               'l': (0, 0)},
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.spawned_item = spawned_item
        self.relative_pos = relative_pos

    def use_item(self):
        direction = self.owning_entity.position.direction
        # This component just passes the direction and expects projectile
        # creation code in entity factory to take care of speeds
        self.owner.spawner.spawn(self.spawned_item, self.relative_pos[direction],
                                 direction=direction)

    def __repr__(self):
        d = loads(repr(super()))
        d['spawned_item'] = self.spawned_item
        d['relative_pos'] = self.relative_pos
        return dumps(d)