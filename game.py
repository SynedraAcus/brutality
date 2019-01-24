#! /usr/bin/env python3.6
import sys

from bear_hug.bear_hug import BearTerminal, BearLoop
from bear_hug.bear_utilities import copy_shape
from bear_hug.ecs_widgets import ECSLayout
from bear_hug.event import BearEvent, BearEventDispatcher
from bear_hug.resources import Atlas, XpLoader
from bear_hug.widgets import ClosingListener, LoggingListener

from entities import MapObjectFactory

#Bear_hug boilerplate
t = BearTerminal(font_path='cp437_12x12.png', size='85x60',
                 title='Brutality', filter=['keyboard', 'mouse'])
dispatcher = BearEventDispatcher()
loop = BearLoop(t, dispatcher)
dispatcher.register_listener(ClosingListener(), ['misc_input', 'tick'])

atlas = Atlas(XpLoader('test_atlas.xp'), 'test_atlas.json')
factory = MapObjectFactory(atlas, dispatcher)

# Init game screen
chars = [[' ' for _ in range(85)] for y in range(60)]
colors = copy_shape(chars, 'gray')
#TODO: Generate layout bg
layout = ECSLayout(chars, colors)
dispatcher.register_listener(layout, 'all')

# Debug event logger
logger = LoggingListener(sys.stderr)
dispatcher.register_listener(logger, ['ecs_add', 'ecs_collision'])

# Game-specific event types
dispatcher.register_event_type('brut_damage')
dispatcher.register_event_type('brut_heal')
t.start()
t.add_widget(layout, (0, 0), layer=1)

# Initial on-screen stuff
# Created before the loop starts, will be added on the first tick
factory.create_entity('cop', (10, 30))
factory.create_entity('barrel', (0, 50))
factory.create_entity('barrel', (10, 15))
factory.create_entity('target', (65, 30))
factory.create_entity('invis', (0, 0), size=(85, 15))
loop.run()
