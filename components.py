from collections import OrderedDict
from json import dumps, loads
from math import sqrt
from random import randint, choice

from bear_hug.bear_utilities import BearECSException, rectangles_collide
from bear_hug.ecs import Component, PositionComponent, BearEvent, \
    Entity, EntityTracker, CollisionComponent, \
    DestructorComponent


class WalkerComponent(PositionComponent):
    """
    A simple PositionComponent that switches widgets appropriately
    """
    
    def __init__(self, *args, direction='r', initial_phase='1',
                 jump_duration=0.4, jump_timer=0,
                 jump_direction=0,
                 jump_vx=60, jump_vy=-40, **kwargs):
        super().__init__(*args, **kwargs)
        self.dispatcher.register_listener(self, ['tick', 'ecs_collision'])
        self.direction = direction
        self.phase = initial_phase
        self.moved_this_tick = False
        self.jump_vx = jump_vx
        self.jump_vy = jump_vy
        self.jump_direction = jump_direction
        self.jump_timer = jump_timer
        self.jump_duration = jump_duration
        
    def walk(self, move):
        """
        Move the owner, switching widgets for step animation and setting
        direction

        If this is undesirable (ie character was pushed or something), use
        regular ``position_component.move()``, which is not overridden.

        :param move: tuple of ints - relative move
        :return:
        """
        if self.moved_this_tick:
            return
        self.relative_move(*move)
        self.moved_this_tick = True
        if move[0] > 0:
            self.direction = 'r'
        elif move[0] < 0:
            self.direction = 'l'
        # If move[0] == 0, the direction stays whatever it was, move is vertical
        # TODO: Supp more than two phases of movement
        if self.phase == '1':
            self.phase = '2'
        else:
            self.phase = '1'
        self.dispatcher.add_event(BearEvent('play_sound', 'step'))
        self.owner.widget.switch_to_image(f'{self.direction}_{self.phase}')

    def jump(self):
        """
        Jump in currently set direction
        :return:
        """
        # TODO: Call correct jump image
        # Jump direction is set to 1 while raising and to -1 while falling
        # Zero when not in jump state
        if self.jump_direction:
            # No double jumps
            return
        self.affect_z = False
        self.jump_direction = 1
        self.jump_timer = 0
        self.vx = self.jump_vx if self.direction == 'r' else -1 * self.jump_vx
        self.vy = self.jump_vy

    def turn(self, direction):
        """
        Set direction and set correct widget
        :param direction:
        :return:
        """
        if direction not in ('l', 'r'):
            raise ValueError('WalkerComponent can only turn l or r')
        self.owner.position.direction = direction
        self.owner.widget.switch_to_image(f'{self.direction}_{self.phase}')
    
    def on_event(self, event):
        if event.event_type == 'tick':
            self.moved_this_tick = False
            if self.jump_direction:
                self.jump_timer += event.event_value
                if self.jump_timer >= self.jump_duration:
                    # Ending jump
                    self.vx = 0
                    self.vy = 0
                    self.jump_direction = 0
                    self.affect_z = True
                elif self.jump_direction == 1 and \
                        self.jump_timer >= self.jump_duration/2:
                    self.jump_direction = -1
                    self.vy = -1 * self.vy
        elif event.event_type == 'ecs_collision' \
                and event.event_value[0] == self.owner.id \
                and self.jump_direction:
            should_fall = False
            # TODO: Fix bugs in jump
            if event.event_value[1]:
                # This exception covers some weird bug when after changing level
                # mid-jump it attempts to process ecs_collision event with an
                # already destroyed highlight entity, and crashes with KeyError
                try:
                    other = EntityTracker().entities[event.event_value[1]]
                    if other.collision.passable:
                        should_fall = False
                    else:
                        should_fall = True
                except KeyError:
                    should_fall = True
            if should_fall:
                self.vx = 0
                if self.jump_direction == 1:
                    # Currently raising, need to drop
                    self.jump_direction = -1
                    self.jump_timer = self.jump_duration - self.jump_timer
                    self.vy = -1 * self.vy
        return super().on_event(event)

    def __repr__(self):
        d = loads(super().__repr__())
        d.update({'direction': self.direction,
                  'initial_phase': self.phase,
                  'jump_vx': self.jump_vx,
                  'jump_vy': self.jump_vy,
                  'jump_direction': self.jump_direction,
                  'jump_timer': self.jump_timer,
                  'jump_duration': self.jump_duration})
        return dumps(d)


