#! /usr/bin/env python3.6
import sys

from bear_hug.bear_hug import BearTerminal, BearLoop
from bear_hug.bear_utilities import copy_shape
from bear_hug.ecs_widgets import ScrollableECSLayout
from bear_hug.event import BearEventDispatcher
from bear_hug.resources import Atlas, XpLoader
from bear_hug.sound import SoundListener
from bear_hug.widgets import ClosingListener, LoggingListener

from entities import MapObjectFactory
from listeners import ScrollListener, EntityTracker
from widgets import PatternGenerator

#Bear_hug boilerplate
t = BearTerminal(font_path='cp437_12x12.png', size='85x60',
                 title='Brutality', filter=['keyboard', 'mouse'])
dispatcher = BearEventDispatcher()
loop = BearLoop(t, dispatcher)
dispatcher.register_listener(ClosingListener(), ['misc_input', 'tick'])

atlas = Atlas(XpLoader('test_atlas.xp'), 'test_atlas.json')

# Init game screen
chars = [[' ' for _ in range(150)] for y in range(60)]
colors = copy_shape(chars, 'gray')
patterns = PatternGenerator(atlas)
upper_bg = patterns.generate_tiled('brick_tile', (150, 30))
lower_bg = patterns.tile_randomly('floor_tile_1',
                                  'floor_tile_2',
                                  'floor_tile_3',
                                  size=(150, 30))
bg = patterns.stack_boxes(upper_bg, lower_bg, order='vertical')
layout = ScrollableECSLayout(*bg, view_pos=(0, 0), view_size=(85, 60))
dispatcher.register_listener(layout, 'all')
factory = MapObjectFactory(atlas, dispatcher, layout)



# Game-specific event types
dispatcher.register_event_type('brut_damage')
dispatcher.register_event_type('brut_heal')
dispatcher.register_event_type('brut_focus')  # See listeners.ScrollListener
dispatcher.register_event_type('brut_temporary_focus')

# TODO: find some free sounds that actually fit the game
jukebox = SoundListener(sounds={'step': 'sounds/dshoof.wav',
                                'shot': 'sounds/dsshotgn.wav'})
dispatcher.register_listener(jukebox, 'play_sound')

# Launching the actual game
dispatcher.register_listener(ScrollListener(layout=layout),
                             ['brut_focus',
                              'brut_temporary_focus',
                             'ecs_move',
                             'ecs_destroy'])
dispatcher.register_listener(EntityTracker(), ['ecs_create', 'ecs_destroy'])
t.start()
t.add_widget(layout, (0, 0), layer=1)

# Debug event logger
logger = LoggingListener(sys.stderr)
dispatcher.register_listener(logger, ['ecs_add', 'ecs_collision', 'brut_damage'])

# Initial on-screen stuff
# Created before the loop starts, will be added on the first tick
factory.create_entity('cop', (10, 30))
factory.create_entity('barrel', (75, 25))
factory.create_entity('barrel', (61, 50))
factory.create_entity('nunchaku_punk', (65, 30))
# factory.create_entity('target', (65, 30))
factory.create_entity('invis', (0, 0), size=(150, 15))
factory.create_entity('invis', (0, 15), size=(2, 45))
factory.create_entity('invis', (148, 15), size=(2, 45))
factory.create_entity('invis', (0, 58), size=(100, 2))
loop.run()
