from random import randint

from bear_hug.bear_utilities import copy_shape, BearECSException,\
    BearResourceException
from bear_hug.ecs import Entity, WidgetComponent, PositionComponent, \
    DestructorComponent, deserialize_entity, CollisionComponent,\
    WalkerCollisionComponent, DecayComponent
from bear_hug.event import BearEvent
from bear_hug.widgets import SimpleAnimationWidget, Animation, Widget, \
    SwitchingWidget, Label
from bear_hug.resources import Atlas, XpLoader

from components import *
from background import generate_tiled, tile_randomly, generate_bg,\
    ghetto_transition, dept_transition


class EntityFactory:
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
        self.counts = {}
        self.decorations = {'can', 'can2', 'cigarettes', 'garbage_bag',
                            'bucket', 'pizza_box',
                            'cop_corpse', 'bottle_punk_corpse', 'nunchaku_punk_corpse',
                            'scientist_f_corpse', 'scientist_f2_corpse',
                            'scientist_m_corpse', 'scientist_m2_corpse'}
        self.barriers = {'broken_car', 'barricade_1', 'barricade_2',
                         'barricade_3', 'dept_locker', 'dept_fence',
                         'dept_bench', 'dept_wall_inner',
                         'dept_table_1', 'dept_table_2', 'dept_chair_1',
                         'dept_chair_2', 'dept_table_boss',
                         'science_table_1', 'science_table_2',
                         'science_device_1', 'science_device_2',
                         'science_spike'}
        self.face_positions = {'broken_car': (0, 3),
                               'barricade_1': (0, 2),
                               'barricade_2': (0, 3),
                               'barricade_3': (0, 5),
                               'dept_locker': (0, 3),
                               'dept_fence': (0, 0),
                               'dept_bench': (0, 2),
                               'dept_wall_inner': (0, 11),
                               'dept_table_1': (0, 10),
                               'dept_table_2': (0, 11),
                               'dept_chair_1': (0, 2),
                               'dept_chair_2': (0, 2),
                               'dept_table_boss': (0, 14),
                               'science_table_1': (0, 9),
                               'science_table_2': (0, 6),
                               'science_device_1': (0, 3),
                               'science_device_2': (0, 2),
                               'science_spike': (0, 0)}
        self.face_sizes = {'broken_car': (33, 11),
                           'barricade_1': (7, 14),
                           'barricade_2': (9, 11),
                           'barricade_3': (11, 8),
                           'dept_locker': (6, 17),
                           'dept_fence': (21, 14),
                           'dept_bench': (17, 5),
                           'dept_wall_inner': (3, 21),
                           'dept_table_1': (10, 8),
                           'dept_table_2': (11, 8),
                           'dept_chair_1': (5, 10),
                           'dept_chair_2': (5, 10),
                           'dept_table_boss': (24, 10),
                           'science_table_1': (11, 9),
                           'science_table_2': (29, 9),
                           'science_device_1': (6, 17),
                           'science_device_2': (8, 13),
                           'science_spike': (0, 0)}
        self.depths = {'broken_car': 4,
                       'barricade_1': 5,
                       'barricade_2': 5,
                       'barricade_3': 4,
                       'dept_locker': 3,
                       'dept_fence': 0,
                       'dept_bench': 2,
                       'dept_wall_inner': 11,
                       'dept_table_1': 7,
                       'dept_table_2': 7,
                       'dept_chair_1': 1,
                       'dept_chair_2': 1,
                       'dept_table_boss': 6,
                       'science_table_1': 7,
                       'science_table_2': 2,
                       'science_device_1': 3,
                       'science_device_2': 3,
                       'science_spike': 0}
        self.shadow_positions = {'broken_car': (0, 7),
                                 'barricade_1': (1, 9),
                                 'barricade_2': (0, 6),
                                 'barricade_3': (0, 6),
                                 'dept_locker': (0, 17),
                                 'dept_fence': (0, 13),
                                 'dept_bench': (0, 5),
                                 'dept_wall_inner': (0, 19),
                                 'dept_table_1': (0, 11),
                                 'dept_table_2': (0, 12),
                                 'dept_chair_1': (0, 10),
                                 'dept_chair_2': (0, 10),
                                 'dept_table_boss': (0, 19),
                                 'science_table_1': (0, 11),
                                 'science_table_2': (0, 13),
                                 'science_device_1': (1, 16),
                                 'science_device_2': (0, 12),
                                 'science_spike': (0, 19)}
        self.shadow_sizes = {'broken_car': (38, 7),
                             'barricade_1': (11, 7),
                             'barricade_2': (14, 8),
                             'barricade_3': (13, 8),
                             'dept_locker': (9, 3),
                             'dept_fence': (21, 2),
                             'dept_bench': (19, 2),
                             'dept_range_table': (13, 19),
                             'dept_wall_inner': (15, 12),
                             'dept_table_1': (17, 7),
                             'dept_table_2': (18, 7),
                             'dept_chair_1': (7, 3),
                             'dept_chair_2': (7, 3),
                             'dept_table_boss': (30, 7),
                             'science_table_1': (15, 8),
                             'science_table_2': (29, 2),
                             'science_device_1': (5, 4),
                             'science_device_2': (10, 3),
                             'science_spike': (3, 1)}

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
        # Following hack is necessary because the SpawnerComponent adresses the
        # factory directly. If the factory could respond to events, the
        # component wouldn't need to know anything about it and will become a
        # simple event emitter
        if hasattr(entity, 'spawner'):
            entity.spawner.factory = self
        if emit_show:
            if hasattr(entity, 'hiding') and entity.hiding.should_hide:
                # If the entity needs to be hidden, don't add it
                return
            self.dispatcher.add_event(BearEvent('ecs_add', (entity.id,
                                                        entity.position.x,
                                                        entity.position.y)))

    def create_entity(self, entity_type, pos, emit_show=True, **kwargs):
        """
        Create entity and emit the corresponding events.

        If entity is in ``self.decorations``, calls
        ``self.generate_inactive_decoration`` with the correct ID and type. In
        this case, kwargs are ignored, since this kind of entity is not supposed
        to have anything except widget and position.

        Otherwise calls ``self._create_{entity_type}`` and passes all kwargs to
        this method.

        In either case, this method takes care of providing correct entity ID
        and emitting ``ecs_create`` and, if requested, ``ecs_add``.

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
            if entity_type in self.decorations:
                entity = self.generate_inactive_decoration(f'{entity_type}_{self.counts[entity_type]}',
                                                           entity_type)
            elif entity_type in self.barriers:
                entity = self.generate_barrier(f'{entity_type}_{self.counts[entity_type]}',
                                               entity_type)
            else:
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
        return entity.id

    def _create_message(self, entity_id, text = 'Sample text\nsample text',
                        vx=0, vy=0, destroy_condition='keypress', lifetime=2.0,
                        **kwargs):
        message = Entity(id=entity_id)
        widget = Label(text, z_level=200)
        message.add_component(WidgetComponent(self.dispatcher, widget))
        message.add_component(PositionComponent(self.dispatcher, vx=vx, vy=vy,
                                                affect_z=False))
        message.add_component(DestructorComponent(self.dispatcher))
        message.add_component(DecayComponent(self.dispatcher, destroy_condition=destroy_condition,
                                             lifetime=lifetime))
        return message

    def _create_message_spawner(self, entity_id, xsize=10, ysize=10,
                                entity_filter = lambda x: True, **kwargs):
        spawner = Entity(id = entity_id)
        chars = [[' ' for x in range(xsize)] for y in range(ysize)]
        colors = copy_shape(chars, '000')
        widget = Widget(chars, colors)
        spawner.add_component(WidgetComponent(self.dispatcher, widget))
        spawner.add_component(PositionComponent(self.dispatcher))
        spawner.add_component(DestructorComponent(self.dispatcher))
        spawner.add_component(SpawnerComponent(self.dispatcher, factory=self))
        spawner.add_component(SpawnerCollisionComponent(self.dispatcher,
                                                        entity_filter=entity_filter,
                                                        spawned_item='message',
                                                        spawn_kwargs=kwargs))
        return spawner

    def _create_ghetto_bg(self, entity_id, size=(50, 20), **kwargs):
        wall = Entity(id=entity_id)
        # widget = Widget(*generate_tiled(self.atlas, 'brick_tile', size))
        w = generate_bg(self.atlas, ghetto_transition, size[0])
        widget = Widget(*w)
        wall.add_component(WidgetComponent(self.dispatcher, widget))
        wall.add_component(PositionComponent(self.dispatcher,affect_z=True))
        wall.add_component(DestructorComponent(self.dispatcher))
        wall.add_component(CollisionComponent(self.dispatcher, depth=20))
        return wall

    def _create_dept_bg(self, entity_id, size=(50, 20), **kwargs):
        wall = Entity(id=entity_id)
        # widget = Widget(*generate_tiled(self.atlas, 'brick_tile', size))
        w = generate_bg(self.atlas, dept_transition, size[0])
        widget = Widget(*w)
        wall.add_component(WidgetComponent(self.dispatcher, widget))
        wall.add_component(PositionComponent(self.dispatcher, affect_z=True))
        wall.add_component(DestructorComponent(self.dispatcher))
        wall.add_component(CollisionComponent(self.dispatcher, depth=20))
        return wall

    def _create_floor(self, entity_id, size=(150, 30), **kwargs):
        floor = Entity(id=entity_id)
        widget = Widget(*tile_randomly(self.atlas, 'floor_tile_1',
                                                  'floor_tile_2',
                                                  'floor_tile_3',
                                                  size=size))
        # Disable affect_z so that floor won't overlap everything
        floor.add_component(PositionComponent(self.dispatcher, affect_z=False))
        floor.add_component(WidgetComponent(self.dispatcher, widget))
        floor.add_component(DestructorComponent(self.dispatcher))
        return floor

    def generate_inactive_decoration(self, entity_id, entity_type, **kwargs):
        """
        Generate a simple Entity with Widget and Position, but nothing else.

        This method is meant for decorative elements (ie some garbage on the
        floor). All _create_{garbage_type_item} methods will redirect here to
        avoid writing tons of boilerplate methods.
        :param entity_id: Entity ID
        :param type: a type of object.
        :return:
        """
        e = Entity(id=entity_id)
        widget = Widget(*self.atlas.get_element(entity_type))
        e.add_component(WidgetComponent(self.dispatcher, widget))
        e.add_component(PositionComponent(self.dispatcher))
        e.add_component(DestructorComponent(self.dispatcher))
        return e

    def generate_barrier(self, entity_id, entity_type, **kwargs):
        """
        Generate a simple Entity with Widget, Position, and CollisionComponent.

        This method is used for various un-passable entities without complex
        logic or animations, like walls, fences, barriers, trees and whatnot.
        It relies on the factory class having self.face_positions,
        self.face_sizes and self.depths dictionaries for CollisionComponents.
        :param entity_id:
        :param type:
        :return:
        """
        e = Entity(id=entity_id)
        widget = Widget(*self.atlas.get_element(entity_type))
        e.add_component(WidgetComponent(self.dispatcher, widget))
        e.add_component(PositionComponent(self.dispatcher))
        e.add_component(CollisionComponent(self.dispatcher,
                                           face_position = self.face_positions[entity_type],
                                           face_size=self.face_sizes[entity_type],
                                           z_shift=(1, -1),
                                           depth=self.depths[entity_type]))
        e.add_component(DestructorComponent(self.dispatcher))
        return e

    def _create_dept_range_table(self, entity_id, **kwargs):
        """
        Doesn't have CollisionComponent to permit shooting
        :param entity_id:
        :param kwargs:
        :return:
        """
        e = Entity(id=entity_id)
        widget = Widget(*self.atlas.get_element('dept_range_table'))
        e.add_component(WidgetComponent(self.dispatcher, widget))
        e.add_component(PositionComponent(self.dispatcher))
        e.add_component(DestructorComponent(self.dispatcher))
        e.add_component(CollisionComponent(self.dispatcher,
                                           face_position=(0, 13),
                                           face_size=(5, 7),
                                           z_shift=(1, -1),
                                           depth=12))
        return e

    def _create_barrel(self, entity_id, **kwargs):
        barrel_entity = Entity(id=entity_id)
        widget = SimpleAnimationWidget(Animation((self.atlas.get_element(
                                                      'barrel_1'),
                                                  self.atlas.get_element(
                                                      'barrel_2')),
                                                  3),
                                       emit_ecs=True)
        barrel_entity.add_component(PositionComponent(self.dispatcher))
        barrel_entity.add_component(WidgetComponent(self.dispatcher, widget))
        barrel_entity.add_component(CollisionComponent(self.dispatcher,
                                                       face_position=(0, 2),
                                                       face_size=(6, 7),
                                                       z_shift=(1, -1),
                                                       depth=2))
        barrel_entity.add_component(DestructorComponent(self.dispatcher))
        return barrel_entity

    def _create_level_switch(self, entity_id, **kwargs):
        e = Entity(entity_id)
        widget = SimpleAnimationWidget(Animation((self.atlas.get_element('level_switch_1'),
                                                  self.atlas.get_element('level_switch_2'),
                                                  self.atlas.get_element('level_switch_3')),
                                                 2),
                                       emit_ecs=True)
        e.add_component(WidgetComponent(self.dispatcher, widget))
        e.add_component(PositionComponent(self.dispatcher)),
        e.add_component(DestructorComponent(self.dispatcher))
        return e
    
    def _create_cop(self, entity_id, **kwargs):
        cop_entity = Entity(id=entity_id)
        widget = SwitchingWidget(images_dict={'r_1': self.atlas.get_element('cop_r_1'),
                                              'r_2': self.atlas.get_element('cop_r_2'),
                                              'l_1': self.atlas.get_element('cop_l_1'),
                                              'l_2': self.atlas.get_element('cop_l_2')},
                                 initial_image='r_1')
        # Useful for quickly testing assets
        # widget = SwitchingWidget(
        #     images_dict={'r_1': self.atlas.get_element('scientist_f_r_1'),
        #                  'r_2': self.atlas.get_element('scientist_f_r_2'),
        #                  'l_1': self.atlas.get_element('scientist_f_l_1'),
        #                  'l_2': self.atlas.get_element('scientist_f_l_2')},
        #     initial_image='r_1')
        # f_l = self._create_hand(f'{entity_id}_hand_fl',
        #                         'scientist_hand_forward', direction='l')
        # f_r = self._create_hand(f'{entity_id}_hand_fr',
        #                         'scientist_hand_forward', direction='r')
        # b_l = self._create_hand(f'{entity_id}_hand_bl', 'scientist_hand_back',
        #                         direction='l')
        # b_r = self._create_hand(f'{entity_id}_hand_br', 'scientist_hand_back',
        #                         direction='r')
        cop_entity.add_component(WalkerComponent(self.dispatcher))
        cop_entity.add_component(SwitchWidgetComponent(self.dispatcher, widget))
        cop_entity.add_component(WalkerCollisionComponent(self.dispatcher,
                                                          depth=1))
        cop_entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        cop_entity.add_component(InputComponent(self.dispatcher))
        cop_entity.add_component(FactionComponent(self.dispatcher,
                                                  faction='police'))
        cop_entity.add_component(CharacterHealthComponent(self.dispatcher,
                                                          corpse='cop_corpse',
                                                          hitpoints=10))
        cop_entity.add_component(DestructorComponent(self.dispatcher))
        # Creating hand entities
        f_l = self._create_hand(f'{entity_id}_hand_fl', 'cop_hand_forward',
                                direction='l')
        f_r = self._create_hand(f'{entity_id}_hand_fr', 'cop_hand_forward',
                                direction='r')
        b_l = self._create_hand(f'{entity_id}_hand_bl', 'cop_hand_back',
                                direction='l')
        b_r = self._create_hand(f'{entity_id}_hand_br', 'cop_hand_back',
                                         direction='r')
        for hand in (f_l, f_r, b_l, b_r):
            self.dispatcher.add_event(BearEvent('ecs_create', hand))
            hand.position.tracked_entity = entity_id
        left_fist = self._create_fist(f'fist_{entity_id}_left',
                                 owning_entity=cop_entity)
        self.dispatcher.add_event(BearEvent('ecs_create', left_fist))
        right_fist = self._create_fist(f'fist_{entity_id}_right',
                                       owning_entity=cop_entity)
        self.dispatcher.add_event(BearEvent('ecs_create', right_fist))
        cop_entity.add_component(HandInterfaceComponent(self.dispatcher,
                                                        hand_entities={
                                                            'forward_l': f_l.id,
                                                            'forward_r': f_r.id,
                                                            'back_l': b_l.id,
                                                            'back_r': b_r.id},
                                                        hands_offsets={
                                                            'forward_l': (-2, 5),
                                                            'forward_r': (0, 5),
                                                            'back_l': (-3, 4),
                                                            'back_r': (3, 4)},
                                                        item_offsets={
                                                            'forward_l': (0, 0),
                                                            'forward_r': (7, 0),
                                                            'back_l': (0, 0),
                                                            'back_r': (4, 0)},
                                                        left_item=left_fist.id,
                                                        right_item=right_fist.id))
        self.dispatcher.add_event(BearEvent(event_type='brut_focus',
                                            event_value=entity_id))
        return cop_entity
    
    def _create_nunchaku_punk(self, entity_id, **kwargs):
        nunchaku = Entity(id=entity_id)
        widget = SwitchingWidget(images_dict={'r_1': self.atlas.get_element('nunchaku_punk_r_1'),
                                              'r_2': self.atlas.get_element('nunchaku_punk_r_2'),
                                              'l_1': self.atlas.get_element('nunchaku_punk_l_1'),
                                              'l_2': self.atlas.get_element('nunchaku_punk_l_2'),
                                  },
                                 initial_image='l_1')
        nunchaku.add_component(SwitchWidgetComponent(self.dispatcher, widget))
        nunchaku.add_component(WalkerComponent(self.dispatcher))
        nunchaku.add_component(WalkerCollisionComponent(self.dispatcher,
                                                        depth=1))
        nunchaku.add_component(SpawnerComponent(self.dispatcher, factory=self))
        nunchaku.add_component(DestructorComponent(self.dispatcher))
        nunchaku.add_component(CharacterHealthComponent(self.dispatcher,
                                                        corpse='nunchaku_punk_corpse',
                                                        hitpoints=5))
        nunchaku.add_component(MeleeControllerComponent(self.dispatcher))
        nunchaku.add_component(FactionComponent(self.dispatcher,
                                                  faction='punks'))
        weapon = self._create_nunchaku(f'{entity_id}_nunchaku', owning_entity=nunchaku)
        self.dispatcher.add_event(BearEvent('ecs_create', weapon))
        fist = self._create_fist(f'fist_{entity_id}',
                                       owning_entity=nunchaku)
        self.dispatcher.add_event(BearEvent('ecs_create', fist))
        # Creating hand entities
        f_l = self._create_hand(f'{entity_id}_hand_fl',
                                'nunchaku_punk_hand_forward', direction='l')
        f_r = self._create_hand(f'{entity_id}_hand_fr',
                                'nunchaku_punk_hand_forward', direction='r')
        b_l = self._create_hand(f'{entity_id}_hand_bl',
                                'nunchaku_punk_hand_back', direction='l')
        b_r = self._create_hand(f'{entity_id}_hand_br',
                                'nunchaku_punk_hand_back', direction='r')
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
                                                        right_item=weapon.id,
                                                        left_item=fist.id))
        return nunchaku

    def _create_bottle_punk(self, entity_id, **kwargs):
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
        punk.add_component(WalkerCollisionComponent(self.dispatcher,
                                                    depth=1))
        punk.add_component(SpawnerComponent(self.dispatcher, factory=self))
        punk.add_component(DestructorComponent(self.dispatcher))
        punk.add_component(CharacterHealthComponent(self.dispatcher,
                                                    corpse='bottle_punk_corpse',
                                                    hitpoints=5))
        punk.add_component(BottleControllerComponent(self.dispatcher))
        punk.add_component(FactionComponent(self.dispatcher,
                                                faction='punks'))
        f_l = self._create_hand(f'{entity_id}_hand_fl',
                                'bottle_punk_hand_forward', direction='l')
        f_r = self._create_hand(f'{entity_id}_hand_fr',
                                'bottle_punk_hand_forward', direction='r')
        b_l = self._create_hand(f'{entity_id}_hand_bl',
                                'bottle_punk_hand_back', direction='l')
        b_r = self._create_hand(f'{entity_id}_hand_br',
                                'bottle_punk_hand_back', direction='r')
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
                                                          'forward_l': (-1, 6),
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

    def _create_cop_jump(self, entity_id, direction='r', **kwargs):
        e = Entity(id=entity_id)
        widget=Widget(*self.atlas.get_element(f'cop_jump_{direction}'))
        e.add_component(WidgetComponent(self.dispatcher, widget))
        vx = 60 if direction == 'r' else -60
        e.add_component(PositionComponent(self.dispatcher,
                                          vx=vx))
        e.add_component(DecayComponent(self.dispatcher,
                                       destroy_condition='timeout',
                                       lifetime=0.1))
        e.add_component(DestructorComponent(self.dispatcher))
        return e

    def _create_invis(self, entity_id, size=(0, 0), **kwargs):
        """
        Create an impassable background object
        :param x: xpos
        :param y: ypos
        :param size: size tuple
        :return:
        """
        bg_entity = Entity(id=entity_id)
        chars = [[' ' for x in range(size[0])] for y in range(size[1])]
        colors = copy_shape(chars, 'gray')
        widget = Widget(chars, colors)
        bg_entity.add_component(WidgetComponent(self.dispatcher, widget,
                                                owner=bg_entity))
        bg_entity.add_component(PositionComponent(self.dispatcher))
        bg_entity.add_component(DestructorComponent(self.dispatcher))
        return bg_entity

    def _create_muzzle_flash(self, entity_id, direction='r', **kwargs):
        """
        A muzzle flash for a pistol
        :param entity_id:
        :param direction:
        :param kwargs:
        :return:
        """
        muzzle = Entity(id=entity_id)
        if direction == 'r':
            widget = Widget(*self.atlas.get_element('shot_r'))
        else:
            widget = Widget(*self.atlas.get_element('shot_l'))
        muzzle.add_component(WidgetComponent(self.dispatcher, widget))
        muzzle.add_component(DestructorComponent(self.dispatcher))
        muzzle.add_component(PositionComponent(self.dispatcher))
        muzzle.add_component(DecayComponent(self.dispatcher,
                                            destroy_condition='timeout',
                                            lifetime=0.1))
        return muzzle

    def _create_bullet(self, entity_id, direction='r', z_level=10, **kwargs):
        """
        Create a simple projectile
        :param speed:
        :return:
        """
        if direction == 'r':
            vx = 50
        else:
            vx = -50
        bullet_entity = Entity(id=entity_id)
        bullet_entity.add_component(WidgetComponent(self.dispatcher,
            SimpleAnimationWidget(Animation((self.atlas.get_element(f'bullet_{direction}_1'),
                                             self.atlas.get_element(f'bullet_{direction}_2'),
                                             self.atlas.get_element(f'bullet_{direction}_3'),
                                             ), 10),
                                  z_level=z_level)))
        bullet_entity.add_component(PositionComponent(self.dispatcher, vx=vx,
                                                      affect_z=False))
        bullet_entity.add_component(ProjectileCollisionComponent(self.dispatcher,
                                                                 damage=1,
                                                                 depth=3))
        bullet_entity.add_component(DestructorComponent(self.dispatcher))
        return bullet_entity

    def _create_punch(self, entity_id, direction='r', z_level=10, **kwargs):
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
                                    f'punch_{direction}'),
                                       z_level=z_level)))
        if direction == 'r':
            vx = 50
        else:
            vx = -50
        punch.add_component(PositionComponent(self.dispatcher, vx=vx,
                                              affect_z=False))
        punch.add_component(ProjectileCollisionComponent(self.dispatcher,
                                                         damage=3,
                                                         depth=3))
        punch.add_component(DestructorComponent(self.dispatcher))
        punch.add_component(DecayComponent(self.dispatcher,
                                           destroy_condition='timeout',
                                           lifetime=0.1))
        return punch

    def _create_bottle(self, entity_id, direction='r', z_level=10, **kwargs):
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
                                           z_level=z_level,
                                           emit_ecs=True)
            vx = 20
        else:
            widget = SimpleAnimationWidget(Animation((self.atlas.get_element('bottle_nw'),
                                                      self.atlas.get_element('bottle_sw'),
                                                      self.atlas.get_element('bottle_se'),
                                                      self.atlas.get_element('bottle_ne')),
                                                      8),
                                           z_level=z_level,
                                           emit_ecs=True)
            vx = -20
        entity.add_component(WidgetComponent(self.dispatcher, widget))
        entity.add_component(GravityPositionComponent(self.dispatcher,
                                               acceleration=40, vx=vx, vy=-35,
                                               affect_z=False))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(GrenadeComponent(self.dispatcher,
                                              spawned_item='flame'))
        entity.add_component(GrenadeCollisionComponent(self.dispatcher))
        entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        return entity

    def _create_flame(self, entity_id, **kwargs):
        """
        A flame on the ground
        :param entity_id:
        :return:
        """
        entity = Entity(id=entity_id)
        widget = SimpleAnimationWidget(Animation((self.atlas.get_element('flame_1'),
                                                  self.atlas.get_element('flame_2')),
                                                 3),
                                       emit_ecs=True)
        entity.add_component(WidgetComponent(self.dispatcher, widget))
        entity.add_component(PositionComponent(self.dispatcher))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(DecayComponent(self.dispatcher,
                                            destroy_condition='timeout',
                                            lifetime=5.0))
        entity.add_component(HazardCollisionComponent(self.dispatcher,
                                                      depth=2,
                                                      passable=True))
        return entity

    def _create_target(self, entity_id, **kwargs):
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
        target_entity.add_component(CollisionComponent(self.dispatcher,
                                           face_position=(0, 2),
                                           face_size=(7, 8),
                                           z_shift=(1, -1),
                                           depth=4))
        return target_entity

    # TODO: some common method for spawning single-use attack animations.
    def _create_hand(self, entity_id, hand_type=None, direction='r', **kwargs):
        entity = Entity(entity_id)
        chars, colors = self.atlas.get_element(f'{hand_type}_{direction}')
        entity.add_component(WidgetComponent(self.dispatcher,
                                             Widget(chars, colors)))
        entity.add_component(AttachedPositionComponent(self.dispatcher,
                                                       affect_z=False))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False))
        return entity

    def _create_pistol(self, entity_id, owning_entity=None, **kwargs):
        entity = Entity(entity_id)
        widget = SwitchingWidget(images_dict={'l': self.atlas.get_element('pistol_l'),
                                              'r': self.atlas.get_element('pistol_r')},
                                 initial_image='r')
        entity.add_component(SwitchWidgetComponent(self.dispatcher,
                                                   widget))
        entity.add_component(SpawningItemBehaviourComponent(self.dispatcher,
                                owning_entity=owning_entity,
                                spawned_items={'bullet': {'r': (1, 0),
                                                         'l': (-2, 0)},
                                               'muzzle_flash': {'r': (5, -1),
                                                               'l': (-2, -1)}},
                                item_name='Service pistol',
                                item_description='Reliable, if somewhat\nunderpowered, police sidearm\nCited as a main reason for\na bring-your-own-gun policy.'))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False,
                                             should_hide=False))
        entity.add_component(CollectableBehaviourComponent(self.dispatcher))
        entity.add_component(PositionComponent(self.dispatcher, affect_z=False))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        return entity

    def _create_fist(self, entity_id, owning_entity=None, **kwargs):
        entity = Entity(entity_id)
        widget = SwitchingWidget(
            images_dict={'l': self.atlas.get_element('fist_l'),
                         'r': self.atlas.get_element('fist_r')},
            initial_image='r')
        entity.add_component(SwitchWidgetComponent(self.dispatcher,
                                                   widget))
        entity.add_component(SpawningItemBehaviourComponent(self.dispatcher,
                                    owning_entity=owning_entity,
                                    spawned_items={'punch': {'r': (-3, -2),
                                                             'l': (2, -2)}},
                                    item_name='Fist',
                                    item_description='Your own hand in punch mode.\nIt is not gonna break down\nany walls, but at least it\'s\nalways with you.'))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False,
                                             should_hide=False))
        entity.add_component(PositionComponent(self.dispatcher, affect_z=False))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        return entity

    def _create_nunchaku(self, entity_id, owning_entity=None, **kwargs):
        entity = Entity(entity_id)
        widget = SwitchingWidget(
            images_dict={'l': self.atlas.get_element('nunchaku_l'),
                         'r': self.atlas.get_element('nunchaku_r')},
            initial_image='r')
        entity.add_component(SwitchWidgetComponent(self.dispatcher,
                                                   widget))
        entity.add_component(SpawningItemBehaviourComponent(self.dispatcher,
                                    owning_entity=owning_entity,
                                    spawned_items={'punch': {'r': (8, -1),
                                                             'l': (-1, -2)}},
                                    item_name='Nunchaku',
                                    item_description='Two sticks and a length of\nchain. Great range, but\nuseless in close quarters.'))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False,
                                             should_hide=False))
        entity.add_component(CollectableBehaviourComponent(self.dispatcher))
        entity.add_component(PositionComponent(self.dispatcher, affect_z=False))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        return entity

    def _create_bottle_launcher(self, entity_id, owning_entity=None, **kwargs):
        entity = Entity(entity_id)
        widget = SwitchingWidget(
            images_dict={'l': self.atlas.get_element('bottle_ne'),
                         'r': self.atlas.get_element('bottle_nw')},
            initial_image='r')
        entity.add_component(SwitchWidgetComponent(self.dispatcher,
                                                   widget))
        entity.add_component(CollectableBehaviourComponent(self.dispatcher))
        entity.add_component(SpawningItemBehaviourComponent(self.dispatcher,
                                    owning_entity=owning_entity,
                                    spawned_items={'bottle': {'r': (2, -2),
                                                              'l': (-4, -2)}},
                                    item_name='Molotov',
                                    item_description='Looks cool in a riot, but\ncannot be aimed other than\n"In that general direction".'))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False,
                                             should_hide=False))
        entity.add_component(PositionComponent(self.dispatcher, affect_z=False))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        return entity

#TODO: general character creation method