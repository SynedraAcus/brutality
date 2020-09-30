#! /usr/bin/env python3.6

import sys
import traceback
from argparse import ArgumentParser
from os import path

from bear_hug.bear_hug import BearTerminal, BearLoop
from bear_hug.bear_utilities import copy_shape
from bear_hug.ecs import EntityTracker, CollisionListener
from bear_hug.ecs_widgets import ScrollableECSLayout
from bear_hug.event import BearEventDispatcher, BearEvent
from bear_hug.resources import Atlas, Multiatlas, XpLoader
from bear_hug.widgets import Widget, ClosingListener, LoggingListener, \
    MenuWidget, MenuItem

from entities import EntityFactory
from listeners import ScrollListener, SavingListener, LoadingListener, \
    SpawningListener, LevelSwitchListener, MenuListener, \
    ItemDescriptionListener, ScoreListener, SplashListener, ConfigListener
from mapgen import LevelManager, restart
from plot import Goal
from widgets import HitpointBar, ItemWindow, ScoreWidget

parser = ArgumentParser('A game about beating people')
parser.add_argument('-s', type=str, help='Save file to load on startup')
parser.add_argument('--disable_sound', action='store_true',
                    help='Disable all sound. Prevents simpleaudio from importing')
args = parser.parse_args()

################################################################################
# Preparing stuff before game launch
################################################################################

path_base = path.split(sys.argv[0])[0]
#Bear_hug boilerplate
t = BearTerminal(font_path=path.join(path_base, 'cp437_12x12.png'),
                 size='81x61', title='Brutality', filter=['keyboard', 'mouse'])
dispatcher = BearEventDispatcher()
loop = BearLoop(t, dispatcher)
dispatcher.register_listener(ClosingListener(), ['misc_input', 'tick'])
t.start()

################################################################################
# Showing splash screen while stuff loads
#
################################################################################

splash_loader = XpLoader('splash.xp')
chars, colors = splash_loader.get_image()
splash_widget = Widget(chars, colors)
t.add_widget(splash_widget, layer=10)
chars = [[9608 for x in range(81)] for y in range(61)]
colors = copy_shape(chars, '#000000')
splash_underlay = Widget(chars, colors)
t.add_widget(splash_underlay, layer=9)

# This event type is only emitted by main menu level generator
dispatcher.register_event_type('brut_remove_splash')
splash_listener = SplashListener(dispatcher=dispatcher,
                                 terminal=t,
                                 widgets=[splash_widget, splash_underlay])
dispatcher.register_listener(splash_listener, ('key_down',
                                               'brut_remove_splash'))
dispatcher.register_listener(splash_widget, 'key_down')


################################################################################
# Loading assets and initializing stuff
#
################################################################################
atlas = Multiatlas((Atlas(XpLoader(path.join(path_base, 'test_atlas.xp')),
                          path.join(path_base, 'test_atlas.json')),
                    Atlas(XpLoader(path.join(path_base, 'ghetto_bg.xp')),
                          path.join(path_base, 'ghetto_bg.json')),
                    Atlas(XpLoader(path.join(path_base, 'department.xp')),
                          path.join(path_base, 'department.json')),
                    Atlas(XpLoader(path.join(path_base, 'scientists.xp')),
                          path.join(path_base, 'scientists.json')),
                    Atlas(XpLoader(path.join(path_base, 'level_headers.xp')),
                          path.join(path_base, 'level_headers.json'))))

chars = [[' ' for _ in range(500)] for y in range(60)]
colors = copy_shape(chars, 'gray')
layout = ScrollableECSLayout(chars, colors, view_pos=(0, 0), view_size=(81, 50))
dispatcher.register_listener(layout, 'all')
factory = EntityFactory(atlas, dispatcher, layout)

################################################################################
# Game-specific event types
# Expected values for each type shown in comments
################################################################################

