"""
Map generators
"""

import random
from math import sqrt

from bear_hug.ecs import EntityTracker, Singleton
from bear_hug.event import BearEvent, BearEventDispatcher

from entities import EntityFactory
from listeners import SpawnItem, SpawningListener
from plot import PlotManager


def restart(level_manager, factory, dispatcher, loop):
    """
    Restart the game
    :return:
    """
    try:
        player_entity = EntityTracker().entities['cop_1']
        player_entity.hands.drop('left')
        player_entity.hands.drop('right')
        missing_hp = player_entity.health.max_hitpoints - player_entity.health.hitpoints
        dispatcher.add_event(BearEvent('brut_heal', ('cop_1',
                                                     missing_hp)))
    except KeyError:
        player_entity = factory._create_cop('cop_1')
        dispatcher.add_event(BearEvent('ecs_create', player_entity))
        dispatcher.add_event(BearEvent('ecs_add', ('cop_1', 20, 20)))
        dispatcher.add_event(BearEvent('brut_heal', ('cop_1', 100)))
        loop._run_iteration(0)
    dispatcher.add_event(BearEvent('brut_reset_score', 0))
    dispatcher.add_event(BearEvent('brut_close_menu', None))
    level_manager.set_level('main_menu')


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
        self.methods = {'main_menu': '_menu',
                        'final': '_final',
                        'ghetto_one': '_ghetto_one',
                        'ghetto_test': '_ghetto_test',
                        'lab_fight': '_lab_fight',
                        'department': '_department',
                        'boss_leave_it': '_boss_leave_it',
                        'boss_saved': '_boss_good',
                        'boss_failed': '_boss_bad',
                        'boss_talk': '_boss_talk',
                        'ghetto_expo_h': '_ghetto_expo_hostage',
                        'ghetto_expo_d': '_ghetto_expo_drugs',
                        'goal': 'next_goal_level'}
        self.starting_positions = {'ghetto_test': (10, 20),
                                   'final': (10, 10),
                                   'main_menu': (10, 20),
                                   'ghetto_one': (20, 20),
                                   'department': (10, 20),
                                   'lab_fight': (10, 20),
                                   'boss_leave_it': (70, 20),
                                   'boss_saved': (80, 20),
                                   'ghetto_expo_h': (20, 20),
                                   'ghetto_expo_d': (20, 20),
                                   'boss_failed': (80, 20)}
        self.titles = {'ghetto_one': 'ghetto_title',
                       'ghetto_expo_d': 'ghetto_title',
                       'lab_fight': 'lab_title'}
        self.sounds = {'ghetto_one': 'punk_bg',
                       'ghetto_expo_d': 'punk_bg',
                       'lab_fight': 'lab_bg'}
        self.styles = {'ghetto', 'dept', 'lab'}
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
        # Remove any un-triggered spawns
        self.spawner.remove_spawns()
        # Disable level switch to make sure it doesn't trigger mid-level change
        self.level_switch.disable()
        self.dispatcher.add_event(BearEvent('set_bg_sound', None))

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

    def next_goal_level(self):
        """
        Generate the next goal level
        :return:
        """
        # Boilerplate to be used in future development
        goal = PlotManager().current_goal
        player_pos = self.generate_level(goal.location,
                                         goal.level_types[goal.current_stage])
        self.level_switch.current_level = f'{goal.location}_{goal.level_types[goal.current_stage]}'
        player = EntityTracker().entities[self.player_entity]

    def generate_level(self, style='ghetto', level_type='corridor',
                       next_level='ghetto_test'):
        """
        Generate a required type of level
        :param style: str. A location type (ghetto, dept, lab, etc)
        :param level_type: str. A level type (corridor, hostage, etc)
        :param next_level: str. A level ID for the level switch
        :return:
        """
        if style not in self.styles:
            raise ValueError(f'Invalid level style "{style}" for levelgen')
        if level_type not in self.types:
            raise ValueError(f'Invalid level type "{level_type}" for levelgen')
        player_pos = (20, 20)
        # Since the ScrollingECSLayout does not support resizing, "smaller"
        # levels will still need to be 500 chars wide. To simulate less
        # spacious places, just make a smaller piece surrounded with walls
        # and/or level exits and leave the rest empty

        # Generate style basics: BG and decorations
        if style == 'ghetto':
            self.factory.create_entity('ghetto_bg', (0, 0), size=(500, 20))
            self.factory.create_entity('floor', (0, 20), size=(500, 30))
            self.factory.create_entity('invis', (0, 51), size=(500, 9))
            # Add some garbage. Each heap contains at least one garbage bag
            # and 2 to 5 other items (possibly including more bags)
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
            self.dispatcher.add_event(BearEvent('set_bg_sound', 'supercop_bg'))
            self.factory.create_entity('dept_bg', (0, 0), size=(500, 20))
            self.factory.create_entity('floor', (0, 20), size=(500, 30))
            self.factory.create_entity('invis', (0, 50), size=(500, 9))
            # No garbage or similar stuff on the department floor
        elif style == 'lab':
            self.factory.create_entity('lab_bg', (0, 0), size=(500, 20))
            self.factory.create_entity('floor', (0, 20), size=(500, 30))
            self.factory.create_entity('invis', (0, 51), size=(500, 9))
        # Placing actual game content
        #
        # The level is decomposed into a bunch of prefab-like "rooms".
        # They may correspond to the rooms (unexpected, huh?), piles of stuff,
        # enemy groups, etc.
        if style == 'ghetto' and level_type == 'corridor':
            # In case of the ghetto, "rooms" are just piles of things placed
            # randomly (with some spacing), but with no actual walls
            # First 50 chars are left empty to make sure the player is not
            # dropped right into the middle of the battle
            running_len = 50
            while running_len < 400:
                running_len += self.ghetto_room(running_len)
            # final barricade
            self.factory.create_entity('barricade_1', (440, 12))
            self.factory.create_entity('barricade_2', (435, 30))
            self.factory.create_entity('barricade_3', (425, 40))
            self.factory.create_entity('bottle_punk', (460, 30))
            self.factory.create_entity('bottle_punk', (460, 25))
            self.factory.create_entity('bottle_punk', (465, 10))
            running_len = 450
        elif style == 'dept' and level_type == 'corridor':
            # In case of the department, the map is made of rooms
            # Each room consists of some stuff and its rightmost wall
            running_len = 0
            while running_len < 400:
                running_len += self.dept_room(running_len)
            # Exit block should contain the level switch and maybe some stuff
        elif style == 'lab' and level_type == 'corridor':
            # The lab consists of 6 70-char rooms plus the 80-char final zone.
            # First and last room are prefabs, other 5 are randomly shuffled

            # Initial room
            player_pos = (5, 20)
            self.factory.create_entity('lab_wall_inner', (55, 0))
            self.factory.create_entity('female_scientist', (20, 10),
                                       monologue=('You\'re here to destroy this place?',
                                                  'Good riddance if you ask me,',
                                                  'Although my colleagues\nmight, well...',
                                                  'disagree',
                                                  'Anyway, I never wanted\nto be part of this.',
                                                  'Here\'s something\nyou should know:',
                                                  'The emitter near the table\nactivates the machines',
                                                  'Activated spikes can\npower everything else',
                                                  'I think you would want\nthis machine powered',
                                                  'Break the spike\nto kill the circuit',
                                                  'Good luck'))
            self.factory.create_entity('science_table_2', (0, 10))
            self.factory.create_entity('emitter', (10, 25))
            self.factory.create_entity('science_healer', (30, 19))
            self.factory.create_entity('spike', (35, 30))
            self.factory.create_entity('spike', (49, 15))
            # Final room - a simple machine to disassemble
            self.factory.create_entity('spike', (440, 5), powered=True)
            self.factory.create_entity('spike', (440, 30))
            running_len = 70
            room_order = [0, 1, 2, 3, 4]
            random.shuffle(room_order)
            for room in room_order:
                # Roomgen code will be here
                running_len += self.lab_room(running_len, room)
            running_len = 450
        self.factory.create_entity('level_switch', (running_len+1, 20),
                                   size=(500-running_len - 1, 30),
                                   next_level=next_level)
        # Returns the starting position for the player
        return player_pos

    def lab_room(self, left_edge, room_type=0):
        """
        Generate a lab room

        A 70 char wide room. walls
        :return:
        """
        # room_type = 4
        self.factory.create_entity('lab_wall_inner', (left_edge + 55, 0))
        if room_type == 0:
            self.factory.create_entity('science_table_1', (left_edge - 8, 9))
            self.factory.create_entity('dept_chair_2', (left_edge + 10, 15))
            self.factory.create_entity('spike', (left_edge + 30, 5))
            self.factory.create_entity('science_prop', (left_edge + 45, 10))
            self.factory.create_entity('scientist_enemy', (left_edge+20, 10))
            self.factory.create_entity('scientist_enemy', (left_edge+35, 20))
        elif room_type == 1:
            self.factory.create_entity('science_table_2', (left_edge - 1, 10))
            self.factory.create_entity('scientist_enemy', (left_edge + 40, 10))
        elif room_type == 2:
            # A single drop
            # The player probably already has enough weapons at this point and
            # can easily heal by walking back towards the level start
            self.factory.create_entity('dept_locker', (left_edge - 3, 4))
            item = random.choice(('bandage', 'emitter', 'pistol'))
            self.factory.create_entity(item, (left_edge + 12, 24))
            self.factory.create_entity('science_table_3', (left_edge + 22, 15))
            self.factory.create_entity('spike', (left_edge + 50, 5))
            self.factory.create_entity('spike', (left_edge + 25, 5))
        elif room_type == 3:
            for i in range(4):
                self.factory.create_entity('science_device_1', (left_edge + 20 * i - 4, 4))
                self.factory.create_entity('science_device_1', (left_edge + 20 * i - 9, 10))
                if i < 3 and random.random() < 0.3:
                    self.factory.create_entity('bandage', (left_edge + 20 * i + 5, 25))
        elif room_type == 4:
            self.factory.create_entity('science_table_4', (left_edge - 6, 12))
            self.factory.create_entity('dept_chair_2', (left_edge + 4, 16))
            self.factory.create_entity('scientist_enemy', (left_edge + 18, 12))
            self.factory.create_entity('scientist_enemy', (left_edge + 16, 18))
        return 70

    def ghetto_room(self, left_edge):
        """
        Generate a single ghetto room

        (which is not actually a room, it is just a piece of street without
        walls which contains a single element)
        :param left_edge:
        :return:
        """
        # The size of the future room
        if 400 - left_edge < 55:
            return 450 - left_edge
        room_width = random.randint(60, min(100, 450-left_edge))
        element = random.random()
        # TODO: store the room probabilities in a parameter for easy editing
        if element < 0.1:
            # A broken car
            self.factory.create_entity('broken_car', (left_edge+(room_width - 44) // 2,
                                                      12))
        elif element < 0.15:
            pass # Empty piece of land
        elif element < 0.7:
            # A simple battle
            punk_count = random.randint(2, 3)
            positions = [(random.randint(left_edge + 5,
                                         left_edge + room_width-5),
                                random.randint(10, 25))]
            for _ in range(punk_count):
                # Drop the punks at some distance from each other
                dist = 0
                while dist < 10:
                    punk_pos = (random.randint(left_edge + 5,
                                               left_edge + room_width - 5),
                                random.randint(10, 25))
                    dist = min(sqrt((punk_pos[0] - x[0]) ** 2 +
                                    (punk_pos[1] - x[1]) ** 2)
                               for x in positions)
                positions.append(punk_pos)
            for punk_pos in positions:
                self.factory.create_entity(random.choice(('bottle_punk',
                                                          'nunchaku_punk')),
                                           punk_pos)
            if random.random() < 0.6:
                # Maybe add them a barrel to hang around
                barrel_pos = (left_edge + room_width // 2, 25)
                self.factory.create_entity('barrel', barrel_pos)
                for _ in range(random.randint(1, 3)):
                    # Sprinkle with some garbage
                    self.factory.create_entity(random.choice(('can', 'can2',
                                                              'cigarettes',
                                                              'garbage_bag',
                                                              'bucket',
                                                              'pizza_box')),
                                               (barrel_pos[0] + random.randint(-5, 5),
                                                barrel_pos[1] + 9 + random.randint(-2, 2)))
        else:
            # Barricaded stash
            stash_y = random.choice((16, 37))
            first = random.choice(('barricade_1', 'barricade_2', 'barricade_3'))
            second = first
            while second == first:
                second = random.choice(('barricade_1', 'barricade_2',
                                        'barricade_3'))
            first_pos = (left_edge + room_width//2 - random.randint(20, 30),
                         stash_y + random.randint(-3, 3))
            second_pos = (first_pos[0] + random.randint(30, 45),
                          first_pos[1] + random.randint(-3, 3))
            self.factory.create_entity(first, first_pos)
            self.factory.create_entity(second, second_pos)
            items = ('ammo_pickup', 'bandage', 'nunchaku', 'shiv',
                     'bottle_launcher', 'pistol')
            item_probs = (0.3, 0.3, 0.1, 0.1, 0.1, 0.1)
            for _ in range(random.randint(3, 5)):
                roll = random.random()
                for i, prob in enumerate(item_probs):
                    roll -= prob
                    if roll <= 0:
                        self.factory.create_entity(items[i],
                                                   (random.randint(first_pos[0] + 20, second_pos[0] - 5),
                                                    stash_y + random.randint(5, 10)))
                        break
            if random.random() < 0.7:
                # Most stashes are at least somewhat guarded
                self.factory.create_entity(random.choice(('bottle_punk',
                                                         'nunchaku_punk')),
                                           (left_edge + room_width // 2,
                                            min(stash_y + random.randint(-5, 5), 35)))

        return room_width

    def dept_room(self, left_edge):
        """
        Generate a single department room.

        :return: room width
        """
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
        room_type = random.randint(0, 2)
        # room_type = 0
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
                                                                13 + 15 * table_row))
                    self.factory.create_entity('dept_table_1', (left_edge + 40 * table_column + 6 - 20 * table_row,
                                                                10 + 15 * table_row))
                    if random.random() < 0.3:
                        monologue=PlotManager().get_peaceful_phrase('cops')
                        self.factory.create_entity('cop_npc',
                                                   (left_edge + 40 * table_column + 3 - 20 * table_row,
                                                   5 + 20 * table_row),
                                                   monologue=monologue)
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
            # Dept corridor is  mostly proof of concept, because I
            # don't currently have any need for dept corridor levels. Maybe as
            # an exposition sometime when I need to talk to some cop?
        return room_width

