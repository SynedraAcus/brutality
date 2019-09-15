from bear_hug.bear_utilities import copy_shape, BearECSException
from bear_hug.ecs import Entity, WidgetComponent, PositionComponent, \
    DestructorComponent, deserialize_entity
from bear_hug.event import BearEvent
from bear_hug.widgets import SimpleAnimationWidget, Animation, Widget, \
    SwitchingWidget

from components import WalkerComponent, WalkerCollisionComponent, \
    SwitchWidgetComponent, SpawnerComponent, VisualDamageHealthComponent, \
    DestructorHealthComponent, FactionComponent, CollisionComponent, \
    ProjectileCollisionComponent, InputComponent, PassingComponent, \
    DecayComponent, MeleeControllerComponent, HidingComponent,\
    HandInterfaceComponent, SpawningItemBehaviourComponent,\
    GravityPositionComponent
from widgets import PatternGenerator


class MapObjectFactory:
    """
    A factory that produces all objects.
    Only `factory.create_entity()` and `load_entity_from_JSON()` are exposed;
    other methods are internal.

    This class (or its subclass) is expected to have a method for each kind of
    entity it creates. This method should have the name `factory._create_{item}`
    and will be called with item ID as a first argument. Kwargs from the
    `create_entity` call, if any, will be passed to the creator method. Since
    creator methods typically rely on `self.dispatcher` and other factory
    attributes, they shouldn't be static or classmethods.
    """
    def __init__(self, atlas, dispatcher, layout):
        self.dispatcher = dispatcher
        self.atlas = atlas
        self.layout = layout
        self.patterns = PatternGenerator(self.atlas)
        self.counts = {}

    def load_entity_from_JSON(self, json_string, emit_show=True):
        """
        Create the entity described by a JSON string
        This method does not check or correct anything, instead assuming that
        the JSON file contains all necessary data. Emits 'ecs_create', 'ecs_add'
        and, if `emit_show` is set to True, 'ecs_show'
        :param json_string:
        :param emit_show:
        :return:
        """
        entity = deserialize_entity(json_string, self.dispatcher)
        self.dispatcher.add_event(BearEvent('ecs_create', entity))
        # TODO: make factory respond to events
        # Following hack is necessary because the SpawnerComponent adresses the
        # factory directly. If the factory could respond to events, the
        # component wouldn't need to know anything about it and will become a
        # simple event emitter
        if hasattr(entity, 'spawner'):
            entity.spawner.factory = self
        if emit_show:
            self.dispatcher.add_event(BearEvent('ecs_add', (entity.id,
                                                            entity.position.x,
                                                            entity.position.y)))

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
            entity = getattr(self, f'_create_{entity_type}')(
                entity_id=f'{entity_type}_{self.counts[entity_type]}',
                **kwargs)
        except AttributeError:
            raise BearECSException(f'Incorrect entity type {entity_type}')
        #Setting position of a child
        entity.position.move(*pos, emit_event=False)
        self.dispatcher.add_event(BearEvent('ecs_create', entity))
        if emit_show:
            self.dispatcher.add_event(BearEvent('ecs_add', (entity.id, *pos)))

    def _create_wall(self, entity_id, size=(50, 30)):
        wall = Entity(id=entity_id)
        widget = Widget(*self.patterns.generate_tiled('brick_tile', size))
        wall.add_component(WidgetComponent(self.dispatcher, widget))
        wall.add_component(PositionComponent(self.dispatcher))
        wall.add_component(PassingComponent(self.dispatcher))
        return wall

    def _create_floor(self, entity_id, size=(150, 30)):
        floor = Entity(id=entity_id)
        widget = Widget(*self.patterns.tile_randomly('floor_tile_1',
                                                     'floor_tile_2',
                                                     'floor_tile_3',
                                                      size=size))
        floor.add_component(PositionComponent(self.dispatcher))
        floor.add_component(WidgetComponent(self.dispatcher, widget))
        return floor

    def _create_barrel(self, entity_id):
        barrel_entity = Entity(id=entity_id)
        widget = SimpleAnimationWidget(Animation((self.atlas.get_element(
                                                      'barrel_1'),
                                                  self.atlas.get_element(
                                                      'barrel_2')),
                                                  3),
                                       emit_ecs=True)
        barrel_entity.add_component(PositionComponent(self.dispatcher))
        barrel_entity.add_component(WidgetComponent(self.dispatcher, widget))
        barrel_entity.add_component(PassingComponent(self.dispatcher,
                                                     shadow_pos=(0, 7),
                                                     shadow_size=(6, 2)))
        barrel_entity.add_component(CollisionComponent(self.dispatcher))
        return barrel_entity
    
    def _create_cop(self, entity_id):
        cop_entity = Entity(id=entity_id)
        widget = SwitchingWidget(images_dict={'r_1': self.atlas.get_element('cop_r_1'),
                                              'r_2': self.atlas.get_element('cop_r_2'),
                                              'l_1': self.atlas.get_element('cop_l_1'),
                                              'l_2': self.atlas.get_element('cop_l_2')},
                                 initial_image='r_1')
        cop_entity.add_component(WalkerComponent(self.dispatcher))
        cop_entity.add_component(SwitchWidgetComponent(self.dispatcher, widget))
        cop_entity.add_component(WalkerCollisionComponent(self.dispatcher))
        cop_entity.add_component(PassingComponent(self.dispatcher, shadow_pos=(0, 15),
                                                  shadow_size=(13, 3)))
        cop_entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        cop_entity.add_component(InputComponent(self.dispatcher))
        cop_entity.add_component(FactionComponent(self.dispatcher,
                                                  faction='police'))
        # Creating hand entities
        f_l = self._create_cop_hand_forward(f'{entity_id}_hand_fl',
                                            direction='l')
        f_r = self._create_cop_hand_forward(f'{entity_id}_hand_fr',
                                            direction='r')
        b_l = self._create_cop_hand_back(f'{entity_id}_hand_bl',
                                         direction='l')
        b_r = self._create_cop_hand_back(f'{entity_id}_hand_br',
                                         direction='r')
        self.dispatcher.add_event(BearEvent('ecs_create', f_l))
        self.dispatcher.add_event(BearEvent('ecs_create', f_r))
        self.dispatcher.add_event(BearEvent('ecs_create', b_l))
        self.dispatcher.add_event(BearEvent('ecs_create', b_r))
        pistol = self._create_pistol(f'{entity_id}_left_pistol',
                                     owning_entity=cop_entity)
        self.dispatcher.add_event(BearEvent('ecs_create', pistol))
        fist = self._create_fist(f'{entity_id}_fist',
                                 owning_entity=cop_entity)
        self.dispatcher.add_event(BearEvent('ecs_create', fist))
        cop_entity.add_component(HandInterfaceComponent(self.dispatcher,
                                                        hand_entities={
                                                            'forward_l': f_l.id,
                                                            'forward_r': f_r.id,
                                                            'back_l': b_l.id,
                                                            'back_r': b_r.id},
                                                        hands_offsets={
                                                            'forward_l': (-3, 5),
                                                            'forward_r': (0, 5),
                                                            'back_l': (-3, 4),
                                                            'back_r': (3, 4)},
                                                        item_offsets={
                                                            'forward_l': (0, 0),
                                                            'forward_r': (7, 0),
                                                            'back_l': (0, 0),
                                                            'back_r': (4, 0)},
                                                        left_item=fist.id,
                                                        right_item=pistol.id))
        self.dispatcher.add_event(BearEvent(event_type='brut_focus',
                                            event_value=entity_id))
        return cop_entity
    
    def _create_nunchaku_punk(self, entity_id):
        nunchaku = Entity(id=entity_id)
        widget = SwitchingWidget(images_dict={'r_1': self.atlas.get_element('nunchaku_punk_r_1'),
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
                                                shadow_size=(8, 3)))
        nunchaku.add_component(SpawnerComponent(self.dispatcher, factory=self))
        nunchaku.add_component(DestructorComponent(self.dispatcher))
        nunchaku.add_component(DestructorHealthComponent(self.dispatcher,
                                                         hitpoints=5))
        nunchaku.add_component(MeleeControllerComponent(self.dispatcher))
        nunchaku.add_component(FactionComponent(self.dispatcher,
                                                  faction='punks'))
        weapon = self._create_nunchaku('nunchaku1', owning_entity=nunchaku)
        self.dispatcher.add_event(BearEvent('ecs_create', weapon))
        # Creating hand entities
        f_l = self._create_nunchaku_punk_hand_forward(f'{entity_id}_hand_fl',
                                            direction='l')
        f_r = self._create_nunchaku_punk_hand_forward(f'{entity_id}_hand_fr',
                                            direction='r')
        b_l = self._create_nunchaku_punk_hand_back(f'{entity_id}_hand_bl',
                                         direction='l')
        b_r = self._create_nunchaku_punk_hand_back(f'{entity_id}_hand_br',
                                         direction='r')
        self.dispatcher.add_event(BearEvent('ecs_create', f_l))
        self.dispatcher.add_event(BearEvent('ecs_create', f_r))
        self.dispatcher.add_event(BearEvent('ecs_create', b_l))
        self.dispatcher.add_event(BearEvent('ecs_create', b_r))
        nunchaku.add_component(HandInterfaceComponent(self.dispatcher,
                                                        hand_entities={
                                                            'forward_l': f_l.id,
                                                            'forward_r': f_r.id,
                                                            'back_l': b_l.id,
                                                            'back_r': b_r.id},
                                                        hands_offsets={
                                                            'forward_l': (-1, 5),
                                                            'forward_r': (0, 4),
                                                            'back_l': (-1, 5),
                                                            'back_r': (0, 4)},
                                                        item_offsets={
                                                            'forward_l': (0, 0),
                                                            'forward_r': (8, 0),
                                                            'back_l': (0, -2),
                                                            'back_r': (4, 0)},
                                                        right_item=weapon.id))
        return nunchaku

    def _create_bottle_punk(self, entity_id):
        punk = Entity(id=entity_id)
        widget = SwitchingWidget(
            images_dict={'r_1': self.atlas.get_element('bottle_punk_r_1'),
                         'r_2': self.atlas.get_element('bottle_punk_r_2'),
                         'l_1': self.atlas.get_element('bottle_punk_l_1'),
                         'l_2': self.atlas.get_element('bottle_punk_l_2'),
                         },
            initial_image='l_1')
        punk.add_component(SwitchWidgetComponent(self.dispatcher, widget))
        punk.add_component(WalkerComponent(self.dispatcher))
        punk.add_component(WalkerCollisionComponent(self.dispatcher))
        punk.add_component(PassingComponent(self.dispatcher,
                                            shadow_pos=(0, 15),
                                            shadow_size=(6, 3)))
        punk.add_component(SpawnerComponent(self.dispatcher, factory=self))
        punk.add_component(DestructorComponent(self.dispatcher))
        punk.add_component(DestructorHealthComponent(self.dispatcher,
                                                         hitpoints=5))
        punk.add_component(InputComponent(self.dispatcher))
        punk.add_component(FactionComponent(self.dispatcher,
                                                faction='punks'))
        # Sttart from here
        f_l = self._create_bottle_punk_hand_forward(f'{entity_id}_hand_fl',
                                                      direction='l')
        f_r = self._create_bottle_punk_hand_forward(f'{entity_id}_hand_fr',
                                                      direction='r')
        b_l = self._create_bottle_punk_hand_back(f'{entity_id}_hand_bl',
                                                   direction='l')
        b_r = self._create_bottle_punk_hand_back(f'{entity_id}_hand_br',
                                                   direction='r')
        self.dispatcher.add_event(BearEvent('ecs_create', f_l))
        self.dispatcher.add_event(BearEvent('ecs_create', f_r))
        self.dispatcher.add_event(BearEvent('ecs_create', b_l))
        self.dispatcher.add_event(BearEvent('ecs_create', b_r))
        fist = self._create_fist(f'{entity_id}_fist',
                                 owning_entity=punk)
        self.dispatcher.add_event(BearEvent('ecs_create', fist))
        launcher = self._create_bottle_launcher(f'{entity_id}_bottle_launcher',
                                                owning_entity=punk)
        self.dispatcher.add_event(BearEvent('ecs_create', launcher))
        punk.add_component(HandInterfaceComponent(self.dispatcher,
                                                      hand_entities={
                                                          'forward_l': f_l.id,
                                                          'forward_r': f_r.id,
                                                          'back_l': b_l.id,
                                                          'back_r': b_r.id},
                                                      hands_offsets={
                                                          'forward_l': (1, 6),
                                                          'forward_r': (2, 4),
                                                          'back_l': (1, 5),
                                                          'back_r': (2, 5)},
                                                      item_offsets={
                                                          'forward_l': (0, 0),
                                                          'forward_r': (5, 1),
                                                          'back_l': (0, 0),
                                                          'back_r': (6, 0)},
                                                      left_item=fist.id,
                                                      right_item=launcher.id))
        return punk
    
    def _create_invis(self, entity_id, size=(0, 0)):
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
        bg_entity.add_component(PositionComponent(self.dispatcher))
        bg_entity.add_component(PassingComponent(self.dispatcher))
        return bg_entity

    def _create_bullet(self, entity_id, speed=(0, 0), direction='r'):
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
    
    def _create_punch(self, entity_id, speed=(0, 0), direction='r'):
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

    def _create_bottle(self, entity_id, speed=(0, 0), direction='r'):
        """
        A rotating flying bottle
        :param entity_id:
        :return:
        """
        entity = Entity(id=entity_id)
        if direction == 'r':
            widget = SimpleAnimationWidget(Animation((self.atlas.get_element('bottle_ne'),
                                                      self.atlas.get_element('bottle_se'),
                                                      self.atlas.get_element('bottle_sw'),
                                                      self.atlas.get_element('bottle_nw')),
                                                      8),
                                           emit_ecs=True)
        else:
            widget = SimpleAnimationWidget(Animation((self.atlas.get_element('bottle_nw'),
                                                      self.atlas.get_element('bottle_sw'),
                                                      self.atlas.get_element('bottle_se'),
                                                      self.atlas.get_element('bottle_ne')),
                                                      8),
                                           emit_ecs=True)
        entity.add_component(WidgetComponent(self.dispatcher, widget))
        entity.add_component(GravityPositionComponent(self.dispatcher,
                                               acceleration=30,
                                               vx=speed[0], vy=speed[1]))
        entity.add_component(ProjectileCollisionComponent(self.dispatcher, damage=1))
        entity.add_component(DestructorComponent(self.dispatcher))
        return entity

    def _create_target(self, entity_id):
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
        target_entity.add_component(CollisionComponent(self.dispatcher))
        return target_entity

    # TODO: some common method for spawning single-use attack animations.
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

    # TODO: merge boilerplate hand generators into a single `_create_hand(hand_type)`
    def _create_cop_hand_back(self, entity_id, direction='r'):
        entity = Entity(entity_id)
        chars, colors = self.atlas.get_element(f'cop_hand_back_{direction}')
        entity.add_component(WidgetComponent(self.dispatcher,
                                             Widget(chars, colors)))
        entity.add_component(PositionComponent(self.dispatcher))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False))
        return entity

    def _create_cop_hand_forward(self, entity_id, direction='r'):
        entity = Entity(entity_id)
        chars, colors = self.atlas.get_element(f'cop_hand_forward_{direction}')
        entity.add_component(WidgetComponent(self.dispatcher,
                                             Widget(chars, colors)))
        entity.add_component(PositionComponent(self.dispatcher))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False))
        return entity

    def _create_punk_hand_back(self, entity_id, direction='r'):
        entity = Entity(entity_id)
        chars, colors = self.atlas.get_element(f'punk_hand_back_{direction}')
        entity.add_component(WidgetComponent(self.dispatcher,
                                             Widget(chars, colors)))
        entity.add_component(PositionComponent(self.dispatcher))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False))
        return entity

    def _create_nunchaku_punk_hand_forward(self, entity_id, direction='r'):
        entity = Entity(entity_id)
        chars, colors = self.atlas.get_element(f'nunchaku_punk_hand_forward_{direction}')
        entity.add_component(WidgetComponent(self.dispatcher,
                                             Widget(chars, colors)))
        entity.add_component(PositionComponent(self.dispatcher))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False))
        return entity

    def _create_nunchaku_punk_hand_back(self, entity_id, direction='r'):
        entity = Entity(entity_id)
        chars, colors = self.atlas.get_element(f'nunchaku_punk_hand_back_{direction}')
        entity.add_component(WidgetComponent(self.dispatcher,
                                             Widget(chars, colors)))
        entity.add_component(PositionComponent(self.dispatcher))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False))
        return entity

    def _create_bottle_punk_hand_forward(self, entity_id, direction='r'):
        entity = Entity(entity_id)
        chars, colors = self.atlas.get_element(
            f'bottle_punk_hand_forward_{direction}')
        entity.add_component(WidgetComponent(self.dispatcher,
                                             Widget(chars, colors)))
        entity.add_component(PositionComponent(self.dispatcher))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False))
        return entity

    def _create_bottle_punk_hand_back(self, entity_id, direction='r'):
        entity = Entity(entity_id)
        chars, colors = self.atlas.get_element(
            f'bottle_punk_hand_back_{direction}')
        entity.add_component(WidgetComponent(self.dispatcher,
                                             Widget(chars, colors)))
        entity.add_component(PositionComponent(self.dispatcher))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False))
        return entity

    def _create_pistol(self, entity_id, owning_entity=None):
        entity = Entity(entity_id)
        widget = SwitchingWidget(images_dict={'l': self.atlas.get_element('pistol_l'),
                                              'r': self.atlas.get_element('pistol_r')},
                                 initial_image='r')
        entity.add_component(SwitchWidgetComponent(self.dispatcher,
                                                   widget))
        entity.add_component(SpawningItemBehaviourComponent(self.dispatcher,
                                                            owning_entity=owning_entity,
                                                            spawned_item='bullet',
                                                            relative_pos={'r': (0, 0),
                                                                          'l': (-2, 0)}))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False))
        entity.add_component(PositionComponent(self.dispatcher))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        return entity

    def _create_fist(self, entity_id, owning_entity=None):
        entity = Entity(entity_id)
        widget = SwitchingWidget(
            images_dict={'l': self.atlas.get_element('fist_l'),
                         'r': self.atlas.get_element('fist_r')},
            initial_image='r')
        entity.add_component(SwitchWidgetComponent(self.dispatcher,
                                                   widget))
        entity.add_component(SpawningItemBehaviourComponent(self.dispatcher,
                                                            owning_entity=owning_entity,
                                                            spawned_item='punch',
                                                            relative_pos={
                                                                'r': (0, -2),
                                                                'l': (-1, -2)}))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False))
        entity.add_component(PositionComponent(self.dispatcher))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        return entity

    def _create_nunchaku(self, entity_id, owning_entity=None):
        entity = Entity(entity_id)
        widget = SwitchingWidget(
            images_dict={'l': self.atlas.get_element('nunchaku_l'),
                         'r': self.atlas.get_element('nunchaku_r')},
            initial_image='r')
        entity.add_component(SwitchWidgetComponent(self.dispatcher,
                                                   widget))
        entity.add_component(SpawningItemBehaviourComponent(self.dispatcher,
                                                            owning_entity=owning_entity,
                                                            spawned_item='punch',
                                                            relative_pos={
                                                                'r': (8, -1),
                                                                'l': (-1, -2)}))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False))
        entity.add_component(PositionComponent(self.dispatcher))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        return entity

    def _create_bottle_launcher(self, entity_id, owning_entity=None):
        entity = Entity(entity_id)
        widget = SwitchingWidget(
            images_dict={'l': self.atlas.get_element('fist_l'),
                         'r': self.atlas.get_element('fist_r')},
            initial_image='r')
        entity.add_component(SwitchWidgetComponent(self.dispatcher,
                                                   widget))
        entity.add_component(SpawningItemBehaviourComponent(self.dispatcher,
                                                            owning_entity=owning_entity,
                                                            spawned_item='bottle',
                                                            relative_pos={
                                                                'r': (2, -2),
                                                                'l': (-3, -2)}))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False))
        entity.add_component(PositionComponent(self.dispatcher))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        return entity