# Combat system
dispatcher.register_event_type('brut_damage') # EntityID, value (int)
dispatcher.register_event_type('brut_heal') # EntityID, value (int)
# Item manipulations
dispatcher.register_event_type('brut_use_item') # Entity ID of used item
dispatcher.register_event_type('brut_use_hand') #hand entity ID
dispatcher.register_event_type('brut_pick_up') # owner entity ID, which hand (left or right), picked up entity ID
dispatcher.register_event_type('brut_change_ammo') # Item entity ID, new ammo value
dispatcher.register_event_type('brut_score') # Value (add to score)
dispatcher.register_event_type('brut_reset_score') # Value (set score to)
# View operations
dispatcher.register_event_type('brut_focus')  # See listeners.ScrollListener
dispatcher.register_event_type('brut_temporary_focus') # Entity ID
# Service
dispatcher.register_event_type('brut_open_menu') # Value ignored
dispatcher.register_event_type('brut_close_menu') # Value ignored
dispatcher.register_event_type('brut_show_items') # Value ignored
dispatcher.register_event_type('brut_save_game') # Path to savefile
dispatcher.register_event_type('brut_load_game') # Path to savefile
dispatcher.register_event_type('brut_change_config') # Config key and new value


################################################################################
# Adding main game widgets
################################################################################

t.add_widget(layout, (0, 0), layer=1)
# HUD elements
t.add_widget(Widget(*atlas.get_element('hud_bg')),
             (0, 50), layer=1)
# TODO: remove cop_1 and create variable for player char ID
# The current system in bunch of places relies on player's entity ID always
# being cop_1. This may not be correct and normally should be stored as a
# variable. But this is probably not gonna be important until later
hp_bar = HitpointBar(target_entity='cop_1')
dispatcher.register_listener(hp_bar, ('brut_damage', 'brut_heal'))
left_item_window = ItemWindow('cop_1', 'left', atlas)
dispatcher.register_listener(left_item_window,
                             ('brut_pick_up', 'brut_change_ammo'))
t.add_widget(left_item_window, (1, 51), layer=2)
right_item_window = ItemWindow('cop_1', 'right', atlas)
dispatcher.register_listener(right_item_window,
                             ('brut_pick_up', 'brut_change_ammo'))
t.add_widget(right_item_window, (66, 51), layer=2)
# Pseudo-events to let HUD know about the default fists
dispatcher.add_event(BearEvent('brut_pick_up', ('cop_1', 'left',
                                                'fist_pseudo')))
dispatcher.add_event(BearEvent('brut_pick_up', ('cop_1', 'right',
                                                'fist_pseudo')))
t.add_widget(hp_bar, (19, 54), layer=2)

################################################################################
# Starting various listeners
################################################################################

# Collision
collision = CollisionListener()
dispatcher.register_listener(collision, ['ecs_create', 'ecs_destroy',
                                         'ecs_remove', 'ecs_add',
                                         'ecs_move'])
# Screen scrolling
dispatcher.register_listener(ScrollListener(layout=layout,
                                            distance=30),
                             ['brut_focus',
                              'brut_temporary_focus',
                             'tick', 'ecs_move',
                             'ecs_destroy'])
dispatcher.register_listener(EntityTracker(), ['ecs_create', 'ecs_destroy'])
# Debug event logger
logger = LoggingListener(open(path.join(path_base, 'run.log'), mode='w'))
dispatcher.register_listener(logger, ['ecs_add', 'ecs_remove', 'ecs_destroy',
                                      'brut_change_config', 'play_sound'])
