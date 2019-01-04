#! /usr/bin/env python3.6

from bear_hug.bear_hug import BearTerminal, BearLoop
from bear_hug.bear_utilities import copy_shape
from bear_hug.ecs_widgets import ECSLayout
from bear_hug.event import BearEvent, BearEventDispatcher
from bear_hug.resources import Atlas, XpLoader
from bear_hug.widgets import ClosingListener

from entities import MapObjectFactory

# Creating singletons
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
layout = ECSLayout(chars, colors)
dispatcher.register_listener(layout, 'all')

t.start()
t.add_widget(layout, (0, 0), layer=1)
# Initial on-screen stuff

# Top collider to prevent walking into BG
collider = factory.create_invisible_collider(0, 0, (85, 15))
layout.add_entity(collider)
dispatcher.add_event(BearEvent(event_type='ecs_add',
                               event_value=(collider.id,
                                            collider.position.x,
                                            collider.position.y)))
barrel1 = factory.create_barrel(45, 40)
layout.add_entity(barrel1)
dispatcher.add_event(BearEvent(event_type='ecs_add',
                               event_value=(barrel1.id,
                                            barrel1.position.x,
                                            barrel1.position.y)))
cop = factory.create_cop(10, 30)
layout.add_entity(cop)
dispatcher.add_event(BearEvent(event_type='ecs_add',
                               event_value=(cop.id,
                                            cop.position.x,
                                            cop.position.y)))

loop.run()