class AttachedPositionComponent(PositionComponent):
    """
    A PositionComponent that maintains its position relative to some other entity.

    This component can have its own vx and vy, but it also listens to the
    other's ``ecs_move`` events and repeats them.
    :param tracked_entity: entity ID
    """
    def __init__(self, *args, tracked_entity=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Could be None, in which case it acts like a regular PositionComponent
        self.tracked_entity = tracked_entity
        self.dispatcher.register_listener(self, 'ecs_move')

    def on_event(self, event):
        if event.event_type == 'ecs_move' and self.tracked_entity and \
                event.event_value[0] == self.tracked_entity:
            if not hasattr(self.owner, 'hiding')\
                    or self.owner.hiding.is_working:
                rel_move = EntityTracker().entities[self.tracked_entity].\
                                    position.last_move
                self.relative_move(*rel_move)
        return super().on_event(event)

    def __repr__(self):
        d = loads(super().__repr__())
        d['tracked_entity'] = self.tracked_entity
        return dumps(d)


class GravityPositionComponent(PositionComponent):
    """
    A PositionComponent that maintains a constant downward acceleration.

    :param acceleration: A number. Acceleration in chars per second squared.
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
                self.vy += round(self.have_waited/self.update_freq)
                self.have_waited = 0
        return super().on_event(event)

    def __repr__(self):
        d = loads(super().__repr__())
        {}.update({'acceleration': self.acceleration,
                   'have_waited': self.have_waited})
        return dumps(d)


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
            self.dispatcher.add_event(BearEvent('play_sound', 'punch'))
            self.dispatcher.add_event(BearEvent(event_type='brut_damage',
                                                event_value=(entity, self.damage)))
            self.owner.destructor.destroy()
        
    def __repr__(self):
        d = loads(super().__repr__())
        d['damage'] = self.damage
        return dumps(d)


class PowerProjectileCollisionComponent(ProjectileCollisionComponent):
    """
    A collision projectile for a power spark.

    Acts like a regular ProjectileCollisionComponent unless its target has
    PowerInteractionComponent, in which case it is powered
    """
    def collided_into(self, other):
        if not other:
            self.owner.destructor.destroy()
        else:
            entity = EntityTracker().entities[other]
            if hasattr(entity, 'collision') and not entity.collision.passable:
                if hasattr(entity, 'powered'):
                    entity.powered.get_power()
                else:
                    self.dispatcher.add_event(BearEvent('brut_damage',
                                                        (other, self.damage)))
                self.owner.destructor.destroy()


class HealingProjectileCollisionComponent(CollisionComponent):
    """
    Like a bullet, except that it heals whoever it hits instead of damaging them
    """
    def __init__(self, *args, healing=2, **kwargs):
        super().__init__(*args, **kwargs)
        self.healing=healing

    def collided_into(self, other):
        if not other:
            self.owner.destructor.destroy()
        else:
            entity = EntityTracker().entities[other]
            if not entity.collision.passable:
                if hasattr(entity, 'health'):
                    self.dispatcher.add_event(BearEvent('brut_heal',
                                                        (other, self.healing)))
                self.owner.destructor.destroy()

    def collided_by(self, other):
        # Unlike most other projectiles, can also be collided into.
        # This is guaranteed to destroy the bubble
        self.dispatcher.add_event(BearEvent('brut_heal',
                                            (other, self.healing)))
        self.owner.destructor.destroy()


class HazardCollisionComponent(CollisionComponent):
    """
    A collision component that damages whoever collides into it.

    Intended for use with flames, traps and such.
    """
    def __init__(self, *args, damage=1, damage_cooldown=0.3,
                 on_cooldown=False, have_waited=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.damage = damage
        self.damage_cooldown = damage_cooldown
        self.on_cooldown = on_cooldown
        self.have_waited = have_waited
        self.dispatcher.register_listener(self, 'tick')

    def collided_by(self, entity):
        # TODO: do damage to entities who stand in fire and don't move
        if not self.on_cooldown:
            try:
                # Covers collisions from nonexistent entities
                other = EntityTracker().entities[entity]
            except KeyError:
                return
            if hasattr(other, 'health'):
                self.dispatcher.add_event(BearEvent(event_type='brut_damage',
                                                    event_value=(entity, self.damage)))
            self.on_cooldown = True

    def on_event(self, event):
        if event.event_type == 'tick' and self.on_cooldown:
            self.have_waited += event.event_value
            if self.have_waited >= self.damage_cooldown:
                self.on_cooldown = False
                self.have_waited = 0
        return super().on_event(event)

    def __repr__(self):
        d = loads(super().__repr__())
        d.update({'damage': self.damage,
                  'damage_cooldown': self.damage_cooldown,
                  'have_waited': self.have_waited,
                  'on_cooldown': self.on_cooldown})
        return dumps(d)


class GrenadeCollisionComponent(CollisionComponent):
    """
    Destroys the entity if collided into None (ie screen edge)

    Meant for the grenades and such, which cause crashes by attempting to fly
    beyond screen edges.

    Expects owner to have DestructorComponent
    """
    def collided_into(self, entity):
        if entity is None:
            # If vy is negative (ie on the rise), it's possible that the grenade
            # collided into screen top. In that case, just bounce off it
            if self.owner.position.vy < 0:
                self.owner.position.vy = 0
                self.owner.position.have_waited = self.owner.position.update_freq
            # If not, it has definitely collided into left or right edge
            elif self.owner.position.vy > 5:
                self.owner.destructor.destroy()


class AmmoPickupCollisionComponent(CollisionComponent):
    """
    A collision component for ammo pickup.

    If collided into by an entity with hands, check whether this entity holds
    an item that requires ammo. If it does, and if that item is not on full
    ammo, recharges the item, emits the appropriate event and self-destructs.
    """
    def collided_by(self, other):
        # No sense instantiating entity tracker three times for as many entities
        tracker = EntityTracker()
        entity = tracker.entities[other]
        if hasattr(entity, 'hands'):
            left_item = tracker.entities[entity.hands.left_item]
            right_item = tracker.entities[entity.hands.right_item]
            used = False
            if left_item.item_behaviour.max_ammo and left_item.item_behaviour.ammo < left_item.item_behaviour.max_ammo:
                left_item.item_behaviour.ammo = left_item.item_behaviour.max_ammo
                used = True
            if right_item.item_behaviour.max_ammo and right_item.item_behaviour.ammo < right_item.item_behaviour.max_ammo:
                right_item.item_behaviour.ammo = right_item.item_behaviour.max_ammo
                used = True
            if used:
                self.owner.destructor.destroy()


class GrenadeComponent(Component):
    """
    The grenade behaviour.

    When entity with this component reaches a certain y, it self-destructs and
    creates a predetermined entity with its Spawner. This is supposed to be used
    with things like grenades and Molotov cocktails that fly in the arc and
    explode upon hitting the ground.
    """

    def __init__(self, *args, spawned_item='flame', target_y=None,
                 explosion_sound=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.spawned_item = spawned_item
        self.target_y = target_y
        self.explosion_sound = explosion_sound
        self.dispatcher.register_listener(self, 'ecs_move')

    def on_event(self, event):
        if event.event_type == 'ecs_move' and event.event_value[0] == self.owner.id:
            if not self.target_y:
                self.target_y = self.owner.position.y + randint(2, 12)
            if self.owner.position.y >= self.target_y:
                if self.explosion_sound:
                    self.dispatcher.add_event(BearEvent('play_sound',
                                                        self.explosion_sound))
                    # TODO: remove flame sound if I add other grenades
                    self.dispatcher.add_event(BearEvent('play_sound',
                                                        'molotov_fire'))
                self.owner.spawner.spawn(self.spawned_item,
                                         (round(self.owner.widget.width/2),
                                          round(self.owner.widget.height/2)))
                self.owner.destructor.destroy()

    def __repr__(self):
        d = loads(super().__repr__())
        d.update({'spawned_item': self.spawned_item,
                   'target_y': self.target_y})
        return dumps(d)

    
class HealthComponent(Component):
    """
    A component that monitors owner's health and updates whatever needs updating
    """
    def __init__(self, *args, hitpoints=3, **kwargs):
        super().__init__(*args, name='health', **kwargs)
        self.dispatcher.register_listener(self, ('brut_damage', 'brut_heal'))
        self.max_hitpoints = hitpoints
        self._hitpoints = hitpoints

    def on_event(self, event):
        if event.event_type == 'brut_damage' and event.event_value[0] == self.owner.id:
            self.hitpoints -= event.event_value[1]
        elif event.event_type == 'brut_heal' and event.event_value[0] == self.owner.id:
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
        if self._hitpoints > self.max_hitpoints:
            self._hitpoints = self.max_hitpoints
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


class SpawnerDestructorHealthComponent(HealthComponent):
    """
    Destroys entity upon reaching zero HP and spawns an item
    """
    def __init__(self, *args, spawned_item='pistol', relative_pos=(0, 0),
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.spawned_item = spawned_item
        self.relative_pos = relative_pos

    def process_hitpoint_update(self):
        if self.hitpoints == 0:
            self.owner.spawner.spawn(self.spawned_item, self.relative_pos)
            self.owner.destructor.destroy()


class CharacterHealthComponent(HealthComponent):
    """
    Health component for characters (both playable and NPCs). Upon death,
    creates a corpse and drops whatever the character had in his hands.

    Expects owner to have SpawnerComponent, HandInterfaceComponent and
    DestructorComponent
    """
    def __init__(self, *args, corpse=None, heal_sounds=('bandage', ),
                 hit_sounds=None, death_sounds=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.corpse_type = corpse
        self.hit_sounds = hit_sounds
        self.heal_sounds = heal_sounds
        self.death_sounds = death_sounds
        self.last_hp = self.hitpoints

    def process_hitpoint_update(self):
        if 0 < self.hitpoints < self.last_hp and self.hit_sounds:
            self.last_hp = self.hitpoints
            self.dispatcher.add_event(BearEvent('play_sound',
                                                choice(self.hit_sounds)))
        elif 0 < self.last_hp < self.hitpoints and self.heal_sounds:
            self.last_hp = self.hitpoints
            self.dispatcher.add_event(BearEvent('play_sound',
                                                choice(self.heal_sounds)))
        if self.hitpoints == 0:
            self.owner.spawner.spawn(self.corpse_type,
                                     relative_pos=(0, self.owner.widget.height - 9))
            self.owner.hands.drop('right')
            self.owner.hands.drop('left')
            if self.death_sounds:
                if self.owner.id == 'cop_1':
                    self.dispatcher.add_event(BearEvent('set_bg_sound', None))
                self.dispatcher.add_event(BearEvent('play_sound',
                                                    choice(self.death_sounds)))
            self.owner.destructor.destroy()

    def __repr__(self):
        d = loads(super().__repr__())
        d['corpse'] = self.corpse_type
        return dumps(d)


class VisualDamageHealthComponent(HealthComponent):
    """
    A health component for non-active objects.
    Tells the owner's widget to switch image upon reaching certain amounts of HP
    This should be in `widgets_dict` parameter to __init__ which is a dict from
    int HP to image ID. A corresponding image is shown while HP is not less than
    a dict key, but less than the next one (in increasing order).
    If HP reaches zero and object has a Destructor component, it is destroyed
    """
    def __init__(self, *args, widgets_dict={}, hit_sounds=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.widgets_dict = OrderedDict()
        self.hit_sounds = hit_sounds
        for x in sorted(widgets_dict.keys()):
            # Int conversion useful when loading from JSON, where dict keys get
            # converted to str due to some weird bug. Does nothing during
            # normal Component creation
            self.widgets_dict[int(x)] = widgets_dict[x]
        
    def process_hitpoint_update(self):
        if self.hit_sounds:
            self.dispatcher.add_event(BearEvent('play_sound',
                                                choice(self.hit_sounds)))
        if self.hitpoints == 0 and hasattr(self.owner, 'destructor'):
            self.owner.destructor.destroy()
        for x in self.widgets_dict:
            if self.hitpoints >= x:
                self.owner.widget.switch_to_image(self.widgets_dict[x])
                
    def __repr__(self):
        d = loads(super().__repr__())
        d['widgets_dict'] = self.widgets_dict
        return dumps(d)


class PowerInteractionComponent(Component):
    """
    Responsible for the interaction with energy projectiles.

    The idea is that while these projectiles are harmful for the characters
    (which turns eg pairs of spikes into reliable defensive tools), other
    objects can react to them differently: spikes are ignoring them, healing
    ray emitters are powered by them, etc. This is the component responsible
    for those behaviours
    """
    def __init__(self, *args, powered=False, action_cooldown=0.1, **kwargs):
        super().__init__(*args, name='powered', **kwargs)
        self.powered = powered
        self.action_cooldown = action_cooldown
        self.have_waited = 0
        self.dispatcher.register_listener(self, 'tick')

    def get_power(self):
        if not self.powered:
            # Should charge after being powered even if it had collected some
            # charge before
            self.have_waited = 0
            self.powered = True

    def take_action(self, *args, **kwargs):
        raise NotImplementedError('Power interaction behaviours should be overridden')

    def on_event(self, event):
        if self.powered and event.event_type == 'tick':
            self.have_waited += event.event_value
            while self.have_waited >= self.action_cooldown:
                self.take_action()
                self.have_waited -= self.action_cooldown

    def __repr__(self):
        d = loads(super().__repr__())
        d.update({'powered': self.powered,
                  'action_cooldown': self.action_cooldown})
        return dumps(d)


class SciencePropPowerInteractionComponent(PowerInteractionComponent):
    """
    A prop that does nothing useful. It just switches its widget between powered
    and unpowered state.

    Expects the owner's WidgetComponent to be a SwitchWidgetComponent
    """
    def get_power(self):
        super().get_power()
        self.owner.widget.switch_to_image('powered')

    def take_action(self):
        self.powered = False
        self.owner.widget.switch_to_image('unpowered')
        self.dispatcher.add_event(BearEvent('play_sound', 'blue_machine'))


class SpikePowerInteractionComponent(PowerInteractionComponent):
    """
    Power interaction component for spikes.

    They spam sparks towards any entities with PowerInteractionComponent
    within range
    """
    def __init__(self, *args, range=40, **kwargs):
        super().__init__(*args, **kwargs)
        self.range = range
        self.targets = {}
        self.target_names = []
        self.dispatcher.register_listener(self, ('ecs_add', 'ecs_destroy'))

    def get_power(self):
        super().get_power()
        self.owner.widget.switch_to_image('powered')

    def on_event(self, event):
        r = super().on_event(event)
        if event.event_type == 'ecs_add':
            entity = EntityTracker().entities[event.event_value[0]]
            if not hasattr(entity, 'powered') or entity.id in self.target_names:
                return
            if event.event_value[0] == self.owner.id:
                # On deployment, look for nearby machines
                powered = EntityTracker().filter_entities(lambda x: hasattr(x, 'powered'))
                for machine in powered:
                    dx = self.owner.position.x - machine.position.x
                    dy = self.owner.position.y - machine.position.y
                    dist = sqrt(dx ** 2 + dy ** 2)
                    if dist <= self.range and machine.id != self.owner.id and machine.id not in self.target_names:
                        self.targets[machine.id] = (machine.position.pos[0],
                                                    machine.position.pos[1])
                        self.target_names.append(machine.id)
            else:
                dx = self.owner.position.x - entity.position.x
                dy = self.owner.position.y - entity.position.y
                dist = sqrt(dx ** 2 + dy ** 2)
                if dist <= self.range and entity.id not in self.target_names:
                    self.targets[entity.id] = (entity.position.pos[0] + entity.widget.width // 2,
                                               entity.position.pos[1] + entity.widget.height - 12)
                    self.target_names.append(entity.id)
        elif event.event_type == 'ecs_destroy':
            if event.event_value in self.targets:
                self.target_names.remove(event.event_value)
                del self.targets[event.event_value]

    def take_action(self, *args, **kwargs):
        if self.targets:
            target = self.targets[choice(self.target_names)]
            dx = target[0] - self.owner.position.x - 2
            dy = target[1] - self.owner.position.y - 7
            # Trivially proven from:
            # 1) V**2 = vx**2 + vy ** 2
            # 2) vx/vy = dx/dy
            dx_sign = abs(dx)//dx if dx != 0 else 0
            dy_sign = abs(dy)//dy if dy != 0 else 0
            vy = sqrt(1600 / (1 + dx**2/dy**2)) if dy != 0 else 0
            vx = sqrt(1600 / (1 + dy**2/dx**2)) if dx != 0 else 0
            self.owner.spawner.spawn('tall_spark', (2 + 2*dx_sign,
                                                    7 + 2*dy_sign),
                                     vx=vx * dx_sign,
                                     vy=vy * dy_sign,
                                     **kwargs)
            self.dispatcher.add_event(BearEvent('play_sound',
                                                'spark'))

    def __repr__(self):
        d = loads(super().__repr__())
        d['range'] = self.range
        return dumps(d)


class HealerPowerInteractionComponent(PowerInteractionComponent):
    """
    Shoots healing projectiles in random directions.

    Expects owner to have a SpawnerComponent.
    Expects its widget to be a SwitchWidget with 'powered' and 'unpowered'
    states.
    """
    def get_power(self):
        super().get_power()
        self.owner.widget.switch_to_image('powered')

    def take_action(self, *args, **kwargs):
        vx = randint(-10, 10)
        vy = randint(-10, 10)
        self.dispatcher.add_event(BearEvent('play_sound', 'balloon'))
        self.owner.spawner.spawn('healing_projectile', (5 * vx // abs(vx) if vx != 0 else choice((5, -5)),
                                                        5 * vy // abs(vy) if vy != 0 else choice((5, -5))),
                                 vx=vx, vy=vy)
        self.owner.widget.switch_to_image('unpowered')
        self.powered = False


class SpawnerComponent(Component):
    """
    A component responsible for spawning stuff near its owner
    For projectiles and other such things
    """
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
    # No __repr__ because its only kwarg is the factory instance that cannot
    # be stored between runs.


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


class LevelSwitchComponent(Component):
    """
    Stores the level ID for the level switch widgets
    """
    # TODO: let LevelSwitchComponent track whether the level was won or lost
    def __init__(self, *args, next_level='ghetto_test', **kwargs):
        super().__init__(*args, name='level_switch', **kwargs)
        self.next_level = next_level

    def __repr__(self):
        return dumps({'class': self.__class__.__name__,
                      'next_level': self.next_level})
        
class InputComponent(Component):
    """
    A component that handles input.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, name='controller', **kwargs)
        self.dispatcher.register_listener(self, ['key_down', 'tick'])
        self.walk_delay = 0.1
        self.current_walk_delay = 0
        self.action_delay = 0.4
        self.current_action_delay = 0
        self.next_move = [0, 0]
        self.accepts_input = True

    def on_event(self, event):
        #TODO: Support non-hardcoded actions and keys
        x = super().on_event(event)
        if isinstance(x, BearEvent):
            r = [x]
        elif isinstance(x, list):
            r = x
        else:
            r = []
        if event.event_type == 'tick':
            if self.current_walk_delay > 0:
                self.current_walk_delay -= event.event_value
            else:
                # Movement is processed from the commands collected during
                # the previous tick. Of course, the input is ignored while
                # entity is on the cooldown
                if self.next_move[0] != 0 or self.next_move[1] != 0:
                    self.owner.position.walk(self.next_move)
                    self.next_move = [0, 0]
                    self.current_walk_delay = self.walk_delay
            if self.current_action_delay > 0:
                self.current_action_delay -= event.event_value
        if event.event_type == 'key_down' and self.accepts_input:
            if self.owner.health.hitpoints > 0:
                # These actions are only available to a non-dead player char
                if event.event_value == 'TK_Q' and self.current_action_delay <= 0:
                    # left-handed attack
                    self.current_action_delay = self.owner.hands.use_hand('left')
                elif event.event_value == 'TK_E' and self.current_action_delay <= 0:
                    # Right-handed attack
                    self.current_action_delay = self.owner.hands.use_hand('right')
                elif event.event_value == 'TK_Z' and self.current_action_delay <= 0:
                    # Left-handed pickup
                    self.owner.hands.pick_up(hand='left')
                    self.current_action_delay = self.action_delay
                elif event.event_value == 'TK_C' and self.current_action_delay <= 0:
                    # Right-handed pickup
                    self.owner.hands.pick_up(hand='right')
                    self.current_action_delay = self.action_delay
                elif event.event_value == 'TK_SPACE' and self.current_action_delay <= 0:
                    self.owner.position.jump()
                    self.current_action_delay = self.action_delay
            # These actions are available whether or not the player is dead
            if event.event_value in ('TK_D', 'TK_RIGHT') and self.current_walk_delay <= 0:
                self.next_move[0] += 2
            elif event.event_value in ('TK_A', 'TK_LEFT') and self.current_walk_delay <= 0:
                self.next_move[0] -= 2
            elif event.event_value in ('TK_S', 'TK_DOWN') and self.current_walk_delay <= 0:
                self.next_move[1] += 2
            elif event.event_value in ('TK_W', 'TK_UP') and self.current_walk_delay <= 0:
                self.next_move[1] -= 2
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
        return r


