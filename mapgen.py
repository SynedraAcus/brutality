"""
Map generators
"""

import random
from listeners import SpawnItem

from bear_hug.ecs import EntityTracker
from bear_hug.event import BearEvent

class LevelManager:
    """
    A class responsible for creating levels.

    For each level, it calls all appropriate factory methods to create
    everything except player character
    """
    def __init__(self, dispatcher, factory, spawner=None, player_entity=None):
        # TODO: check types
        self.dispatcher = dispatcher
        self.factory = factory
        self.spawner = spawner
        self.player_entity = player_entity
        self.current_level = None
        self.methods = {'ghetto_test': '_ghetto_test',
                        'ghetto_tutorial': '_ghetto_tutorial'}
        self.starting_positions = {'ghetto_test': (30, 20),
                                   'ghetto_tutorial': (5, 25)}

    def destroy_current_level(self):
        self.current_level = None
        # Remove every entity except self.player_entity
        for entity in EntityTracker().filter_entities(lambda x: x.id != self.player_entity):
            entity.destructor.destroy()
            print(entity)
        # Remove any un-triggered spawns
        self.spawner.remove_spawns()

    def set_level(self, level_id):
        """
        Change level to level_id

        Destroys the existing level in the process. Does not affect PC in any
        way except position (which is set to self.starting_positions[level_id]).

        :param level_id: Level identifier.
        :return:
        """
        # if current level is set, destroy it
        if self.current_level:
            self.destroy_current_level()
        # call correct level-generation method
        getattr(self, self.methods[level_id])()
        # set player position to whatever it should be
        player = EntityTracker().entities[self.player_entity]
        player.position.move(*self.starting_positions[level_id])
        self.current_level = level_id

    def _ghetto_test(self):
        self.factory.create_entity('ghetto_bg', (0, 0), size=(500, 20))
        self.factory.create_entity('floor', (0, 20), size=(500, 30))
        # The purpose of this invisible collider is to have some space below the
        # screen in case eg corpses are spawned at the very bottom
        self.factory.create_entity('invis', (0, 51), size=(500, 9))
        self.factory.create_entity('level_switch', (45, 25))
        self.factory.create_entity('barrel', (2, 17))
        self.factory.create_entity('barrel', (2, 35))
        self.factory.create_entity('barrel', (40, 17))
        self.factory.create_entity('barrel', (40, 40))

    def _ghetto_tutorial(self):
        self.factory.create_entity('ghetto_bg', (0, 0), size=(500, 20))
        self.factory.create_entity('floor', (0, 20), size=(500, 30))
        # The purpose of this invisible collider is to have some space below the
        # screen in case eg corpses are spawned at the very bottom
        self.factory.create_entity('invis', (0, 51), size=(500, 9))
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
        # Tutorial area entities
        self.factory.create_entity('target', (50, 20))
        self.factory.create_entity('target', (90, 20))
        self.factory.create_entity('pistol', (65, 30))
        self.factory.create_entity('message', (20, 20),
                              text='Walk with WASD or arrow keys.',
                              destroy_condition='timeout',
                              vy=-2, lifetime=5)
        spawns = (SpawnItem(item='message',
                            pos=(20, 20),
                            size=(10, 20),
                            kwargs={
                                'text': 'Use your hands with Q and E\nCurrently, you can only punch with your fists,\nso beat the shit out of this target',
                                'destroy_condition': 'timeout',
                                'lifetime': 5,
                                'vy': -2}),
                  SpawnItem(item='message',
                            pos=(55, 20),
                            size=(10, 20),
                            kwargs={
                                'text': 'Pick up items with Z and C\nWith pistol, you can shoot\nat any distance,\neven offscreen',
                                'destroy_condition': 'timeout',
                                'lifetime': 5,
                                'vy': -2}),
                  SpawnItem(item='message',
                            pos=(95, 20),
                            size=(10, 20),
                            kwargs={
                                'text': 'Now go along and finish those punks!',
                                'destroy_condition': 'timeout',
                                'lifetime': 5,
                                'vy': -2}))
        self.spawner.add_spawns_iterable(spawns)
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
        # TODO: something cool for the level end
        # Teleporter to the next level, probably
