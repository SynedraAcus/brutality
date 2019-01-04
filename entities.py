from bear_hug.ecs import Entity, Component, WidgetComponent, PositionComponent
from bear_hug.widgets import SimpleAnimationWidget, Animation, Widget
from bear_hug.event import BearEvent

from components import WalkerComponent, WalkerCollisionComponent

class Character(Entity):
    """
    An entity subclass for stuff that can be characters
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.direction = 'r'
    

class MapObjectFactory:
    def __init__(self, atlas, dispatcher):
        self.dispatcher = dispatcher
        self.atlas = atlas
        self.counts = {}
        
    def create_barrel(self, x, y):
        if 'Barrel' in self.counts:
            self.counts['Barrel'] += 1
        else:
            self.counts['Barrel'] = 1
        barrel_entity = Entity(id='Barrel{}'.format(self.counts['Barrel']))
        widget = SimpleAnimationWidget(Animation((self.atlas.get_element(
                                                      'barrel_1'),
                                                  self.atlas.get_element(
                                                      'barrel_2')),
                                                  2),
                                       emit_ecs=True)
        widget_component = WidgetComponent(self.dispatcher, widget,
                                           owner=barrel_entity)
        position_component = PositionComponent(self.dispatcher, x=x, y=y,
                                               owner=barrel_entity)
        barrel_entity.add_component(position_component)
        barrel_entity.add_component(widget_component)
        return barrel_entity
    
    def create_cop(self, x, y):
        if 'Cop' in self.counts:
            self.counts['Cop'] += 1
        else:
            self.counts['Cop'] = 1
        cop_entity = Entity(id='Cop{}'.format(self.counts['Barrel']))
        widget = Widget(*self.atlas.get_element('cop_r'))
        widget_component = WidgetComponent(self.dispatcher, widget,
                                           owner=cop_entity)
        position_component = WalkerComponent(self.dispatcher, x=x, y=y,
                                               owner=cop_entity)
        collision_component = WalkerCollisionComponent(self.dispatcher)
        cop_entity.add_component(position_component)
        cop_entity.add_component(widget_component)
        cop_entity.add_component(collision_component)
        return cop_entity