# Config
config = ConfigListener()
dispatcher.register_listener(config, 'brut_change_config')
# Sound
if not args.disable_sound:
    sound_files = {'step': 'step.wav',
                   'shot': 'shot.wav',
                   'fist': 'fist.wav',
                   'shiv': 'shiv.wav',
                   'emitter': 'emitter.wav',
                   'punch': 'punch.wav',
                   'spark': 'spark.wav',
                   'nunchaku': 'nunchaku_wave.wav',
                   'reload': 'pistol_reload.wav',
                   'pistol_empty': 'pistol_trigger.wav',
                   'molotov_break': 'molotov_brake.wav',
                   'molotov_fire': 'molotov_fire.wav',
                   'molotov_throw': 'molotov_throw.wav',
                   'balloon': 'balloon.wav',
                   'blue_machine': 'blue_machine.wav',
                   'coin': 'coin.wav',
                   'coin_drop': 'coin_drop.wav',
                   'drive': 'drive.wav',
                   'supercop_bg': 'supercop.wav',
                   'ghetto_walk_bg': 'ghetto_walk.wav',
                   'punk_bg': 'punk_bg.wav',
                   'lab_bg': 'laboratory.wav',
                   'punk_hit': 'punk_hey.wav',
                   'punk_death': 'punk_ho.wav',
                   'cop_hit': 'cop_dmg.wav',
                   'cop_death': 'cop_death.wav',
                   'male_dmg': 'male_dmg.wav',
                   'female_dmg': 'fem_dmg.wav',
                   'male_death': 'male_death.wav',
                   'female_death': 'fem_death.wav',
                   'male_phrase_1': 'male_phrase_1.wav',
                   'male_phrase_2': 'male_phrase_2.wav',
                   'male_phrase_3': 'male_phrase_3.wav',
                   'male_phrase_4': 'male_phrase_4.wav',
                   'male_phrase_5': 'male_phrase_5.wav',
                   'female_phrase_1': 'f_scientist_1.wav',
                   'female_phrase_2': 'f_scientist_2.wav',
                   'female_phrase_3': 'f_scientist_3.wav',
                   'female_phrase_4': 'f_scientist_4.wav',
                   'female_phrase_5': 'f_scientist_5.wav',
                   'bandage': 'bandage.wav',
                   'target_hit': 'target.wav',
                   'item_drop': 'item_drop.wav',
                   'item_grab': 'item_grab.wav',
                   'menu': 'menu_switch.wav',
                   'switch_on': 'switch_on.wav',
                   'switch_off': 'switch_off.wav'}
    from bear_hug.sound import SoundListener
    sounds = {}
    for file in sound_files:
        sounds[file] = path.join(path_base, 'sounds', sound_files[file])
    jukebox = SoundListener(sounds=sounds)
    dispatcher.register_listener(jukebox,
                                 ['play_sound', 'tick', 'set_bg_sound'])

# Spawner for creating various stuff when player walks to a predetermined area
# currently only used for tutorial messages, but can be employed by mapgen to eg
# drop enemies behind the player's back
spawner = SpawningListener('cop_1', factory=factory)
dispatcher.register_listener(spawner, 'ecs_move')

# Level generator
levelgen = LevelManager(dispatcher, factory,
                        spawner=spawner, player_entity='cop_1')

# Level switcher
level_switch = LevelSwitchListener('cop_1', level_manager=levelgen,
                                   factory=factory)
dispatcher.register_listener(level_switch, ('ecs_move', 'ecs_collision',
                                            'tick', 'service'))
levelgen.level_switch = level_switch

# Saving and loading
saving = SavingListener()
dispatcher.register_listener(saving, 'brut_save_game')
loading = LoadingListener(dispatcher, factory, levelgen, loop)
dispatcher.register_listener(loading, 'brut_load_game')\

# Score tracking
score_widget = ScoreWidget(score=0)
t.add_widget(score_widget, (41, 51))
score = ScoreListener(dispatcher=dispatcher,
                      terminal=t,
                      score_widget=score_widget,
                      score=0,
                      player_entity='cop_1', heal_frequency=10)
dispatcher.register_listener(score, ('tick', 'brut_score', 'brut_reset_score'))

################################################################################
# Goals
# Not actually used anywhere, will be developed later
################################################################################


