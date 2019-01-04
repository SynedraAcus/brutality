from bear_hug.bear_utilities import copy_shape
from bear_hug.ecs import Entity, WidgetComponent, PositionComponent
from bear_hug.widgets import SimpleAnimationWidget, Animation, Widget

from components import WalkerComponent, WalkerCollisionComponent, \
    SwitchWidgetComponent
from widgets import SwitchingWidget


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
        widget = SwitchingWidget({'r_1': self.atlas.get_element('cop_r_1'),
                                  'r_2': self.atlas.get_element('cop_r_2'),
                                  'l_1': self.atlas.get_element('cop_l_1'),
                                  'l_2': self.atlas.get_element('cop_l_2')},
                                 initial_image='r_1')
        widget_component = SwitchWidgetComponent(self.dispatcher, widget,
                                                 owner=cop_entity)
        position_component = WalkerComponent(self.dispatcher, x=x, y=y,
                                               owner=cop_entity)
        collision_component = WalkerCollisionComponent(self.dispatcher)
        cop_entity.add_component(position_component)
        cop_entity.add_component(widget_component)
        cop_entity.add_component(collision_component)
        return cop_entity
    
    def create_invisible_collider(self, x, y, size):
        """
        Create an impassable background object
        :param x: xpos
        :param y: ypos
        :param size: size tuple
        :return:
        """
        bg_entity = Entity(id='Collider')
        chars = [[' ' for _ in range(size[0])] for _ in range(size[1])]
        colors = copy_shape(chars, 'gray')
        widget = Widget(chars, colors)
        bg_entity.add_component(WidgetComponent(self.dispatcher, widget,
                                                owner=bg_entity))
        position_component = PositionComponent(self.dispatcher, x=x, y=y,
                                               owner=bg_entity)
        bg_entity.add_component(position_component)
        return bg_entity
