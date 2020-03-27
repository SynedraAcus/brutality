"""
Map generators
"""

import random
from listeners import SpawnItem, SpawningListener
from entities import EntityFactory

from bear_hug.ecs import EntityTracker, Singleton
from bear_hug.event import BearEvent, BearEventDispatcher


class LevelManager(metaclass=Singleton):
    """
    A class responsible for creating levels.

    For each level, it calls all appropriate factory methods to create
    everything except player character
    """
    def __init__(self, dispatcher, factory, spawner=None, level_switch=None,
                 player_entity=None):
        if not isinstance(dispatcher, BearEventDispatcher):
            raise TypeError(f'{type(dispatcher)} used as a dispatcher for LevelManager instead of BearEventDispatcher')
        self.dispatcher = dispatcher
        if not isinstance(factory, EntityFactory):
            raise TypeError(f'{type(factory)} used as a factory for LevelManager instead of EntityFactory')
        self.factory = factory
        if not isinstance(spawner, SpawningListener):
            raise TypeError(f'{type(spawner)} used as a spawner for LevelManager instead of SpawningListener')
        self.spawner = spawner
        self.level_switch = level_switch
        self.player_entity = player_entity
        self.methods = {'ghetto_test': '_ghetto_test',
                        'ghetto_tutorial': '_ghetto_tutorial',
                        'department': '_department'}
        self.starting_positions = {'ghetto_test': (10, 20),
                                   'ghetto_tutorial': (5, 25),
                                   'department': (10, 20)}

    def should_remove(self, entity):
        """
        Return True if this entity should be removed during level change

        This method returns False for:
        1. Player himself (self.player_entity)
        2. Items in player's posession (those that have ItemBehaviourComponent
        and its owning_entity is set to player's ID)
        3. Hands whose name includes player name (strictly speaking, entities
        where both `player_entity` and `hand` are parts of the id).
        """
        if entity.id == self.player_entity:
            return False
        if 'item_behaviour' in entity.components:
            try:
                if entity.item_behaviour.owning_entity.id == self.player_entity:
                    return False
            except AttributeError:
                 if entity.item_behaviour._future_owner == self.player_entity:
                     return False
            return True
        if f'{self.player_entity}_hand' in entity.id:
            return False
        return True

    def destroy_current_level(self, destroy_player=False):
        # Remove every entity except self.player_entity
        filter_method = self.should_remove if not destroy_player else lambda x: True
        for entity in EntityTracker().filter_entities(filter_method):
            entity.destructor.destroy()
        self.dispatcher.add_event(BearEvent('set_bg_sound', None))
        # Remove any un-triggered spawns
        self.spawner.remove_spawns()
        # Disable level switch to make sure it doesn't trigger mid-level change
        self.level_switch.disable()

    def set_level(self, level_id):
        """
        Change level to level_id

        Destroys the existing level in the process. Does not affect PC in any
        way except position (which is set to self.starting_positions[level_id]).

        :param level_id: Level identifier.
        :return:
        """
        # if current level is set, destroy it
        if self.level_switch.current_level:
            self.destroy_current_level()
        getattr(self, self.methods[level_id])()
        # set player position to whatever it should be
        player = EntityTracker().entities[self.player_entity]
        player.position.move(*self.starting_positions[level_id])
        self.level_switch.current_level = level_id
        self.level_switch.enable()

    def _ghetto_test(self):
        self.dispatcher.add_event(BearEvent('set_bg_sound', 'ghetto_walk_bg'))
        self.factory.create_entity('ghetto_bg', (0, 0), size=(500, 20))
        self.factory.create_entity('floor', (0, 20), size=(500, 30))
        # The purpose of this invisible collider is to have some space below the
        # screen in case eg corpses are spawned at the very bottom
        self.factory.create_entity('bandage', (15, 40))
        self.factory.create_entity('pistol', (20, 40))
        self.factory.create_entity('bottle_punk', (320, 10))
        self.factory.create_entity('nunchaku_punk', (350, 30))
        self.factory.create_entity('invis', (0, 51), size=(500, 9))
        self.factory.create_entity('level_switch', (400, 30))
        # Set level switch coordinates
        self.level_switch.switch_pos = (400, 30)
        self.level_switch.switch_size = (15, 4)

    def _department(self):
        self.dispatcher.add_event(BearEvent('set_bg_sound', 'supercop_bg'))
        self.factory.create_entity('level_switch', (415, 33))
        self.level_switch.switch_pos = (415, 33)
        self.level_switch.switch_size = (15, 4)
        self.factory.create_entity('dept_bg', (0, 0), size=(500, 20))
        self.factory.create_entity('floor', (0, 20), size=(500, 30))
        self.factory.create_entity('invis', (0, 51), size=(500, 9))
        # All messages
        self.factory.create_entity('message', (20, 20),
                                   text='Walk with WASD or arrow keys.',
                                   destroy_condition='timeout',
                                   vy=-2, lifetime=5)
        spawns = (SpawnItem(item='message',
                            pos=(20, 20),
                            size=(10, 20),
                            kwargs={
                                'text': 'Use your hands with Q and E\nWith no weapons, you still can punch',
                                'destroy_condition': 'timeout',
                                'lifetime': 5,
                                'vy': -2}),
                  SpawnItem(item='message',
                            pos=(130, 20),
                            size=(10, 20),
                            kwargs={
                                'text': 'Pick up items with Z and C\nWith pistol, you can shoot\nat any distance,\neven offscreen',
                                'destroy_condition': 'timeout',
                                'lifetime': 5,
                                'vy': -2}),
                  SpawnItem(item='message',
                            pos=(150, 20),
                            size=(10, 8),
                            kwargs={
                                'text': 'You can look around with numpad',
                                'destroy_condition': 'timeout',
                                'lifetime': 5,
                                'vy': -2}),
                  SpawnItem(item='message',
                            pos=(350, 20),
                            size=(10, 30),
                            kwargs={
                                'text': 'Hey, come here',
                                'destroy_condition': 'timeout',
                                'lifetime': 5,
                                'vy': -2}),
                  SpawnItem(item='message',
                            pos=(350, 20),
                            size=(30, 8),
                            kwargs={
                                'text': 'We got a damn punk infestation\ndown the street.\n\nGo do something about it',
                                'destroy_condition': 'timeout',
                                'lifetime': 5,
                                'vy': -2}))
        self.spawner.add_spawns_iterable(spawns)
        # Lockers and benches
        self.factory.create_entity('dept_wall_inner', (0, 0))
        self.factory.create_entity('dept_locker', (0, 12))
        self.factory.create_entity('dept_bench', (25, 18))
        self.factory.create_entity('dept_locker', (58, 4))
        self.factory.create_entity('dept_locker', (54, 8))
        self.factory.create_entity('dept_locker', (50, 12))
        self.factory.create_entity('dept_locker', (46, 16))
        self.factory.create_entity('dept_locker', (42, 20))
        self.factory.create_entity('dept_locker', (64, 4))
        self.factory.create_entity('dept_locker', (60, 8))
        self.factory.create_entity('dept_locker', (56, 12))
        self.factory.create_entity('dept_locker', (52, 16))
        self.factory.create_entity('dept_locker', (48, 20))
        self.factory.create_entity('dept_bench', (80, 18))
        self.factory.create_entity('dept_bench', (100, 18))
        # Shooting range
        self.factory.create_entity('dept_wall_inner', (120, 0))
        self.factory.create_entity('dept_wall_inner', (101, 20))
        self.factory.create_entity('pistol', (130, 30))
        self.factory.create_entity('dept_range_table', (160, 13))
        self.factory.create_entity('target', (210, 14))
        self.factory.create_entity('dept_fence', (163, 22))
        self.factory.create_entity('dept_fence', (184, 22))
        self.factory.create_entity('dept_fence', (205, 22))
        self.factory.create_entity('dept_wall_inner', (226, 0))
        self.factory.create_entity('dept_wall_inner', (215, 11))
        # Corridor
        self.factory.create_entity('dept_bench', (240, 18))
        self.factory.create_entity('dept_wall_inner', (265, 0))
        self.factory.create_entity('dept_wall_inner', (254, 11))
        # Office
        self.factory.create_entity('dept_chair_1', (287, 17))
        self.factory.create_entity('dept_table_1', (290, 12))
        self.factory.create_entity('dept_table_2', (305, 12))
        self.factory.create_entity('dept_chair_2', (319, 19))
        self.factory.create_entity('dept_table_boss', (350, 7))
        self.factory.create_entity('dept_wall_inner', (415, 0))
        self.factory.create_entity('dept_wall_inner', (395, 20))

    def _ghetto_tutorial(self):
        self.factory.create_entity('ghetto_bg', (0, 0), size=(500, 20))
        self.factory.create_entity('floor', (0, 20), size=(500, 30))
        # The purpose of this invisible collider is to have some space below the
        # screen in case eg corpses are spawned at the very bottom
        self.factory.create_entity('invis', (0, 51), size=(500, 9))
        self.spawner.add_spawn(SpawnItem(item='message',
                                         pos=(150, 20),
                                         size=(10, 30),
                                         kwargs={
                      'text': 'I don\'t see any punks',
                      'destroy_condition': 'timeout',
                      'lifetime': 5,
                      'vy': -2}))
        self.spawner.add_spawn(SpawnItem(item='message',
                                         pos=(240, 20),
                                         size=(10, 30),
                                         kwargs={
                                             'text': 'Oh, here\'s one',
                                             'destroy_condition': 'timeout',
                                             'lifetime': 5,
                                             'vy': -2}))
        self.spawner.add_spawn(SpawnItem(item='message',
                                         pos=(430, 20),
                                         size=(10, 30),
                                         kwargs={
                                             'text': 'That\'s all for now. Thanks for playing!',
                                             'destroy_condition': 'timeout',
                                             'lifetime': 5,
                                             'vy': -2}))
        # Add some garbage. Each heap contains at least one garbage bag and 2 to 5
        # other items (possibly incuding more bags)
        garbage_pos = []
        for _ in range(6):
            # Make sure garbage heaps are properly spaced
            while True:
                x = random.randint(0, 240)
                max_dist = len(garbage_pos) > 0 \
                           and max((abs(x - i) for i in garbage_pos)) \
                           or 1000
                if max_dist > 50:
                    garbage_pos.append(x)
                    break
            self.factory.create_entity('garbage_bag', (x, 18))
            for i in range(random.randint(3, 6)):
                t = random.choice(('can', 'can2', 'cigarettes', 'garbage_bag',
                                   'bucket', 'pizza_box'))
                self.factory.create_entity(t, (x + random.randint(-5, 5),
                                          22 + random.randint(-2, 2)))
        # Central area
        self.factory.create_entity('broken_car', (150, 12))
        self.factory.create_entity('barricade_3', (250, 35))
        self.factory.create_entity('bottle_punk', (270, 30))
        # factory.create_entity('nunchaku_punk', (300, 20))
        # Main enemy fortification
        self.factory.create_entity('barricade_2', (320, 15))
        self.factory.create_entity('barricade_1', (319, 23))
        self.factory.create_entity('barricade_2', (340, 36))
        self.factory.create_entity('barricade_3', (346, 25))
        self.factory.create_entity('bottle_punk', (380, 32))
        self.factory.create_entity('bottle_punk', (380, 25))
        self.factory.create_entity('nunchaku_punk', (330, 15))
        self.factory.create_entity('nunchaku_punk', (330, 25))
        self.factory.create_entity('nunchaku_punk', (380, 15))
        # Teleporter to the next level, probably
        # Setting BG sound
        self.dispatcher.add_event(BearEvent('set_bg_sound', 'ghetto_walk_bg'))