punk_fight = Goal(name='punk_fight',
                  description='I was sent to throw some punks\nout of the street',
                  enemy_factions=('punks', ),
                  ally_factions=('cops', 'scientists', 'civilians'),
                  location='ghetto',
                  level_types=('corridor', ),
                  exposition_monologues=(None, ),
                  next_on_win=('scientist_drugs', 'scientist_hostage')
                  )
sc_drugs = Goal(name='scientist_drugs',
                description='Apparently, they were protecting a drug lab',
                enemy_factions=('punks', 'scientists'),
                ally_factions=('cops', 'civilians'),
                location='ghetto',
                level_types=('corridor', ),
                exposition_monologues=('Hey you',
                                       'The cop',
                                       'Look out: there is a drug lab\ndown the street',
                                       'and they wouldn\'t just\nlet you walk in'),
                next_on_win=('drug_lab')
                )


################################################################################
# Game menu
################################################################################

menu_items = [MenuItem('Continue', color='white', highlight_color='blue',
                       action=lambda: BearEvent('brut_close_menu', None)),
              MenuItem('Restart', color='white', highlight_color='blue',
                       action=lambda: restart(levelgen, factory, dispatcher, loop)),
              MenuItem('Items', color='white', highlight_color='blue',
                       action=lambda: BearEvent('brut_show_items', None)),
              MenuItem(f'Load (TBD)', color='white', highlight_color='blue',
                       action=lambda: BearEvent('brut_load_game',
                                                'save.json')),
              MenuItem(f'Save (TBD)', color='white', highlight_color='blue',
                       action=lambda: BearEvent('brut_save_game',
                                                'save.json')),
              MenuItem(f'Quit', color='white', highlight_color='blue',
                       action=lambda: BearEvent('misc_input', 'TK_CLOSE'))
              ]
menu = MenuWidget(dispatcher, terminal=t, items=menu_items, items_pos=(5, 6),
                  background=Widget(*atlas.get_element('police_menu_bg')),
                  switch_sound='menu', activation_sound='menu')
menu_listener = MenuListener(dispatcher, terminal=t,
                             menu_widget=menu, menu_pos=(6, 6))
dispatcher.register_listener(menu_listener, ['key_down', 'tick',
                                             'brut_open_menu',
                                             'brut_close_menu'])
item_descriptions = ItemDescriptionListener(dispatcher, terminal=t,
                                            tracked_entity='cop_1')
dispatcher.register_listener(item_descriptions, ['brut_show_items',
                                                 'brut_close_menu',
                                                 'key_down'])

################################################################################
# Creating initial entities
################################################################################

if args.s:
    dispatcher.add_event(BearEvent('brut_load_game', 'save.json'))

else:
    factory.create_entity('cop', (5, 25))
    # Run a single tick so EntityTracker is aware of player before level
    # starts generating
    loop._run_iteration(0)
    levelgen.set_level('main_menu')


# Actually starting
try:
    loop.run()
except Exception:
    # Should the game crash with an unhandled exception, it is logged to the
    # file
    print(''.join(traceback.format_exception(*sys.exc_info())),
          file=open(path.join(path_base, 'crash_exception.log'), mode='w'))

# TODO: redraw ghetto BG
# Currently they look like it's possible to turn into some alley, which it isn't

# TODO: write appropriate item descriptions
# Not really pressing, but it's better to avoid stupid jokes in item
# descriptions. The general tone should be *somewhat* serious.

# TODO: highlight collectables somehow
# Currently they are not very visible, especially with bright punk corpses.

# TODO: some new enemy types
# Test punks are okay but there should be some more

# TODO: more indoor barriers
# Stuff like flower pots, small tables, etc; basically things useful for any
# indoor level

# TODO: additional control layouts (arrows + ASZX? WASD + JKL;?)

# TODO: bank level

# TODO: settings system
# At least something minimal, like enable/disable sound and fullscreen

#TODO: neon sound in splash screen