class HidingComponent(Component):
    """
    Hides the widget for a given entity on the condition, but does not
    destroy the entity itself.

    Expects owner to have PositionComponent and WidgetComponent
    """
    def __init__(self, *args, hide_condition='keypress',
                 lifetime=1.0, age=0, is_working=False,
                 should_hide=True,
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
        # This is set to False when item should not be hidden
        self.should_hide = should_hide
        self.hide_condition = hide_condition

    def hide(self):
        self.should_hide = True
        self.is_working = False
        self.dispatcher.add_event(BearEvent(event_type='ecs_remove',
                                            event_value=self.owner.id))

    def unhide(self):
        """
        Stop hiding the entity forever
        :return:
        """
        self.should_hide = False
        self.show()

    def show(self):
        """
        Show temporarily, until self.hide_condition becomes true
        :return:
        """
        if not self.is_working:
            self.is_working = True
            self.should_hide = True
            self.dispatcher.add_event(BearEvent(event_type='ecs_add',
                                                event_value=(self.owner.id,
                                                             self.owner.position.x,
                                                             self.owner.position.y)))
            if self.hide_condition == 'timeout':
                self.age = 0

    def on_event(self, event):
        if not self.should_hide or not self.is_working:
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
                      'should_hide': self.should_hide,
                      'lifetime': self.lifetime,
                      'age': self.age,
                      'is_working': self.is_working})
        

