"""
Map generators
"""

import random
from listeners import SpawnItem, SpawningListener
from entities import EntityFactory

from bear_hug.ecs import EntityTracker, Singleton
from bear_hug.event import BearEvent, BearEventDispatcher
from bear_hug.bear_utilities import BearLayoutException

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
        self.styles = {'ghetto', 'dept'}
        self.types = {'corridor'}

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
        if level_id in self.methods:
            getattr(self, self.methods[level_id])()
            # set player position to whatever it should be
            player = EntityTracker().entities[self.player_entity]
            player.position.move(*self.starting_positions[level_id])
        else:
            style, level_type = level_id.split('_')
            player_pos = self.generate_level(style, level_type)
            player = EntityTracker().entities[self.player_entity]
            player.position.move(*player_pos)
        self.level_switch.current_level = level_id
        self.level_switch.enable()

    def generate_level(self, style='ghetto', level_type='corridor'):
        """
        Generate a required type of level
        :param style: str. A location type (ghetto, dept, lab, etc)
        :param level_type: str. A level type (corridor, hostage, etc)
        :return:
        """
        if style not in self.styles:
            raise ValueError(f'Invalid level style "{style}" for levelgen')
        if level_type not in self.types:
            raise ValueError(f'Invalid level type "{level_type}" for levelgen')
        # TODO: decompose generate_level into methods
        player_pos = (20, 20)
        # Generate style basics: BG and decorations
        if style == 'ghetto':
            # TODO: customizable level sizes
            self.factory.create_entity('ghetto_bg', (0, 0), size=(500, 20))
            self.factory.create_entity('floor', (0, 20), size=(500, 30))
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
                    t = random.choice(
                        ('can', 'can2', 'cigarettes', 'garbage_bag',
                         'bucket', 'pizza_box'))
                    self.factory.create_entity(t, (x + random.randint(-5, 5),
                                                   22 + random.randint(-2, 2)))
        elif style == 'dept':
            self.factory.create_entity('dept_bg', (0, 0), size=(500, 20))
            self.factory.create_entity('floor', (0, 20), size=(500, 30))
            self.factory.create_entity('invis', (0, 50), size=(500, 9))
            # No garbage or similar stuff on the department floor
        # Placing actual game content
        #
        # The level is decomposed into a bunch of prefab-like "rooms".
        # They may correspond to the rooms (unexpected, huh?), piles of stuff,
        # enemy groups, etc.
        if style == 'ghetto' and level_type == 'corridor':
            # In case of the ghetto, elements are just piles of things
            # randomly placed (with some spacing)
            running_len = 0
            while running_len < 450:
                running_len += self.ghetto_room()
        elif style =='dept' and level_type == 'corridor':
            # In case of the department, the map is made of rooms
            # Each room consists of some stuff and its rightmost wall
            running_len = 0
            while running_len < 450:
                running_len += self.dept_room(running_len)
            # Exit block should contain the level switch and maybe some stuff
        self.factory.create_entity('level_switch', (running_len+1, 20),
                                   size=(500-running_len - 1, 30))
        # Returns the starting position for the player
        return player_pos

    def ghetto_room(self, left_edge):
        pass

    def dept_room(self, left_edge):
        """
        Generate a single department room.

        :return: room width
        """
        # The size of the future room
        if 450 - left_edge < 55:
            return 450 - left_edge
        room_width = random.randint(55, min(100, 450-left_edge))
        # Most obvious: rightmost wall
        door_style = random.randint(0, 2)
        if door_style == 0:
            self.factory.create_entity('dept_wall_inner',
                                       (left_edge + room_width - 25,
                                        11))
            self.factory.create_entity('dept_wall_inner',
                                       (left_edge + room_width - 37,
                                        23))
        if door_style == 1:
            self.factory.create_entity('dept_wall_inner',
                                       (left_edge + room_width - 15,
                                        0))
            self.factory.create_entity('dept_wall_inner',
                                       (left_edge + room_width - 34,
                                        20))
        elif door_style == 2:
            self.factory.create_entity('dept_wall_inner',
                                       (left_edge + room_width - 15,
                                        0))
            self.factory.create_entity('dept_wall_inner',
                                       (left_edge + room_width - 27,
                                        12))
        # Populating the room
        # room_type = random.randint(0, 2)
        room_type = 2
        if room_type == 0:
            # office:
            # Contains tables and chairs. These are placed in a grid, with a
            # quarter randomly omitted
            # May contain a talkative NPC
            tables = int(room_width/40)
            for table_column in range(tables):
                for table_row in range(2):
                    if random.random() < 0.25:
                        continue
                    self.factory.create_entity('dept_chair_1', (left_edge + table_column * 40 + 3 - 20 * table_row,
                                                                13 + 20 * table_row))
                    self.factory.create_entity('dept_table_1', (left_edge + 40 * table_column + 6 - 20 * table_row,
                                                                10 + 20 * table_row))
                    # TODO: Talkative cop NPC
        elif room_type == 1:
            # Gym:
            # Contains punchbags near the wall, maybe some other sports
            # equipment. Also benches near upper and lower wall
            used_space = 10
            # Upper wall
            while used_space < room_width - 30:
                element = random.random()
                if element < 0.3:
                    # A punchbag and some space
                    self.factory.create_entity('punchbag',
                                               (left_edge + 7 + used_space, 0))
                    used_space += 20
                elif element < 0.6:
                    self.factory.create_entity('dept_weight',
                                               (left_edge + used_space + 5, 14))
                    used_space += 30
                elif element < 0.9:
                    self.factory.create_entity('dept_bench',
                                               (left_edge + used_space, 15))
                    used_space += 20
                else:
                    used_space += 10
                if random.random() < 0.4:
                    # Bottom benches are placed regardless of top wall contents
                    self.factory.create_entity('dept_bench',
                                               (left_edge + used_space - 30,
                                                45))
        elif room_type == 2:
            # Right wall lockers
            skip = {0: (1, 1, 1, 0, 0, 0, 0, 0),
                    1: (0, 0, 1, 1, 1, 0, 0, 0),
                    2: (0, 0, 0, 0, 0, 1, 1, 1)}
            for i in range(8):
                if not skip[door_style][i]:
                    self.factory.create_entity('dept_locker',
                                               (left_edge + room_width - 13 - 4 * i,
                                                4 + 4 * i))
            # TODO: do something useful with the dept_corridor room generator
            # Dept corridor is generally mostly proof of concept, because I
            # don't currently have any need for dept corridor levels. Maybe as
            # an exposition sometime when I need to talk to some cop?
        return room_width

    def _ghetto_test(self):
        self.dispatcher.add_event(BearEvent('set_bg_sound', 'ghetto_walk_bg'))
        self.factory.create_entity('ghetto_bg', (0, 0), size=(500, 20))
        self.factory.create_entity('floor', (0, 20), size=(500, 30))
        self.factory.create_entity('signpost', (70, 14), text='To ghetto',
                                   text_color='orange')
        self.factory.create_entity('level_switch', (64, 23),
                                   size=(20, 4),
                                   next_level='ghetto_tutorial')
        self.factory.create_entity('signpost', (45, 14), text='To dept',
                                   text_color='blue')
        self.factory.create_entity('level_switch', (39, 23),
                                   size=(20, 4),
                                   next_level='department')
        self.factory.create_entity('level_switch', (90, 23),
                                   size=(20, 4),
                                   next_level='dept_corridor')
        self.factory.create_entity('emitter', (100, 40))
        self.factory.create_entity('spike', (120, 6))
        self.factory.create_entity('science_healer', (120, 30))
        self.factory.create_entity('spike', (140, 6))
        self.factory.create_entity('science_prop', (138, 35))
        self.factory.create_entity('female_scientist', (20, 15),
                                   monologue=('I am a test scientist NPC',
                                              'I exist to slowly deliver\nthis monologue',
                                              'which is written\nfor the test purposes.',
                                              'I can also shut up if\nthe player is too far',
                                              'and continue when he returns.',
                                              'I can also run away\nif I see an enemy',
                                              'Calming down when they\nare too far.',
                                              'Or dead.',
                                              'I can also be killed.',
                                              'But please don\'t do that'))
        self.factory.create_entity('target', (50, 30))
        # self.factory.create_entity('bottle_punk', (100, 10))
        self.factory.create_entity('nunchaku_punk', (150, 30))
        self.factory.create_entity('invis', (0, 51), size=(500, 9))


    def _department(self):
        self.dispatcher.add_event(BearEvent('set_bg_sound', 'supercop_bg'))
        self.factory.create_entity('level_switch', (415, 20),
                                   size=(85, 30), next_level='ghetto_tutorial')
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
        self.factory.create_entity('dept_boss', (350, 7),
                                   monologue=('Hey, come here',
                                              'We got a damn punk infestation\ndown the street',
                                              'Go do something about it',
                                              'There is probably a reason these assholes\ngot out of their dens',))
        self.factory.create_entity('dept_wall_inner', (415, 0))
        self.factory.create_entity('dept_wall_inner', (395, 20))

    def _ghetto_tutorial(self):
        self.dispatcher.add_event(BearEvent('set_bg_sound', 'ghetto_walk_bg'))
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
