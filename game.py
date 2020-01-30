#! /usr/bin/env python3.6

from argparse import ArgumentParser
import sys
import json

from bear_hug.bear_hug import BearTerminal, BearLoop
from bear_hug.bear_utilities import copy_shape
from bear_hug.ecs import EntityTracker
from bear_hug.ecs_widgets import ScrollableECSLayout
from bear_hug.event import BearEventDispatcher, BearEvent
from bear_hug.resources import Atlas, Multiatlas, XpLoader
from bear_hug.widgets import Widget, ClosingListener, LoggingListener

from entities import EntityFactory
from mapgen import LevelManager
from listeners import ScrollListener, SavingListener, LoadingListener, SpawnItem,\
    SpawningListener, LevelSwitchListener, MenuListener
from widgets import HitpointBar, ItemWindow, MenuItem, MenuWidget

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
                    Atlas(XpLoader('ghetto_bg.xp'), 'ghetto_bg.json'),
                    Atlas(XpLoader('department.xp'), 'department.json')))

# Init game screen
chars = [[' ' for _ in range(500)] for y in range(60)]
colors = copy_shape(chars, 'gray')
layout = ScrollableECSLayout(chars, colors, view_pos=(0, 0), view_size=(81, 50))
dispatcher.register_listener(layout, 'all')
factory = EntityFactory(atlas, dispatcher, layout)

# Game-specific event types
# Expected values shown for each type
# Combat system
dispatcher.register_event_type('brut_damage') # value (int)
dispatcher.register_event_type('brut_heal') # value (int)
# Item manipulations
dispatcher.register_event_type('brut_use_item') # Entity ID of used item
dispatcher.register_event_type('brut_use_hand') #hand entity ID
dispatcher.register_event_type('brut_pick_up') # owner entity ID, which hand (left or right), picked up entity ID
# View operations
dispatcher.register_event_type('brut_focus')  # See listeners.ScrollListener
dispatcher.register_event_type('brut_temporary_focus') # Entity ID
# Service
dispatcher.register_event_type('brut_open_menu') # Value ignored
dispatcher.register_event_type('brut_close_menu') # Value ignored
dispatcher.register_event_type('brut_save_game') # Path to savefile
dispatcher.register_event_type('brut_load_game') # Path to savefile


################################################################################
# Starting the game terminal and adding main widgets
################################################################################

t.start()
t.add_widget(layout, (0, 0), layer=1)
# HUD elements
t.add_widget(Widget(*atlas.get_element('hud_bg')),
             (0, 50), layer=1)
# TODO: remove cop_1 and create variable for player char ID
# The current system in bunch of places relies on player's entity ID always
# being cop_1. This may not be correct and normally should be stored as a
# variable. But this is probably not gonna be important until saves save stuff
# besides entities
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
dispatcher.register_listener(logger, ['brut_damage', 'brut_pick_up', 'set_bg_sound'])

# TODO: TSLD sounds
# TODO: correct paths for sounds, atlas and font
if not args.disable_sound:
    from bear_hug.sound import SoundListener
    jukebox = SoundListener(sounds={'step': 'sounds/step.wav',
                                    'shot': 'sounds/shot.wav',
                                    'punch': 'sounds/punch.wav',
                                    'supercop_bg': 'sounds/supercop.wav',
                                    'punk_bg': 'sounds/punk_bg.wav',
                                    'test_beat': '117856__day-tripper13__breaks-beat-4811.wav'})
    dispatcher.register_listener(jukebox,
                                 ['play_sound', 'tick', 'set_bg_sound'])
    dispatcher.add_event(BearEvent('set_bg_sound', 'supercop_bg'))

# Message spawner for tutorial messages
spawner = SpawningListener('cop_1', factory=factory)
dispatcher.register_listener(spawner, 'ecs_move')

# Level generator
levelgen = LevelManager(dispatcher, factory,
                        spawner=spawner, player_entity='cop_1')

# Level switcher
level_switch = LevelSwitchListener('cop_1', level_manager=levelgen,
                                   level_sequence={
                                       'ghetto_test': 'department',
                                       'department': 'ghetto_tutorial'})
dispatcher.register_listener(level_switch, 'ecs_move')
levelgen.level_switch = level_switch

# Saving and loading
saving = SavingListener()
dispatcher.register_listener(saving, 'brut_save_game')
loading = LoadingListener(dispatcher, factory, levelgen, loop)
dispatcher.register_listener(loading, 'brut_load_game')
################################################################################
# Test menu
################################################################################

menu_items = [MenuItem('Continue', color='white', highlight_color='blue',
                       action=lambda: BearEvent('brut_close_menu', None)),
              MenuItem(f'Plot (TBD)', color='white', highlight_color='blue',
                       action=lambda: print('Button 2')),
              MenuItem(f'Items (TBD)', color='white', highlight_color='blue',
                       action=lambda: print('Button 3')),
              MenuItem(f'Load', color='white', highlight_color='blue',
                       action=lambda: BearEvent('brut_load_game',
                                                'save.json')),
              MenuItem(f'Save', color='white', highlight_color='blue',
                       action=lambda: BearEvent('brut_save_game',
                                                'save.json')),
              MenuItem(f'Quit', color='white', highlight_color='blue',
                       action=lambda: BearEvent('misc_input', 'TK_CLOSE'))
              ]
menu = MenuWidget(dispatcher, terminal=t, items=menu_items, items_pos=(5, 6),
                  background=Widget(*atlas.get_element('police_menu_bg')))
menu_listener = MenuListener(dispatcher, terminal=t,
                             menu_widget=menu, menu_pos=(6, 6))
dispatcher.register_listener(menu_listener, ['key_down', 'tick',
                                             'brut_open_menu',
                                             'brut_close_menu'])
################################################################################
# Creating initial entities
################################################################################

if args.s:
    dispatcher.add_event(BearEvent('brut_load_game', 'save.json'))

else:
    factory.create_entity('cop', (5, 25))
    # RUn a single tick so EntityTracker is aware of everything before level
    # is being generated
    loop._run_iteration(0)
    levelgen.set_level('ghetto_test')


# Actually starting
loop.run()

# TODO: redraw ghetto BG
# Currently they look like it's possible to turn into some alley, which it isn't
# TODO: Z-levels-aware collision detector