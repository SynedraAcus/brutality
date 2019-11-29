#! /usr/bin/env python3.6

from argparse import ArgumentParser
import sys
import random

from bear_hug.bear_hug import BearTerminal, BearLoop
from bear_hug.bear_utilities import copy_shape
from bear_hug.ecs import EntityTracker
from bear_hug.ecs_widgets import ScrollableECSLayout
from bear_hug.event import BearEventDispatcher, BearEvent
from bear_hug.resources import Atlas, XpLoader
from bear_hug.widgets import Widget, ClosingListener, LoggingListener

from entities import MapObjectFactory
from listeners import ScrollListener, SavingListener
from widgets import HitpointBar, ItemWindow

parser = ArgumentParser('A game about beating people')
parser.add_argument('-s', type=str, help='Save file to load on startup')
parser.add_argument('--disable_sound', action='store_true')
args = parser.parse_args()

################################################################################
# Preparing stuff before game launch
################################################################################

#Bear_hug boilerplate
t = BearTerminal(font_path='cp437_12x12.png', size='81x61',
                 title='Brutality', filter=['keyboard', 'mouse'])
dispatcher = BearEventDispatcher()
loop = BearLoop(t, dispatcher)
dispatcher.register_listener(ClosingListener(), ['misc_input', 'tick'])
atlas = Atlas(XpLoader('test_atlas.xp'), 'test_atlas.json')

# Init game screen
chars = [[' ' for _ in range(250)] for y in range(50)]
colors = copy_shape(chars, 'gray')
layout = ScrollableECSLayout(chars, colors, view_pos=(0, 0), view_size=(81, 50))
dispatcher.register_listener(layout, 'all')
factory = MapObjectFactory(atlas, dispatcher, layout)

# Game-specific event types
# Expected values shown for each type
dispatcher.register_event_type('brut_damage') # value (int)
dispatcher.register_event_type('brut_heal') # value (int)
dispatcher.register_event_type('brut_focus')  # See listeners.ScrollListener
dispatcher.register_event_type('brut_temporary_focus') # Entity ID
dispatcher.register_event_type('brut_use_item') # Entity ID of used item
dispatcher.register_event_type('brut_use_hand') #hand entity ID
dispatcher.register_event_type('brut_pick_up') # owner entity ID, which hand (left or right), picked up entity ID


################################################################################
# Starting various listeners
################################################################################

dispatcher.register_listener(ScrollListener(layout=layout,
                                            distance=30),
                             ['brut_focus',
                              'brut_temporary_focus',
                             'ecs_move',
                             'ecs_destroy'])
dispatcher.register_listener(EntityTracker(), ['ecs_create', 'ecs_destroy'])
# Debug event logger
logger = LoggingListener(sys.stderr)
dispatcher.register_listener(logger, ['brut_damage', 'brut_pick_up'])
# Save test
saving = SavingListener()
dispatcher.register_listener(saving, 'key_down')
# TODO: find some free sounds that actually fit the game
if not args.disable_sound:
    from bear_hug.sound import SoundListener
    jukebox = SoundListener(sounds={'step': 'sounds/dshoof.wav',
                                    'shot': 'sounds/dsshotgn.wav'})
    dispatcher.register_listener(jukebox, 'play_sound')


################################################################################
# Starting the game terminal and adding main widgets
################################################################################

t.start()
t.add_widget(layout, (0, 0), layer=1)
# HUD elements
t.add_widget(Widget(*atlas.get_element('hud_bg')),
             (0, 50), layer=1)
hp_bar = HitpointBar(target_entity='cop_1')
dispatcher.register_listener(hp_bar, ('brut_damage', 'brut_heal'))
left_item_window = ItemWindow('cop_1', 'left', atlas)
dispatcher.register_listener(left_item_window, 'brut_pick_up')
t.add_widget(left_item_window, (1, 51), layer=2)
right_item_window = ItemWindow('cop_1', 'right', atlas)
dispatcher.register_listener(right_item_window, 'brut_pick_up')
t.add_widget(right_item_window, (66, 51), layer=2)
# Pseudo-events to let HUD know about the default fists
dispatcher.add_event(BearEvent('brut_pick_up', ('cop_1', 'left', 'fist_pseudo')))
dispatcher.add_event(BearEvent('brut_pick_up', ('cop_1', 'right', 'fist_pseudo')))
t.add_widget(hp_bar, (19, 54), layer=2)

################################################################################
# Creating initial entities
################################################################################

if args.s:
    for line in open(args.s):
        factory.load_entity_from_JSON(line.rstrip())

else:
    # Created before the loop starts, will be added on the first tick
    factory.create_entity('ghetto_bg', (0, 0), size=(250, 20))
    factory.create_entity('floor', (0, 20), size=(250, 30))
    # Add some garbage. Each heap contains at least one garbage bag and 2 to 5
    # other items (possibly incuding more bags)
    garbage_pos = []
    for _ in range(3):
        # Make sure garbage heaps are properly spaced
        while True:
            x = random.randint(0, 240)
            max_dist = len(garbage_pos) > 0\
                       and max((abs(x-i) for i in garbage_pos))\
                       or 1000
            if max_dist > 50:
                garbage_pos.append(x)
                break
        factory.create_entity('garbage_bag', (x, 18))
        for i in range(random.randint(3, 6)):
            t = random.choice(('can', 'can2', 'cigarettes', 'garbage_bag',
                               'bucket', 'pizza_box'))
            factory.create_entity(t, (x + random.randint(-5, 5),
                                      22 + random.randint(-2, 2)))
    # Spawning 5 punks at random pos
    # for _ in range(5):
    #     t = random.choice(('nunchaku_punk', 'bottle_punk'))
    #     x = random.randint(60, 240)
    #     y = random.randint(20, 30)
    #     factory.create_entity(t, (x, y))
    factory.create_entity('cop', (5, 25))
    factory.create_entity('broken_car', (50, 20))
    # factory.create_entity('target', (50, 20))
    # factory.create_entity('target', (90, 20))
    # factory.create_entity('pistol', (65, 30))
    # factory.create_entity('nunchaku', (45, 40))
    factory.create_entity('nunchaku_punk', (210, 8))
    factory.create_entity('bottle_punk', (230, 20))
    factory.create_entity('bottle_punk', (220, 32))

    # Messages and stuff
    factory.create_entity('message', (20, 20),
                          text='Walk with WASD or arrow keys.',
                          destroy_condition='timeout',
                          vy=-2, lifetime=5)
    factory.create_entity('message_spawner', (20, 20),
                          xsize=8, ysize=30,
                          entity_filter=lambda x: x == 'cop_1',
                          text='Use your hands with Q and E\nCurrently, you can only punch with your fists,\nso beat the shit out of this target',
                          destroy_condition='timeout', lifetime=5,
                          vy=-2)
    factory.create_entity('message_spawner', (55, 20),
                          xsize=8, ysize=30,
                          entity_filter=lambda x: x == 'cop_1',
                          text='Pick up items with Z and C\nWith pistol, you can shoot\nat any distance,\neven offscreen',
                          destroy_condition='timeout', lifetime=5,
                          vy=-2)
    factory.create_entity('message_spawner', (95, 20),
                          xsize=8, ysize=30,
                          entity_filter=lambda x: x == 'cop_1',
                          text='Now go along and finish these punks!',
                          destroy_condition='timeout', lifetime=5,
                          vy=-2)
loop.run()

# TODO: directions for corpses
# TODO: redraw ghetto BG
# Currently they look like it's possible to turn into some alley, which it isn't