class ParticleDestructorComponent(DestructorComponent):
    """
    A subclass of the DestructorComponent that spawns particles when owner is
    destroyed.

    Intended for use with single-use items (eg bandages) which need some sort of
    a visual confirmation that it did indeed work.

    Unlike SpawnerDestructorComponent, contains a pile of data related to the
    particle effects
    """
    def __init__(self, *args, spawned_item, relative_pos = (0, 0),
                 size=(10, 10),
                 character=',', char_count=8, char_speed=10,
                 color='red', lifetime=0.3,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.spawned_item = spawned_item
        self.relative_pos = relative_pos
        self.size = size
        self.character = character
        self.char_count = char_count
        self.char_speed = char_speed
        self.color = color
        self.lifetime = lifetime

    def destroy(self):
        self.owner.spawner.spawn(self.spawned_item, self.relative_pos,
                                 size=self.size, character=self.character,
                                 char_count=self.char_count,
                                 char_speed=self.char_speed,
                                 color=self.color, lifetime=self.lifetime)
        super().destroy()

    def __repr__(self):
        d = loads(super().__repr__())
        d['spawned_item'] = self.spawned_item
        d['relative_pos'] = self.relative_pos
        d['size'] = self.size
        d['character'] = self.character
        d['char_count'] = self.char_count
        d['char_speed'] = self.char_speed
        d['color'] = self.color
        d['lifetime'] = self.lifetime
        return dumps(d)


class HandInterfaceComponent(Component):
    """
    A Component that allows human characters to use hands.

    This entity keeps track of all hand entities assigned to this character. It
    shows the correct hand at the correct position and expects the hand itself
    to call the corresponding item. When created, requires two dicts:

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
    def __init__(self, *args, hand_entities, hands_offsets, item_offsets,
                 left_item=None,
                 right_item=None,
                 **kwargs):
        super().__init__(*args, name='hands', **kwargs)
        # In case the item is destroyed while it is held
        self.dispatcher.register_listener(self, 'ecs_destroy')
        self.hand_entities = hand_entities
        # Offsets of hands relative to the character
        self.hands_offsets = hands_offsets
        # Offsets of items relative to the hand, ie the position of the
        # outer tip of the hand. For left-facing items, *right edge* of the item
        # should be at this position
        self.item_offsets = item_offsets
        self.left_item = left_item
        self.right_item = right_item
        # A little helper to find correct hand for a given direction
        self.which_hand = {'right': {'r': 'forward_r',
                                     'l': 'back_l'},
                           'left': {'r': 'back_r',
                                    'l': 'forward_l'}}

    def use_hand(self, hand='right'):
        """
        use the item in hand

        Draws the hand and the item where they belong. Returns the item cooldown
        (in seconds)
        :param hand:
        :return:
        """
        hand_label = self.which_hand[hand][self.owner.position.direction]
        # Have to call the HidingComponent and WidgetComponent directly
        hand_entity = EntityTracker().entities[self.hand_entities[hand_label]]
        hand_entity.widget.z_level = self.owner.widget.z_level + 1
        hand_x = self.owner.position.x + self.hands_offsets[hand_label][0]
        hand_y = self.owner.position.y + self.hands_offsets[hand_label][1]
        hand_entity.hiding.show()
        hand_entity.position.move(hand_x, hand_y)
        # Use item in hand
        item_id = self.right_item if hand == 'right' else self.left_item
        item = EntityTracker().entities[item_id]
        item.widget.switch_to_image(self.owner.position.direction)
        item.widget.z_level = self.owner.widget.z_level + 1
        item.hiding.show()
        item_x = hand_x + self.item_offsets[hand_label][0] \
                        + item.item_behaviour.grab_offset[self.owner.position.direction][0]
        item_y = hand_y + self.item_offsets[hand_label][1] \
                        + item.item_behaviour.grab_offset[self.owner.position.direction][1]
        if self.owner.position.direction == 'l':
            item_x -= item.widget.width
        item.position.move(item_x, item_y)
        self.dispatcher.add_event(BearEvent('brut_use_item', item_id))
        return item.item_behaviour.use_delay

    def pick_up(self, hand='right'):
        """
        Pick up whatever item is on the ground under owner.

        If owner has any non-fist item in that hand, drop it.
        Then, if there is an item available, pick it up; otherwise, set fist
        as an active item.

        :param hand: Either 'left' or 'right'. Pick up in that hand.
        :return:
        """

        # See if there is an item on the ground
        other_item = None
        for entity in EntityTracker().filter_entities(lambda x: hasattr(x, 'collectable')):
            if rectangles_collide((entity.position.x, entity.position.y),
                                  entity.widget.size,
                                  (self.owner.position.x,
                                   self.owner.position.y + self.owner.widget.height - 5),
                                  (self.owner.widget.width, 5)) and entity.item_behaviour.owning_entity is None:
                other_item = entity
                break
        if other_item is None:
            # If there is no item, drop whatever there was right under player's
            # feet and reactivate fist
            self.drop(hand, shift=False)
            if hand == 'right':
                self.right_item = f'fist_{self.owner.id}_right'
                self.dispatcher.add_event(BearEvent('brut_pick_up',
                                                    (self.owner.id,
                                                     'right',
                                                     self.right_item)))
            else:
                self.left_item = f'fist_{self.owner.id}_right'
                self.dispatcher.add_event(BearEvent('brut_pick_up',
                                                    (self.owner.id,
                                                     'left',
                                                     self.left_item)))
        else:
            # if there is another item, current one is thrown slightly to the
            # side, and a new one is picked up
            self.drop(hand)
            other_item.item_behaviour.owning_entity = self.owner
            other_item.hiding.hide()
            self.dispatcher.add_event(BearEvent('play_sound',
                                                'item_grab'))
            if hand == 'right':
                self.right_item = other_item.id
            elif hand == 'left':
                self.left_item = other_item.id
            self.dispatcher.add_event(BearEvent('brut_pick_up',
                                                (self.owner.id,
                                                 hand,
                                                 other_item.id)))

    def drop(self, hand='right', shift=True):
        """
        Drop whatever is in the corresponding hand.

        If the item held is fist (generally, any item with ``fist`` in entity
        ID, so creating a "Perverted sword of four-handed fisting" or something
        is likely to cause all sorts of problems both to the engine and players'
        sanity), does nothing.

        :param hand: str. Either 'right' or 'left'

        :param shift: str. If True, the item is randomly offset by several chars.
        If False, it is dropped right under the player. Defaults to True.
        """
        item_id = hand == 'right' and self.right_item or self.left_item
        if 'fist' not in item_id:
            item = EntityTracker().entities[item_id]
            item.item_behaviour.owning_entity = None
            item.hiding.show()
            pos = [self.owner.position.x,
                   self.owner.position.y + self.owner.widget.height - item.widget.height]
            if shift:
                pos[0] += randint(-3, 3)
                pos[1] += randint(-3, 3)
            item.position.move(*pos)
            item.widget.z_level = item.position.y + item.widget.height
            item.hiding.unhide()
            self.dispatcher.add_event(BearEvent('play_sound', 'item_drop'))

    def on_event(self, event):
        if event.event_type == 'ecs_destroy':
            if event.event_value == self.right_item:
                self.right_item = f'fist_{self.owner.id}_right'
                self.dispatcher.add_event(BearEvent('brut_pick_up',
                                                    (self.owner.id,
                                                     'right',
                                                     self.right_item)))
            elif event.event_value == self.left_item:
                self.left_item = f'fist_{self.owner.id}_left'
                self.dispatcher.add_event(BearEvent('brut_pick_up',
                                                    (self.owner.id,
                                                     'left',
                                                     self.left_item)))

    def __repr__(self):
        d = loads(super().__repr__())
        d['hand_entities'] = self.hand_entities
        d['hands_offsets'] = self.hands_offsets
        d['item_offsets'] = self.item_offsets
        d['left_item'] = self.left_item
        d['right_item'] = self.right_item
        return dumps(d)


class CollectableBehaviourComponent(Component):
    """
    A behaviour component for the item that can be picked up

    This is actually empty and marks entity as pick up-able.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, name='collectable', **kwargs)