################################################################################
#
# Prefab levels
#
################################################################################

    def _menu(self):
        self.dispatcher.add_event(BearEvent('set_bg_sound', 'ghetto_walk_bg'))
        self.factory.create_entity('ghetto_bg', (0, 0), size=(500, 20))
        self.factory.create_entity('floor', (0, 20), size=(500, 30))
        self.factory.create_entity('invis', (0, 51), size=(500, 9))
        self.factory.create_entity('female_scientist', (20, 15),
                                   monologue=('Welcome to the BRUTALITY prototype',
                                              'Try Esc to access menu\nand WASD/arrows to walk',
                                              'To begin the game, walk into\none of the switches to the right',
                                              'I recommend starting from the\nDEPARTMENT'
                                              ))
        self.factory.create_entity('signpost', (45, 30), text='Skip\ntutorial')
        self.factory.create_entity('level_switch', (37, 39),
                                   size=(60, 9),
                                   next_level='ghetto_one')
        self.factory.create_entity('signpost', (57, 14), text='DEPARTMENT',
                                   text_color='blue')
        self.factory.create_entity('level_switch', (49, 23),
                                   size=(60, 8),
                                   next_level='department')
        # Debug lab teleport and scores
        # Remove from release code!
        self.factory.create_entity('level_switch', (120, 23),
                                   size=(20, 8),
                                   next_level='lab_fight')
        for i in range(120, 150, 5):
            self.factory.create_entity('score_pickup', (i, 30))
        self.factory.create_entity('nunchaku_punk', (170, 10))

    def _final(self):
        self.dispatcher.add_event(BearEvent('set_bg_sound', 'ghetto_walk_bg'))
        self.factory.create_entity('ghetto_bg', (0, 0), size=(500, 20))
        self.factory.create_entity('floor', (0, 21), size=(500, 30))
        self.factory.create_entity('invis', (0, 51), size=(500, 9))
        self.factory.create_entity('signpost', (30, 25),
                                   text='Back to\nmain menu')
        self.factory.create_entity('level_switch', (25, 35), size=(20, 4),
                                   next_level='main_menu')
        self.factory.create_entity('female_scientist', (20, 20),
                                   monologue=('Thank you for playing!',
                                              'This is all for now.',
                                              'Stay tuned for further updates'))

    def _ghetto_test(self):
        self.dispatcher.add_event(BearEvent('set_bg_sound', 'ghetto_walk_bg'))
        self.factory.create_entity('ghetto_bg', (0, 0), size=(500, 20))
        self.factory.create_entity('floor', (0, 20), size=(500, 30))
        self.factory.create_entity('signpost', (70, 14), text='To ghetto',
                                   text_color='orange')
        self.factory.create_entity('level_switch', (64, 23),
                                   size=(20, 4),
                                   next_level='ghetto_tutorial')
        self.factory.create_entity('signpost', (45, 30), text='Expo')
        self.factory.create_entity('level_switch', (40, 39),
                                   size=(20, 4),
                                   next_level='boss_leave_it')
        self.factory.create_entity('signpost', (45, 14), text='To dept',
                                   text_color='blue')
        self.factory.create_entity('level_switch', (39, 23),
                                   size=(20, 4),
                                   next_level='department')
        self.factory.create_entity('signpost', (95, 14), text='Lab\ncorridor',
                                   text_color='blue')
        self.factory.create_entity('level_switch', (90, 23),
                                   size=(20, 4),
                                   next_level='lab_corridor')
        self.factory.create_entity('signpost', (130, 14),
                                   text='Ghetto\ncorridor',
                                   text_color='orange')
        self.factory.create_entity('level_switch', (120, 23),
                                   size=(20, 4),
                                   next_level='ghetto_corridor')
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
        self.factory.create_entity('scientist_enemy', (100, 10))
        self.factory.create_entity('scientist_enemy', (150, 30))
        self.factory.create_entity('invis', (0, 51), size=(500, 9))

    # A dirty hack around passing the monologue to boss-talk properly. Three
    # methods cover three possible dialogues without affecting level itself
    # Later this hack would be replaced with properly drawing dialogue from
    # PlotManager directly in generate_level.
    # Same for _ghetto_expo_* methods


    def _boss_leave_it(self):
        """
        :return:
        """
        monologue=('So, on one hand, good work',
                   'Keeping the streets clean\nand all that',
                   'Nice.',
                   'On the other:\nyou\'ve stepped on some toes',
                   'which would rather\nstay un-stepped-on.',
                   'I like you, I really do.\nSo do me a favor',
                   'Leave this business be',
                   'It\'s not worth your job,\nlet alone your life.',
                   'Fight someone your own weight.',
                   'DISMISSED!')
        self._boss_talk(monologue=monologue, next_level='final')

    def _boss_good(self):
        monologue=('Good work.',
                   'Order restored,\nthe hostage safe...',
                   'Some punk ass busted, as well.',
                   'Really good work, cowboy.',
                   'One day you\'d make\na decent captain',
                   'Not just yet,\nbut one day you will.',
                   'Dismissed.')
        self._boss_talk(monologue=monologue)

    def _boss_bad(self):
        monologue=('What the fuck this was',
                   'Who do you think you are?',
                   'Bruce motherfucking Willis?',
                   'Going on a rescue mission alone\nis cool on one condition:',
                   'THAT YOUR FUCKING HOSTAGE SURVIVES',
                   'NOT FUCKING DIES, SURVIVES',
                   'You\'re gonna hang for this.'
                   'Dismissed, asshole.')
        self._boss_talk(monologue=monologue)

    def _ghetto_expo_hostage(self):
        self.generate_level('ghetto', 'corridor')
        self.factory.create_entity('cop_npc', (25, 10),
                                   monologue=('They\'ve besieged a lab\ndown the street',
                                              'No idea what\'s in the lab',
                                              'But you should hurry.',
                                              'There are definitely people\nlocked inside'))

    def _ghetto_expo_drugs(self):
        self.generate_level('ghetto', 'corridor', 'lab_fight')
        self.factory.create_entity('cop_npc', (25, 10),
                                   monologue=('Officer.',
                                              'There is a meth lab nearby',
                                              'Apparently the punks\nare just hired muscle,',
                                              'and some old guys\nin lab coats',
                                              'are behind it all',
                                              'You\'ll find the lab\ndown the street',
                                              'But be careful: these guys are\nanything but harmless'))

    def _ghetto_one(self):
        self.generate_level('ghetto', 'corridor', 'ghetto_expo_d')

    def _lab_fight(self):
        self.generate_level('lab', 'corridor', 'boss_leave_it')

    def _boss_talk(self, monologue=('Line one', 'Line two'),
                   next_level='main_menu'):
        self.dispatcher.add_event(BearEvent('set_bg_sound',
                                            'supercop_bg'))
        self.factory.create_entity('dept_bg', (0, 0), size=(500, 20))
        self.factory.create_entity('floor', (0, 20), size=(500, 30))
        self.factory.create_entity('invis', (0, 51), size=(500, 9))
        self.factory.create_entity('dept_wall_inner', (30, 0))
        self.factory.create_entity('dept_wall_inner', (18, 12))
        self.factory.create_entity('dept_wall_inner', (6, 24))
        self.factory.create_entity('dept_table_1', (48, 17))
        self.factory.create_entity('dept_chair_1', (49, 17))
        self.factory.create_entity('cop_npc', (52, 12), monologue='')
        self.factory.create_entity('dept_boss', (60, 8),
                                   monologue=monologue)
        self.factory.create_entity('dept_wall_inner', (120, 0))
        self.factory.create_entity('dept_wall_inner', (100, 20))
        self.factory.create_entity('dept_table_2', (105, 35))
        self.factory.create_entity('dept_chair_2', (125, 40))
        self.factory.create_entity('dept_locker', (131, 4))
        self.factory.create_entity('dept_locker', (127, 8))
        self.factory.create_entity('dept_locker', (124, 12))
        self.factory.create_entity('dept_bench', (143, 15))
        self.factory.create_entity('level_switch', (140, 20), size=(70, 30),
                                   next_level=next_level)

    def _department(self):
        """
        A tutorial level
        """
        self.dispatcher.add_event(BearEvent('set_bg_sound', 'supercop_bg'))
        self.factory.create_entity('level_switch', (415, 20),
                                   size=(85, 30), next_level='ghetto_one')
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
                                'text': 'Use your hands with Q and E\nWith no weapons equipped, you can punch',
                                'destroy_condition': 'timeout',
                                'lifetime': 8,
                                'vy': -1}),
                  SpawnItem(item='message',
                            pos=(50, 20),
                            size=(10, 20),
                            kwargs={
                                'text': 'Jump with spacebar',
                                'destroy_condition': 'timeout',
                                'lifetime': 8,
                                'vy': -1
                            }),
                  SpawnItem(item='message',
                            pos=(130, 20),
                            size=(10, 20),
                            kwargs={
                                'text': 'Pick up items with Z and C\nWith pistol, you can shoot\nat any distance,\neven offscreen',
                                'destroy_condition': 'timeout',
                                'lifetime': 8,
                                'vy': -1}),
                  SpawnItem(item='message',
                            pos=(150, 20),
                            size=(10, 8),
                            kwargs={
                                'text': 'You can look around with numpad',
                                'destroy_condition': 'timeout',
                                'lifetime': 8,
                                'vy': -1}),
                  SpawnItem(item='message',
                            pos=(170, 30),
                            size=(10, 20),
                            kwargs={
                                'text': 'Walk into ammo balls\n(like these)\nto reload your weapons',
                                'destroy_condition': 'timeout',
                                'lifetime': 8,
                                'vy': -1})
                  )
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
        self.factory.create_entity('ammo_pickup', (190, 35))
        self.factory.create_entity('ammo_pickup', (200, 35))
        self.factory.create_entity('ammo_pickup', (210, 35))
        self.factory.create_entity('dept_wall_inner', (226, 0))
        self.factory.create_entity('dept_wall_inner', (215, 11))
        # Corridor
        self.factory.create_entity('dept_bench', (240, 18))
        self.factory.create_entity('dept_wall_inner', (270, 0))
        self.factory.create_entity('dept_wall_inner', (259, 11))
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
