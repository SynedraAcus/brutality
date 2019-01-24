from bear_hug.bear_utilities import copy_shape, BearECSException
from bear_hug.ecs import Entity, WidgetComponent, PositionComponent
from bear_hug.event import BearEvent
from bear_hug.widgets import SimpleAnimationWidget, Animation, Widget

from components import WalkerComponent, WalkerCollisionComponent, \
    SwitchWidgetComponent, SpawnerComponent, VisualDamageHealthComponent, \
    ProjectileCollisionComponent
from widgets import SwitchingWidget


class MapObjectFactory:
    #TODO: make this a nice universally-available singleton

    def __init__(self, atlas, dispatcher):
        self.dispatcher = dispatcher
        self.atlas = atlas
        self.counts = {}
        self.object_methods = {'cop': self.create_cop,
                               'barrel': self.create_barrel,
                               'invis': self.create_invisible_collider,
                               'bullet': self.create_bullet,
                               'target': self.create_target}

    def create_entity(self, entity_type, pos, emit_show=True, **kwargs):
        """
        Create entity and emit the corresponding events.
        Kwargs, if any, are passed to the creating function.
        :param entity_type: str. Entity type code
        :param pos: Two-int position tuple
        :param emit_show: bool. If True, emits ecs_add event
        :return:
        """
        try:
            entity = self.object_methods[entity_type](**kwargs)
        except KeyError as e:
            raise BearECSException(f'Incorrect entity type {entity_type}')
        #Setting position of a child
        entity.position.move(*pos, emit_event=False)
        self.dispatcher.add_event(BearEvent('ecs_create', entity))
        if emit_show:
            self.dispatcher.add_event(BearEvent('ecs_add', (entity.id, *pos)))

    def create_barrel(self):
        if 'Barrel' in self.counts:
            self.counts['Barrel'] += 1
        else:
            self.counts['Barrel'] = 1
        barrel_entity = Entity(id=f'Barrel{self.counts["Barrel"]}')
        widget = SimpleAnimationWidget(Animation((self.atlas.get_element(
                                                      'barrel_1'),
                                                  self.atlas.get_element(
                                                      'barrel_2')),
                                                  3),
                                       emit_ecs=True)
        widget_component = WidgetComponent(self.dispatcher, widget,
                                           owner=barrel_entity)
        position_component = PositionComponent(self.dispatcher, #x=x, y=y,
                                               owner=barrel_entity)
        barrel_entity.add_component(position_component)
        barrel_entity.add_component(widget_component)
        return barrel_entity
    
    def create_cop(self):
        if 'Cop' in self.counts:
            self.counts['Cop'] += 1
        else:
            self.counts['Cop'] = 1
        cop_entity = Entity(id=f'Cop{self.counts["Cop"]}')
        widget = SwitchingWidget({'r_1': self.atlas.get_element('cop_r_1'),
                                  'r_2': self.atlas.get_element('cop_r_2'),
                                  'l_1': self.atlas.get_element('cop_l_1'),
                                  'l_2': self.atlas.get_element('cop_l_2')},
                                 initial_image='r_1')
        widget_component = SwitchWidgetComponent(self.dispatcher, widget,
                                                 owner=cop_entity)
        position_component = WalkerComponent(self.dispatcher, #x=x, y=y,
                                               owner=cop_entity)
        collision_component = WalkerCollisionComponent(self.dispatcher)
        cop_entity.add_component(position_component)
        cop_entity.add_component(widget_component)
        cop_entity.add_component(collision_component)
        cop_entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        return cop_entity
    
    def create_invisible_collider(self, size=(0,0)):
        """
        Create an impassable background object
        :param x: xpos
        :param y: ypos
        :param size: size tuple
        :return:
        """
        if 'collider' in self.counts:
            self.counts['collider'] += 1
        else:
            self.counts['collider'] = 1
        bg_entity = Entity(id=f'collider{self.counts["collider"]}')
        chars = [['#' for _ in range(size[0])] for _ in range(size[1])]
        colors = copy_shape(chars, 'gray')
        widget = Widget(chars, colors)
        bg_entity.add_component(WidgetComponent(self.dispatcher, widget,
                                                owner=bg_entity))
        position_component = PositionComponent(self.dispatcher, #x=x, y=y,
                                               owner=bg_entity)
        bg_entity.add_component(position_component)
        return bg_entity

    def create_bullet(self, speed=(0, 0)):
        """
        Create a simple projectile
        :param speed:
        :return:
        """
        if 'bullet' in self.counts:
            self.counts['bullet'] += 1
        else:
            self.counts['bullet'] = 1
        bullet_entity = Entity(id=f'Bullet{self.counts["bullet"]}')
        #TODO: Debug bullet animation
        bullet_entity.add_component(WidgetComponent(self.dispatcher,
            SimpleAnimationWidget(Animation((self.atlas.get_element('bullet_1'),
                                             self.atlas.get_element('bullet_2'),
                                             self.atlas.get_element('bullet_3'),
                                             ), 5))))
        bullet_entity.add_component(PositionComponent(self.dispatcher,
                                                      vx=speed[0], vy=speed[1]))
        bullet_entity.add_component(ProjectileCollisionComponent(self.dispatcher))
        return bullet_entity

    def create_target(self):
        """
        A target
        :return:
        """
        #TODO: move counts to create_entity
        if 'target' in self.counts:
            self.counts['target'] += 1
        else:
            self.counts['target'] = 1
        target_entity = Entity(id=f'Target{self.counts["target"]}')
        widget = SwitchingWidget(images_dict={
                        'intact': self.atlas.get_element('target_intact'),
                        'slight': self.atlas.get_element('target_1'),
                        'severe': self.atlas.get_element('target_2'),
                        'destroyed': self.atlas.get_element('target_destroyed')},
                                initial_image='intact')
        target_entity.add_component(SwitchWidgetComponent(self.dispatcher,
                                                          widget))
        target_entity.add_component(VisualDamageHealthComponent(
                            self.dispatcher,
                            widgets_dict={0: 'destroyed',
                             1: 'severe',
                             2: 'slight',
                             3: 'intact'},
                            hitpoints=3))
        target_entity.add_component(PositionComponent(self.dispatcher))
        return target_entity