class ItemBehaviourComponent(Component):
    """
    A component that makes its Entity an owned item.
    """

    def __init__(self, *args, owning_entity=None,
                 single_use = False,
                 max_ammo = None,
                 grab_offset = {'r': (0, 0),
                                'l': (0, 0)},
                 item_name = 'PLACEHOLDER',
                 item_description = 'Someone failed to write\nan item description',
                 use_sound = None,
                 use_delay = 0.1,
                 **kwargs):
        super().__init__(*args, name='item_behaviour', **kwargs)
        self.single_use = single_use
        self.max_ammo = max_ammo
        self._ammo = None
        self.ammo = max_ammo
        self.use_sound = use_sound
        self.is_destroying = False
        self.grab_offset = grab_offset
        self.item_name = item_name
        self.use_delay = use_delay
        d = item_description.split('\n')
        if len(d) > 5 or any(len(x)>28 for x in d):
            raise ValueError(f'Item description for {item_name} too long. Should be <=5 lines, <=28 chars each')
        self.item_description = item_description
        self._owning_entity = None
        self._future_owner = None
        self.owning_entity = owning_entity
        self.dispatcher.register_listener(self, ('brut_use_item', 'tick'))

    @property
    def ammo(self):
        return self._ammo

    @ammo.setter
    def ammo(self, value):
        self._ammo = value
        if value is not None:
            if value > self.max_ammo:
                raise ValueError('Setting ammo for more than maximum')
            if self.owner:
                self.dispatcher.add_event(BearEvent('brut_change_ammo',
                                                (self.owner.id, self._ammo)))

    @property
    def owning_entity(self):
        if self._owning_entity:
            return self._owning_entity
        else:
            return self._future_owner

    @owning_entity.setter
    def owning_entity(self, value):
        if isinstance(value, Entity):
            self._owning_entity = value
        elif isinstance(value, str):
            # The item entity can be created (eg during deserialization) before
            # its owning entity has been announced via 'ecs_create'. If so,
            # remember owning entity ID and attempt to find the actual entity
            # when the item is first used. If the entity is still not created by
            # then, no attempt to catch the resulting KeyError is made.
            #
            # Trying to set entity outright via EntityTracker() causes a bug:
            # empty component-less entity being used upon loading. It's easier
            # to postpone everything than try to figure out this weird bug,
            # probably related to the exact order in which entities are
            # deserialized
            self._future_owner = value
        elif value is None:
            self._owning_entity = None
            self._future_owner = None
        else:
            # owning_entity can be empty, but not some incorrect type
            raise BearECSException(f'A {type(value)} used as an owning_entity for item')

    def use_item(self):
        if self.single_use:
            self.is_destroying = True
        if self.use_sound:
            self.dispatcher.add_event(BearEvent('play_sound', self.use_sound))

    def on_event(self, event):
        if event.event_type == 'brut_use_item' and event.event_value == self.owner.id:
            try:
                self.use_item()
            except AttributeError:
                self.owning_entity = EntityTracker().entities[self._future_owner]
                self.use_item()
        elif event.event_type == 'tick' and self.is_destroying:
            self.owner.destructor.destroy()

    def __repr__(self):
        d = loads(super().__repr__())
        try:
            d['owning_entity'] = self.owning_entity.id
        except AttributeError:
            d['owning_entity'] = self._future_owner
        d['grab_offset'] = self.grab_offset
        return dumps(d)


