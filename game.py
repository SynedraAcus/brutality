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

from entities import MapObjectFactory, Multiatlas
from mapgen import LevelManager
from listeners import ScrollListener, SavingListener, SpawnItem,\
    SpawningListener, LevelSwitchListener
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
atlas = Multiatlas((Atlas(XpLoader('test_atlas.xp'), 'test_atlas.json'),
                    Atlas(XpLoader('ghetto_bg.xp'), 'ghetto_bg.json')))
                   # TODO: add dept to multiatlas

# Init game screen
chars = [[' ' for _ in range(500)] for y in range(60)]
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
# Starting various listeners
################################################################################

dispatcher.register_listener(ScrollListener(layout=layout,
                                            distance=30),
                             ['brut_focus',
                              'brut_temporary_focus',
                             'tick', 'ecs_move',
                             'ecs_destroy'])
dispatcher.register_listener(EntityTracker(), ['ecs_create', 'ecs_destroy'])
# Debug event logger
logger = LoggingListener(sys.stderr)
dispatcher.register_listener(logger, ['brut_damage', 'brut_pick_up'])
# Save test
saving = SavingListener()
dispatcher.register_listener(saving, 'key_down')
# TODO: find some free sounds that actually fit the game
# TODO: correct paths for sounds, atlas and font
if not args.disable_sound:
    from bear_hug.sound import SoundListener
    jukebox = SoundListener(sounds={'step': 'sounds/step.wav',
                                    'shot': 'sounds/shot.wav',
                                    'punch': 'sounds/punch.wav'})
    dispatcher.register_listener(jukebox, 'play_sound')

# Message spawner for tutorial messages
# TODO: un-hardcode player ID in tutorial SpawnerListener
spawner = SpawningListener('cop_1', factory=factory)
dispatcher.register_listener(spawner, 'ecs_move')

# Level generator
levelgen = LevelManager(dispatcher, factory,
                        spawner=spawner, player_entity='cop_1')

# Level switcher
level_switch = LevelSwitchListener('cop_1', level_manager=levelgen,
                                   level_sequence=['ghetto_test', 'ghetto_tutorial'])
dispatcher.register_listener(level_switch, 'ecs_move')
levelgen.level_switch = level_switch

################################################################################
# Creating initial entities
################################################################################

if args.s:
    for line in open(args.s):
        factory.load_entity_from_JSON(line.rstrip())
    # ScrollListener is initialized anew, so the scroll position is not kept
    dispatcher.add_event(BearEvent('brut_focus', 'cop_1'))

else:
    factory.create_entity('cop', (5, 25))
    # RUn a single tick so EntityTracker is aware of everything before level
    # is being generated
    loop._run_iteration(0)
    levelgen.set_level('ghetto_test')


# Actually starting
loop.run()

# TODO: directions for corpses
# TODO: redraw ghetto BG
# Currently they look like it's possible to turn into some alley, which it isn't
# TODO: Z-levels
