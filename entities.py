from bear_hug.bear_utilities import copy_shape, BearECSException
from bear_hug.ecs import Entity, WidgetComponent, PositionComponent, \
    DestructorComponent
from bear_hug.event import BearEvent
from bear_hug.widgets import SimpleAnimationWidget, Animation, Widget, \
    SwitchingWidget

from components import WalkerComponent, WalkerCollisionComponent, \
    SwitchWidgetComponent, SpawnerComponent, VisualDamageHealthComponent, \
    DestructorHealthComponent, FactionComponent, \
    ProjectileCollisionComponent, InputComponent, PassingComponent, \
    DecayComponent, MeleeControllerComponent


class MapObjectFactory:
    """
    A factory that produces all objects.
    Only `factory.create_entity()` method is available to the user,
    the rest are internal.
    """
    def __init__(self, atlas, dispatcher, layout):
        self.dispatcher = dispatcher
        self.atlas = atlas
        self.layout = layout
        self.counts = {}
        self.object_methods = {'cop': self.__create_cop,
                               'barrel': self.__create_barrel,
                               'invis': self.__create_invisible_collider,
                               'bullet': self.__create_bullet,
                               'target': self.__create_target,
                               'muzzle_flash': self._create_muzzle_flash,
                               'punch': self.__create_punch,
                               'nunchaku_punk': self.__create_nunchaku_punk}

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
            if entity_type in self.counts:
                self.counts[entity_type] += 1
            else:
                self.counts[entity_type] = 1
            entity = self.object_methods[entity_type](
                        entity_id=f'{entity_type}_{self.counts[entity_type]}',
                        **kwargs)
        except KeyError:
            raise BearECSException(f'Incorrect entity type {entity_type}')
        #Setting position of a child
        entity.position.move(*pos, emit_event=False)
        self.dispatcher.add_event(BearEvent('ecs_create', entity))
        if emit_show:
            self.dispatcher.add_event(BearEvent('ecs_add', (entity.id, *pos)))

    def __create_barrel(self, entity_id):
        barrel_entity = Entity(id=entity_id)
        widget = SimpleAnimationWidget(Animation((self.atlas.get_element(
                                                      'barrel_1'),
                                                  self.atlas.get_element(
                                                      'barrel_2')),
                                                  3),
                                       emit_ecs=True)
        widget_component = WidgetComponent(self.dispatcher, widget,
                                           owner=barrel_entity)
        position_component = PositionComponent(self.dispatcher,
                                               owner=barrel_entity)
        passability = PassingComponent(self.dispatcher, shadow_pos=(0, 7),
                                       shadow_size=(6, 2))
        barrel_entity.add_component(position_component)
        barrel_entity.add_component(widget_component)
        barrel_entity.add_component(passability)
        return barrel_entity
    
    def __create_cop(self, entity_id):
        # TODO: cop attack animations
        # TODO: separate widgets/entities for equipped items
        # This one obviously requires having an equipment system in place
        cop_entity = Entity(id=entity_id)
        widget = SwitchingWidget({'r_1': self.atlas.get_element('cop_r_1'),
                                  'r_2': self.atlas.get_element('cop_r_2'),
                                  'l_1': self.atlas.get_element('cop_l_1'),
                                  'l_2': self.atlas.get_element('cop_l_2')},
                                 initial_image='r_1')
        widget_component = SwitchWidgetComponent(self.dispatcher, widget,
                                                 owner=cop_entity)
        position_component = WalkerComponent(self.dispatcher,
                                               owner=cop_entity)
        collision_component = WalkerCollisionComponent(self.dispatcher)
        passability = PassingComponent(self.dispatcher, shadow_pos=(0, 15),
                                       shadow_size=(13, 3))
        cop_entity.add_component(position_component)
        cop_entity.add_component(widget_component)
        cop_entity.add_component(collision_component)
        cop_entity.add_component(passability)
        cop_entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        cop_entity.add_component(InputComponent(self.dispatcher))
        cop_entity.add_component(FactionComponent(self.dispatcher,
                                                  faction='police'))
        self.dispatcher.add_event(BearEvent(event_type='brut_focus',
                                            event_value=entity_id))
        return cop_entity
    
    def __create_nunchaku_punk(self, entity_id):
        nunchaku = Entity(id=entity_id)
        widget = SwitchingWidget({'r_1': self.atlas.get_element('nunchaku_punk_r_1'),
                                  'r_2': self.atlas.get_element('nunchaku_punk_r_2'),
                                  'l_1': self.atlas.get_element('nunchaku_punk_l_1'),
                                  'l_2': self.atlas.get_element('nunchaku_punk_l_2'),
                                  },
                                 initial_image='l_1')
        nunchaku.add_component(SwitchWidgetComponent(self.dispatcher, widget))
        nunchaku.add_component(WalkerComponent(self.dispatcher))
        nunchaku.add_component(WalkerCollisionComponent(self.dispatcher))
        nunchaku.add_component(PassingComponent(self.dispatcher,
                                                shadow_pos=(0, 15),
                                                shadow_size=(13, 3)))
        nunchaku.add_component(SpawnerComponent(self.dispatcher, factory=self))
        nunchaku.add_component(DestructorComponent(self.dispatcher))
        nunchaku.add_component(DestructorHealthComponent(self.dispatcher,
                                                         hitpoints=5))
        nunchaku.add_component(MeleeControllerComponent(self.dispatcher))
        nunchaku.add_component(FactionComponent(self.dispatcher,
                                                  faction='punks'))
        return nunchaku
    
    def __create_invisible_collider(self, entity_id, size=(0, 0)):
        """
        Create an impassable background object
        :param x: xpos
        :param y: ypos
        :param size: size tuple
        :return:
        """
        bg_entity = Entity(id=entity_id)
        chars = [[' ' for _ in range(size[0])] for _ in range(size[1])]
        colors = copy_shape(chars, 'gray')
        widget = Widget(chars, colors)
        bg_entity.add_component(WidgetComponent(self.dispatcher, widget,
                                                owner=bg_entity))
        position_component = PositionComponent(self.dispatcher,
                                               owner=bg_entity)
        bg_entity.add_component(position_component)
        bg_entity.add_component(PassingComponent(self.dispatcher))
        return bg_entity

    def __create_bullet(self, entity_id, speed=(0, 0), direction='r'):
        """
        Create a simple projectile
        :param speed:
        :return:
        """
        bullet_entity = Entity(id=entity_id)
        bullet_entity.add_component(WidgetComponent(self.dispatcher,
            SimpleAnimationWidget(Animation((self.atlas.get_element(f'bullet_{direction}_1'),
                                             self.atlas.get_element(f'bullet_{direction}_2'),
                                             self.atlas.get_element(f'bullet_{direction}_3'),
                                             ), 10))))
        bullet_entity.add_component(PositionComponent(self.dispatcher,
                                                      vx=speed[0], vy=speed[1]))
        bullet_entity.add_component(ProjectileCollisionComponent(self.dispatcher,
                                                                 damage=1))
        bullet_entity.add_component(DestructorComponent(self.dispatcher))
        return bullet_entity
    
    def __create_punch(self, entity_id, speed=(0,0), direction='r'):
        """
        Send a punch
        :param entity_id:
        :param speed:
        :param direction:
        :return:
        """
        punch = Entity(id=entity_id)
        punch.add_component(WidgetComponent(self.dispatcher,
                                Widget(*self.atlas.get_element(
                                    f'punch_{direction}'))))
        punch.add_component(PositionComponent(self.dispatcher,
                                                      vx=speed[0], vy=speed[1]))
        punch.add_component(ProjectileCollisionComponent(self.dispatcher,
                                                         damage=3))
        punch.add_component(DestructorComponent(self.dispatcher))
        punch.add_component(DecayComponent(self.dispatcher,
                                           destroy_condition='timeout',
                                           lifetime=0.2))
        return punch

    def __create_target(self, entity_id):
        """
        A target
        :return:
        """
        target_entity = Entity(id=entity_id)
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
                            widgets_dict={1: 'destroyed',
                             2: 'severe',
                             3: 'slight',
                             4: 'intact'},
                            hitpoints=4))
        target_entity.add_component(PositionComponent(self.dispatcher))
        target_entity.add_component(DestructorComponent(self.dispatcher))
        return target_entity

    def _create_muzzle_flash(self, entity_id, direction='r'):
        entity = Entity(entity_id)
        if direction == 'r':
            chars, colors = self.atlas.get_element('shot_r')
        else:
            chars, colors = self.atlas.get_element('shot_l')
        entity.add_component(WidgetComponent(self.dispatcher,
                                             Widget(chars, colors)))
        entity.add_component(DecayComponent(self.dispatcher,
                                            destroy_condition='timeout',
                                            lifetime=0.1))
        entity.add_component(PositionComponent(self.dispatcher))
        entity.add_component(DestructorComponent(self.dispatcher))
        return entity

