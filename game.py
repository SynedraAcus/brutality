#! /usr/bin/env python3.6

from argparse import ArgumentParser
import sys

from bear_hug.bear_hug import BearTerminal, BearLoop
from bear_hug.bear_utilities import copy_shape
from bear_hug.ecs import EntityTracker
from bear_hug.ecs_widgets import ScrollableECSLayout
from bear_hug.event import BearEventDispatcher, BearEvent
from bear_hug.resources import Atlas, XpLoader
from bear_hug.widgets import Widget, ClosingListener, LoggingListener

from entities import MapObjectFactory
from listeners import ScrollListener, SavingListener
from widgets import HitpointBar

parser = ArgumentParser('A game about beating people')
parser.add_argument('-s', type=str, help='Save file to load on startup')
parser.add_argument('--disable_sound', action='store_true')
args = parser.parse_args()

################################################################################
# Preparing stuff before game launch
################################################################################

#Bear_hug boilerplate
t = BearTerminal(font_path='cp437_12x12.png', size='81x72',
                 title='Brutality', filter=['keyboard', 'mouse'])
dispatcher = BearEventDispatcher()
loop = BearLoop(t, dispatcher)
dispatcher.register_listener(ClosingListener(), ['misc_input', 'tick'])
atlas = Atlas(XpLoader('test_atlas.xp'), 'test_atlas.json')

# Init game screen
chars = [[' ' for _ in range(150)] for y in range(50)]
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


################################################################################
# Starting various listeners
################################################################################

dispatcher.register_listener(ScrollListener(layout=layout),
                             ['brut_focus',
                              'brut_temporary_focus',
                             'ecs_move',
                             'ecs_destroy'])
dispatcher.register_listener(EntityTracker(), ['ecs_create', 'ecs_destroy'])
# Debug event logger
logger = LoggingListener(sys.stderr)
dispatcher.register_listener(logger, ['brut_damage'])
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
# Starting the game terminal and adding main ECSLayout
################################################################################

t.start()
t.add_widget(layout, (0, 0), layer=1)
t.add_widget(Widget(*atlas.get_element('hud_bg')),
             (0, 51), layer=1)
hp_bar = HitpointBar(target_entity='cop_1')
dispatcher.register_listener(hp_bar, ('brut_damage', 'brut_heal'))
t.add_widget(hp_bar, (19, 55), layer=2)

################################################################################
# Creating initial entities
################################################################################

if args.s:
    for line in open(args.s):
        factory.load_entity_from_JSON(line.rstrip())

else:
    # Created before the loop starts, will be added on the first tick
    factory.create_entity('wall', (0, 0), size=(150, 20))
    factory.create_entity('floor', (0, 20), size=(150, 30))
    factory.create_entity('cop', (10, 25))
    factory.create_entity('nunchaku_punk', (40, 20))
    factory.create_entity('barrel', (75, 15))
    factory.create_entity('barrel', (61, 40))
    factory.create_entity('bottle_punk', (70, 20))
loop.run()

# TODO: Items that can be picked up
# TODO: HUD: HP display
# TODO: HUD: item display
# TODO: corpses of enemies
# TODO: MessageEntity