class HealingItemBehaviourComponent(ItemBehaviourComponent):
    """
    Heals owning_entity when used
    """
    def __init__(self, *args, healing=2, **kwargs):
        super().__init__(*args, **kwargs)
        self.healing = healing

    def use_item(self):
        super().use_item()
        self.dispatcher.add_event(BearEvent('brut_heal',
                                           (self.owning_entity.id,
                                            self.healing)))


class SpawningItemBehaviourComponent(ItemBehaviourComponent):
    """
    An ItemBehaviour that uses the Spawner.

    Spawned entity inherits direction from self.owning_entity and therefore
    this class expects it to have PositionComponent.

    Expects owner to have PositionComponent and SpawnerComponent. Expects
    owner's widget to be SwitchWidgetComponent. Expects the method responsible
    for the creation of spawned object to accept ``direction`` kwarg
    """
    def __init__(self, *args, spawned_items={'bullet': {'r': (0, 0),
                                                        'l': (0, 0)}},
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.spawned_items = spawned_items

    def use_item(self):
        if self.max_ammo:
            if self.ammo == 0:
                # TODO: sound or something to indicate a lack of ammo
                return
            else:
                self.ammo -= 1
        super().use_item()
        direction = self.owning_entity.position.direction
        # This component just passes the direction and Z, and expects projectile
        # creation code in entity factory to take care of speeds
        for item in self.spawned_items:
            self.owner.spawner.spawn(item,
                                     self.spawned_items[item][direction],
                                     direction=direction,
                                     z_level=self.owning_entity.widget.z_level)


    def __repr__(self):
        d = loads(super().__repr__())
        d['spawned_items'] = self.spawned_items
        return dumps(d)
