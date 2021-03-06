from bear_hug.bear_utilities import copy_shape
from bear_hug.ecs import WidgetComponent, deserialize_entity, \
    WalkerCollisionComponent, DecayComponent, SwitchWidgetComponent
from bear_hug.widgets import SimpleAnimationWidget, Animation, Widget, \
    SwitchingWidget, Label

from ai import *
from background import tile_randomly, generate_bg, ghetto_transition, \
    dept_transition, lab_transition
from components import *
from widgets import ParticleWidget, LevelSwitchWidget, SignpostWidget


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
        # TODO: move decoration and barried data to TSV or something
        self.decorations = {'can', 'can2', 'cigarettes', 'garbage_bag',
                            'bucket', 'pizza_box',
                            'cop_corpse', 'bottle_punk_corpse',
                            'nunchaku_punk_corpse',
                            'scientist_f_corpse', 'scientist_f2_corpse',
                            'scientist_m_corpse', 'scientist_m2_corpse'}
        self.barriers = {'broken_car', 'barricade_1', 'barricade_2',
                         'barricade_3', 'dept_locker', 'dept_fence',
                         'dept_bench', 'dept_wall_inner', 'punchbag',
                         'dept_table_1', 'dept_table_2', 'dept_chair_1',
                         'dept_chair_2', 'dept_weight',
                         'science_table_1', 'science_table_2',
                         'science_table_3', 'science_table_4',
                         'science_device_1', 'lab_wall_inner'}
        self.face_positions = {'broken_car': (0, 3),
                               'barricade_1': (0, 2),
                               'barricade_2': (0, 3),
                               'barricade_3': (0, 5),
                               'dept_locker': (0, 3),
                               'dept_fence': (0, 0),
                               'dept_bench': (0, 2),
                               'dept_wall_inner': (0, 11),
                               'lab_wall_inner': (0, 11),
                               'punchbag': (0, 0),
                               'dept_weight': (0, 8),
                               'dept_table_1': (0, 10),
                               'dept_table_2': (0, 11),
                               'dept_chair_1': (0, 2),
                               'dept_chair_2': (0, 2),
                               'science_table_1': (0, 9),
                               'science_table_2': (0, 6),
                               'science_table_3': (0, 9),
                               'science_table_4': (0, 9),
                               'science_device_1': (0, 3)}
        self.face_sizes = {'broken_car': (33, 11),
                           'barricade_1': (7, 14),
                           'barricade_2': (9, 11),
                           'barricade_3': (11, 8),
                           'dept_locker': (6, 17),
                           'dept_fence': (21, 14),
                           'dept_bench': (17, 5),
                           'dept_wall_inner': (3, 21),
                           'lab_wall_inner': (3, 20),
                           'punchbag': (3, 26),
                           'dept_weight': (23, 5),
                           'dept_table_1': (10, 8),
                           'dept_table_2': (11, 8),
                           'dept_chair_1': (5, 10),
                           'dept_chair_2': (5, 10),
                           'science_table_1': (11, 9),
                           'science_table_2': (29, 9),
                           'science_table_3': (29, 9),
                           'science_table_4': (11, 9),
                           'science_device_1': (6, 17)}
        self.depths = {'broken_car': 4,
                       'barricade_1': 5,
                       'barricade_2': 5,
                       'barricade_3': 4,
                       'dept_locker': 3,
                       'dept_fence': 0,
                       'dept_bench': 2,
                       'dept_wall_inner': 11,
                       'lab_wall_inner': 11,
                       'punchbag': 1,
                       'dept_weight': 5,
                       'dept_table_1': 7,
                       'dept_table_2': 7,
                       'dept_chair_1': 1,
                       'dept_chair_2': 1,
                       'science_table_1': 7,
                       'science_table_2': 2,
                       'science_table_3': 2,
                       'science_table_4': 7,
                       'science_device_1': 3}

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
        # make sure there is no collision with entity names that would be
        # generated later
        l = entity.id.split('_')
        name = '_'.join(l[:-1])
        if name in self.counts:
            num = int(l[-1])
            if num > self.counts[name]:
                print(name, num)
                self.counts[name] = num
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
            try:
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
                                           face_position=self.face_positions[entity_type],
                                           face_size=self.face_sizes[entity_type],
                                           z_shift=(1, -1),
                                           depth=self.depths[entity_type]))
        e.add_component(DestructorComponent(self.dispatcher))
        return e

    def _create_message(self, entity_id, text = 'Sample text\nsample text',
                        vx=0, vy=0, destroy_condition='keypress', lifetime=2.0,
                        color='white',
                        **kwargs):
        message = Entity(id=entity_id)
        widget = Label(text, z_level=200, color=color)
        message.add_component(WidgetComponent(self.dispatcher, widget))
        message.add_component(PositionComponent(self.dispatcher, vx=vx, vy=vy,
                                                affect_z=False))
        message.add_component(DestructorComponent(self.dispatcher))
        message.add_component(DecayComponent(self.dispatcher,
                                             destroy_condition=destroy_condition,
                                             lifetime=lifetime))
        return message

    def _create_ghetto_bg(self, entity_id, size=(50, 20), **kwargs):
        wall = Entity(id=entity_id)
        w = generate_bg(self.atlas, ghetto_transition, size[0])
        widget = Widget(*w)
        wall.add_component(WidgetComponent(self.dispatcher, widget))
        wall.add_component(PositionComponent(self.dispatcher, affect_z=True))
        wall.add_component(DestructorComponent(self.dispatcher))
        wall.add_component(CollisionComponent(self.dispatcher, depth=20))
        return wall

    def _create_dept_bg(self, entity_id, size=(50, 20), **kwargs):
        wall = Entity(id=entity_id)
        w = generate_bg(self.atlas, dept_transition, size[0])
        widget = Widget(*w)
        wall.add_component(WidgetComponent(self.dispatcher, widget))
        wall.add_component(PositionComponent(self.dispatcher, affect_z=True))
        wall.add_component(DestructorComponent(self.dispatcher))
        wall.add_component(CollisionComponent(self.dispatcher, depth=20))
        return wall

    def _create_lab_bg(self, entity_id, size=(50, 20), **kwargs):
        wall = Entity(id=entity_id)
        w = generate_bg(self.atlas, lab_transition, size[0])
        wall.add_component(WidgetComponent(self.dispatcher, Widget(*w)))
        wall.add_component(PositionComponent(self.dispatcher, affect_z=True))
        wall.add_component(DestructorComponent(self.dispatcher))
        wall.add_component(CollisionComponent(self.dispatcher, depth=20))
        return wall

    def _create_floor(self, entity_id, size=(150, 30), **kwargs):
        floor = Entity(id=entity_id)
        widget = Widget(*tile_randomly(self.atlas, 'floor_tile_1',
                                                  'floor_tile_2',
                                                  'floor_tile_3',
                                                  size=size),
                        z_level=-1)
        # Disable affect_z so that floor won't overlap everything
        floor.add_component(PositionComponent(self.dispatcher, affect_z=False))
        floor.add_component(WidgetComponent(self.dispatcher, widget))
        floor.add_component(DestructorComponent(self.dispatcher))
        return floor

    def _create_title(self, entity_id, image_id='ghetto_title',
                      bg_sound='ghetto_walk_bg'):
        # TODO: animate title cards
        e = Entity(entity_id)
        e.add_component(WidgetComponent(self.dispatcher,
                                        Widget(*self.atlas.get_element(image_id),
                                               z_level=100)))
        e.add_component(PositionComponent(self.dispatcher, affect_z=False))
        e.add_component(SoundDestructorComponent(self.dispatcher,
                                                 bg_sound=bg_sound))
        e.add_component(DecayComponent(self.dispatcher,
                                       destroy_condition='timeout',
                                       lifetime=2.0))
        return e



    def _create_particle_explosion(self, entity_id, size=(10, 10),
                                   character='*', char_count=10, char_speed=5,
                                   color='red', lifetime=1, **kwargs):
        e = Entity(entity_id)
        w = ParticleWidget(size=size, character=character, color=color,
                           char_count=char_count, char_speed=char_speed,
                           z_level=50)
        e.add_component(WidgetComponent(self.dispatcher, w))
        e.add_component(PositionComponent(self.dispatcher, affect_z=False))
        e.add_component(DestructorComponent(self.dispatcher))
        e.add_component(DecayComponent(self.dispatcher,
                                       destroy_condition='timeout',
                                       lifetime=lifetime))
        return e

################################################################################
# BARRIERS AND DECORATIONS WITH INTERNAL LOGIC
################################################################################

    def _create_dept_range_table(self, entity_id, **kwargs):
        """
        A low table that can be shot over.
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

    def _create_level_switch(self, entity_id, size=(25, 5),
                             next_level='ghetto_test',
                             **kwargs):
        e = Entity(entity_id)
        widget = LevelSwitchWidget(size=size)
        e.add_component(LevelSwitchComponent(self.dispatcher,
                                             next_level=next_level))
        e.add_component(WidgetComponent(self.dispatcher, widget))
        e.add_component(PositionComponent(self.dispatcher))
        e.add_component(DestructorComponent(self.dispatcher))
        e.add_component(CollisionComponent(self.dispatcher, depth=size[1],
                                           z_shift=(1, -1),
                                           face_position=(0, size[1]),
                                           face_size=(size[0] - size[1] - 1, 1),
                                           passable=True))
        return e

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
        A target which changes its appearance when damaged
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
                            hit_sounds=('target_hit', ),
                            widgets_dict={5: 'destroyed',
                             10: 'severe',
                             15: 'slight',
                             20: 'intact'},
                            hitpoints=20))
        target_entity.add_component(PositionComponent(self.dispatcher))
        target_entity.add_component(DestructorComponent(self.dispatcher))
        target_entity.add_component(CollisionComponent(self.dispatcher,
                                           face_position=(0, 2),
                                           face_size=(7, 8),
                                           z_shift=(1, -1),
                                           depth=4))
        return target_entity

    def _create_signpost(self, entity_id, text='TEST TEST\nTEST TEST',
                         text_color='blue'):
        post = Entity(entity_id)
        widget = SignpostWidget(*self.atlas.get_element('signpost'),
                                text=text, text_color=text_color)
        post.add_component(WidgetComponent(self.dispatcher, widget))
        post.add_component(PositionComponent(self.dispatcher))
        post.add_component(CollisionComponent(self.dispatcher,
                                              depth=1))
        post.add_component(DestructorComponent(self.dispatcher))
        return post

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
        bg_entity.add_component(CollisionComponent(self.dispatcher,
                                                   depth=size[1],
                                                   face_size=size,
                                                   passable=False))
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

    def _create_spike(self, entity_id, powered=False, **kwargs):
        spike = Entity(id=entity_id)
        widget = SwitchingWidget(images_dict={'unpowered': self.atlas.get_element('science_spike_unpowered'),
                                              'powered': self.atlas.get_element('science_spike_powered')},
                                 initial_image='unpowered')
        spike.add_component(SwitchWidgetComponent(self.dispatcher, widget))
        spike.add_component(PositionComponent(self.dispatcher))
        spike.add_component(DestructorComponent(self.dispatcher))
        spike.add_component(CollisionComponent(self.dispatcher,
                                               z_shift=(1, -1),
                                               depth=2))
        spike.add_component(SpawnerDestructorHealthComponent(self.dispatcher,
                                               hitpoints=8,
                                               spawned_item='spikebox',
                                               relative_pos=(0, 14)))
        spike.add_component(SpikePowerInteractionComponent(self.dispatcher,
                                                           action_cooldown=0.1,
                                                           range=40,
                                                           powered=powered))
        spike.add_component(SpawnerComponent(self.dispatcher, factory=self))
        return spike

    def _create_science_prop(self, entity_id, **kwargs):
        prop = Entity(entity_id)
        widget = SwitchingWidget(images_dict={'powered': self.atlas.get_element('science_prop_powered'),
                                              'unpowered': self.atlas.get_element('science_prop_unpowered')},
                                 initial_image='unpowered')
        prop.add_component(SwitchWidgetComponent(self.dispatcher, widget))
        prop.add_component(PositionComponent(self.dispatcher))
        prop.add_component(CollisionComponent(self.dispatcher,
                                              depth=2,
                                              face_position=(0, 2),
                                              face_size=(8, 13),
                                              z_shift=(1, -1)))
        prop.add_component(SciencePropPowerInteractionComponent(self.dispatcher,
                                                                powered=False,
                                                                action_cooldown=0.2))
        prop.add_component(DestructorComponent(self.dispatcher))
        return prop

    def _create_science_healer(self, entity_id, **kwargs):
        healer = Entity(entity_id)
        widget = SwitchingWidget(images_dict={'powered': self.atlas.get_element('science_healer_powered'),
                                              'unpowered': self.atlas.get_element('science_healer_unpowered')},
                                 initial_image='unpowered')
        healer.add_component(SwitchWidgetComponent(self.dispatcher, widget))
        healer.add_component(PositionComponent(self.dispatcher))
        healer.add_component(CollisionComponent(self.dispatcher,
                                                depth=1,
                                                z_shift=(1, -1)))
        healer.add_component(HealerPowerInteractionComponent(self.dispatcher,
                                                             powered=False,
                                                             action_cooldown=0.2))
        healer.add_component(SpawnerComponent(self.dispatcher, factory=self))
        healer.add_component(DestructorComponent(self.dispatcher))
        return healer

    def _create_wall_switch(self, entity_id, initial_state=True, **kwargs):
        switch = Entity(entity_id)
        if initial_state:
            initial_image = 'wall_on'
        else:
            initial_image = 'wall_off'
        widget = SwitchingWidget(images_dict={'wall_on': self.atlas.get_element('wall_switch_on'),
                                              'wall_off': self.atlas.get_element('wall_switch_off')},
                                 initial_image=initial_image)
        switch.add_component(SwitchWidgetComponent(self.dispatcher, widget))
        switch.add_component(PositionComponent(self.dispatcher))
        switch.add_component(SwitchHealthComponent(self.dispatcher,
                                                   initial_state=True,
                                                   on_event_type='brut_change_config',
                                                   on_event_value=('sound', True),
                                                   off_event_type='brut_change_config',
                                                   off_event_value=('sound', False),
                                                   on_sound='switch_on',
                                                   off_sound='switch_off',
                                                   on_widget='wall_on',
                                                   off_widget='wall_off'))
        switch.add_component(DestructorComponent(self.dispatcher))
        switch.add_component(CollisionComponent(self.dispatcher,
                                                depth=2,
                                                z_shift=(1, -1)))
        return switch

    def _create_terminal_switch(self, entity_id, initial_state=True, **kwargs):
        switch = Entity(entity_id)
        if initial_state:
            initial_image = 'terminal_on'
        else:
            initial_image = 'terminal_off'
        widget = SwitchingWidget(images_dict={'terminal_on': self.atlas.get_element('terminal_switch_on'),
                                              'terminal_off': self.atlas.get_element('terminal_switch_off')},
                                 initial_image=initial_image)
        switch.add_component(SwitchWidgetComponent(self.dispatcher, widget))
        switch.add_component(PositionComponent(self.dispatcher))
        switch.add_component(SwitchHealthComponent(self.dispatcher,
                                                   initial_state=True,
                                                   on_sound='switch_on',
                                                   off_sound='switch_off',
                                                   on_widget='terminal_on',
                                                   off_widget='terminal_off',
                                                   on_event_type='brut_change_config',
                                                   on_event_value=('fullscreen', True),
                                                   off_event_type='brut_change_config',
                                                   off_event_value=('fullscreen', False)))
        switch.add_component(DestructorComponent(self.dispatcher))
        switch.add_component(CollisionComponent(self.dispatcher,
                                                depth=2,
                                                z_shift=(1, -1)))
        return switch

    def _create_settings_speaker(self, entity_id, **kwargs):
        speaker = Entity(entity_id)
        widget = SimpleAnimationWidget(
            Animation((self.atlas.get_element('speaker_1'),
                       self.atlas.get_element('speaker_2')),
                      4),
            emit_ecs=True)
        speaker.add_component(SpeakerWidgetComponent(self.dispatcher, widget))
        speaker.add_component(PositionComponent(self.dispatcher))
        speaker.add_component(DestructorComponent(self.dispatcher))
        speaker.add_component(CollisionComponent(self.dispatcher, depth=3,
                                                 z_shift=(1, -1)))
        return speaker

    def _create_ammo_pickup(self, entity_id, **kwargs):
        e = Entity(entity_id)
        e.add_component(WidgetComponent(self.dispatcher,
                                        Widget(*self.atlas.get_element('ammo_pickup'))))
        e.add_component(PositionComponent(self.dispatcher))
        e.add_component(DestructorComponent(self.dispatcher))
        e.add_component(AmmoPickupCollisionComponent(self.dispatcher,
                                                     passable=True,
                                                     depth=2))
        return e

    def _create_score_pickup(self, entity_id, score=5, **kwargs):
        e = Entity(entity_id)
        widget = SimpleAnimationWidget(Animation((self.atlas.get_element('coin_1'),
                                                  self.atlas.get_element('coin_3'),
                                                  self.atlas.get_element('coin_2')),
                                                 4),
                                       emit_ecs=True)
        e.add_component(WidgetComponent(self.dispatcher, widget))
        e.add_component(PositionComponent(self.dispatcher))
        e.add_component((DestructorComponent(self.dispatcher)))
        e.add_component(ScorePickupCollisionComponent(self.dispatcher,
                                                      passable=True,
                                                      score=score,
                                                      player_entity='cop_1'))
        return e

################################################################################
# CHARACTERS AND HANDS
################################################################################
    
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
                                                          hitpoints=15,
                                                          hit_sounds=('cop_hit', ),
                                                          death_sounds=('cop_death', )))
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

    def _create_cop_npc(self, entity_id, monologue=('Phrase 1', 'Phrase 2'),
                        **kwargs):
        cop_entity = Entity(id=entity_id)
        widget = SwitchingWidget(images_dict={'r_1': self.atlas.get_element('cop_r_1'),
                                              'r_2': self.atlas.get_element('cop_r_2'),
                                              'l_1': self.atlas.get_element('cop_l_1'),
                                              'l_2': self.atlas.get_element('cop_l_2')},
                                 initial_image='r_1')
        cop_entity.add_component(WalkerComponent(self.dispatcher))
        cop_entity.add_component(SwitchWidgetComponent(self.dispatcher, widget))
        cop_entity.add_component(WalkerCollisionComponent(self.dispatcher,
                                                          depth=1))
        cop_entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        cop_entity.add_component(FactionComponent(self.dispatcher,
                                                  faction='police'))
        cop_entity.add_component(CharacterHealthComponent(self.dispatcher,
                                                          corpse='cop_corpse',
                                                          hitpoints=10,
                                                          hit_sounds=('cop_hit', )))
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
        # AI
        ai = AIComponent(self.dispatcher,
                         states={'wait': WaitAIState(self.dispatcher,
                                                     enemy_factions=('punks',),
                                                     player_perception_distance=35,
                                                     player_id='cop_1',
                                                     player_arrival_state='talk'),
                                 'talk': TalkAIState(self.dispatcher,
                                                    player_id='cop_1',
                                                    player_perception_distance=35,
                                                    wait_state='wait',
                                                    phrase_sounds=('male_phrase_1',
                                                                   'male_phrase_2',
                                                                   'male_phrase_3',
                                                                   'male_phrase_4',
                                                                   'male_phrase_5'),
                                                    monologue=monologue,
                                                    phrase_delay=1.5)},
                         current_state='wait',
                         owner=cop_entity)
        return cop_entity

    def _create_dept_boss(self, entity_id, monologue=('Line 1', 'Line 2'),
                          **kwargs):
        """
        A monologue NPC boss
        :param entity_id:
        :param monologue:
        :param kwargs:
        :return:
        """
        boss = Entity(entity_id)
        # Two identical "phases" because WalkerComponent expects the entity to
        # have two right images and two left images for walking. Although the
        # boss cannot walk, he doesn't merit a separate subclass of
        # PositionComponent
        widget = SwitchingWidget(images_dict={'r_1': self.atlas.get_element('dept_boss_r'),
                                              'r_2': self.atlas.get_element('dept_boss_r'),
                                              'l_1': self.atlas.get_element('dept_boss_l'),
                                              'l_2': self.atlas.get_element('dept_boss_l')},
                                 initial_image='r_1')
        boss.add_component(SwitchWidgetComponent(self.dispatcher, widget))
        boss.add_component(WalkerComponent(self.dispatcher))
        boss.add_component(CollisionComponent(self.dispatcher, passable=False,
                                              face_position=(0, 14),
                                              face_size=(24, 10), depth=10,
                                              z_shift=(1, -1)))
        boss.add_component(DestructorComponent(self.dispatcher))
        boss.add_component(FactionComponent(self.dispatcher, faction='police'))
        boss.add_component(SpawnerComponent(self.dispatcher, factory=self))
        ai = AIComponent(self.dispatcher,
                         states={'wait': WaitAIState(self.dispatcher,
                                                     enemy_factions=('punks',),
                                                     player_perception_distance=35,
                                                     player_id='cop_1',
                                                     player_arrival_state='talk'),
                                 'talk': TalkAIState(self.dispatcher,
                                                    player_id='cop_1',
                                                    player_perception_distance=35,
                                                    wait_state='wait',
                                                    phrase_sounds=('male_phrase_1',
                                                                   'male_phrase_2',
                                                                   'male_phrase_3',
                                                                   'male_phrase_4',
                                                                   'male_phrase_5'),
                                                    monologue=monologue,
                                                    phrase_delay=1.5)},
                         current_state='wait',
                         owner=boss)
        boss.add_component(ai)
        return boss

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
                                                        hitpoints=7,
                                                        score=5,
                                                        hit_sounds=('punk_hit',
                                                                    'punk_death'),
                                                        death_sounds=('punk_death', )
                                                        ))
        ai = AIComponent(self.dispatcher,
                         states={'wait': WaitAIState(self.dispatcher,
                                                     enemy_perception_distance=65,
                                                     enemy_arrival_state='combat',
                                                     check_delay=0.2),
                                 'combat': CombatAIState(self.dispatcher,
                                                         enemy_perception_distance=65,
                                                         right_range=(12, 15),
                                                         left_range=(0, 0),
                                                         wait_state='wait')},
                         current_state='wait',
                         owner=nunchaku)
        nunchaku.add_component(ai)
        nunchaku.add_component(FactionComponent(self.dispatcher,
                                                  faction='punks'))
        weapon = self._create_nunchaku(f'nunchaku_{entity_id}',
                                       owning_entity=nunchaku)
        self.dispatcher.add_event(BearEvent('ecs_create', weapon))
        # Even if not used, both fists should exist for correct processing of
        # item drop during character destruction. Plus, I may want to add some
        # attack that forces enemies to drop their weapons
        left_fist = self._create_fist(f'fist_{entity_id}_left',
                                      owning_entity=nunchaku)
        self.dispatcher.add_event(BearEvent('ecs_create', left_fist))
        right_fist = self._create_fist(f'fist_{entity_id}_right',
                                       owning_entity=nunchaku)
        self.dispatcher.add_event(BearEvent('ecs_create', right_fist))
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
                                                        'forward_r': (8, 1),
                                                        'back_l': (0, -1),
                                                        'back_r': (4, 0)},
                                                      right_item=weapon.id,
                                                      left_item=left_fist.id))
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
                                                    hitpoints=7,
                                                    score=5,
                                                    hit_sounds=('punk_hit',
                                                                'punk_death'),
                                                    death_sounds=('punk_death', )))
        # punk.add_component(BottleControllerComponent(self.dispatcher))
        ai = AIComponent(self.dispatcher,
                         states={'wait': WaitAIState(self.dispatcher,
                                                     enemy_perception_distance=65,
                                                     enemy_arrival_state='combat',
                                                     check_delay=0.2),
                                 'combat': CombatAIState(self.dispatcher,
                                                         enemy_perception_distance=65,
                                                         left_range=(0, 7),
                                                         right_range=(35, 45),
                                                         wait_state='wait')},
                         current_state='wait',
                         owner=punk)
        punk.add_component(ai)
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
        # Even if not used, both fists should exist for correct processing of
        # item drop during character destruction. Plus, I may want to add some
        # attack that forces enemies to drop their weapons
        left_fist = self._create_fist(f'fist_{entity_id}_left',
                                      owning_entity=punk)
        self.dispatcher.add_event(BearEvent('ecs_create', left_fist))
        right_fist = self._create_fist(f'fist_{entity_id}_right',
                                       owning_entity=punk)
        self.dispatcher.add_event(BearEvent('ecs_create', right_fist))
        shiv = self._create_shiv(f'shiv_{entity_id}',
                                 owning_entity=punk)
        self.dispatcher.add_event(BearEvent('ecs_create', shiv))
        launcher = self._create_bottle_launcher(f'bottle_launcher_{entity_id}',
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
                                                      left_item=shiv.id,
                                                      right_item=launcher.id))
        return punk

    def _create_female_scientist(self, entity_id,
                                 monologue=('Line one\nline two', ),
                                 **kwargs):
        scientist = Entity(id=entity_id)
        widget = SwitchingWidget(
            images_dict={'r_1': self.atlas.get_element('scientist_f2_r_1'),
                         'r_2': self.atlas.get_element('scientist_f2_r_2'),
                         'l_1': self.atlas.get_element('scientist_f2_l_1'),
                         'l_2': self.atlas.get_element('scientist_f2_l_2'),
                         },
            initial_image='r_1')
        scientist.add_component(SwitchWidgetComponent(self.dispatcher, widget))
        scientist.add_component(WalkerComponent(self.dispatcher))
        scientist.add_component(WalkerCollisionComponent(self.dispatcher,
                                                    depth=1))
        scientist.add_component(SpawnerComponent(self.dispatcher, factory=self))
        scientist.add_component(DestructorComponent(self.dispatcher))
        scientist.add_component(FactionComponent(self.dispatcher,
                                                 faction='scientists'))
        scientist.add_component(CharacterHealthComponent(self.dispatcher,
                                                    corpse='scientist_f2_corpse',
                                                    hitpoints=5,
                                                    hit_sounds=('female_dmg', ),
                                                    death_sounds=(
                                                    'female_death',)))
        # Creating hand entities
        f_l = self._create_hand(f'{entity_id}_hand_fl',
                                'scientist_hand_forward',
                                direction='l')
        f_r = self._create_hand(f'{entity_id}_hand_fr',
                                'scientist_hand_forward',
                                direction='r')
        b_l = self._create_hand(f'{entity_id}_hand_bl',
                                'scientist_hand_back',
                                direction='l')
        b_r = self._create_hand(f'{entity_id}_hand_br',
                                'scientist_hand_back',
                                direction='r')
        for hand in (f_l, f_r, b_l, b_r):
            self.dispatcher.add_event(BearEvent('ecs_create', hand))
            hand.position.tracked_entity = entity_id
        left_fist = self._create_fist(f'fist_{entity_id}_left',
                                      owning_entity=scientist)
        self.dispatcher.add_event(BearEvent('ecs_create', left_fist))
        right_fist = self._create_fist(f'fist_{entity_id}_right',
                                       owning_entity=scientist)
        self.dispatcher.add_event(BearEvent('ecs_create', right_fist))
        scientist.add_component(HandInterfaceComponent(self.dispatcher,
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
        # AI
        ai = AIComponent(self.dispatcher,
                         states={'wait': WaitAIState(self.dispatcher,
                                                     player_id='cop_1',
                                                     player_perception_distance=50,
                                                     player_arrival_state='talk',
                                                     enemy_factions=('punks', ),
                                                     enemy_perception_distance=50,
                                                     enemy_arrival_state='run'),
                                 'run': RunawayAIState(self.dispatcher,
                                                       enemy_perception_distance=50,
                                                       wait_state='wait',
                                                       enemy_factions=('punks', )),
                                 'talk': TalkAIState(self.dispatcher,
                                                     player_id='cop_1',
                                                     player_perception_distance=50,
                                                     monologue=monologue,
                                                     enemy_factions=('punks, '),
                                                     enemy_perception_distance=50,
                                                     phrase_sounds=(
                                                     'female_phrase_1',
                                                     'female_phrase_2',
                                                     'female_phrase_3',
                                                     'female_phrase_4',
                                                     'female_phrase_5'
                                                     ),
                                                     phrase_delay=1.5)},
                         current_state='wait',
                         owner=scientist)
        scientist.add_component(ai)
        return scientist

    def _create_scientist_enemy(self, entity_id):
        scientist = Entity(id=entity_id)
        # Choosing between two male scientist models
        prefix = choice(('scientist_m', 'scientist_m2'))
        if prefix == 'scientist_m':
            hand_prefix = 'scientist_skinny_hand'
        else:
            hand_prefix = 'scientist_hand'
        widget = SwitchingWidget(
            images_dict={'r_1': self.atlas.get_element(f'{prefix}_r_1'),
                         'r_2': self.atlas.get_element(f'{prefix}_r_2'),
                         'l_1': self.atlas.get_element(f'{prefix}_l_1'),
                         'l_2': self.atlas.get_element(f'{prefix}_l_2'),
                         },
            initial_image='r_1')
        scientist.add_component(SwitchWidgetComponent(self.dispatcher, widget))
        scientist.add_component(WalkerComponent(self.dispatcher))
        scientist.add_component(WalkerCollisionComponent(self.dispatcher,
                                                         depth=1))
        scientist.add_component(SpawnerComponent(self.dispatcher, factory=self))
        scientist.add_component(DestructorComponent(self.dispatcher))
        scientist.add_component(FactionComponent(self.dispatcher,
                                                 faction='scientists'))
        scientist.add_component(CharacterHealthComponent(self.dispatcher,
                                                         corpse=f'{prefix}_corpse',
                                                         hitpoints=4,
                                                         hit_sounds=(
                                                             'male_dmg',),
                                                         death_sounds=(
                                                             'male_death',),
                                                         score=5))
        # Creating hand entities
        f_l = self._create_hand(f'{entity_id}_hand_fl',
                                f'{hand_prefix}_forward',
                                direction='l')
        f_r = self._create_hand(f'{entity_id}_hand_fr',
                                f'{hand_prefix}_forward',
                                direction='r')
        b_l = self._create_hand(f'{entity_id}_hand_bl',
                                f'{hand_prefix}_back',
                                direction='l')
        b_r = self._create_hand(f'{entity_id}_hand_br',
                                f'{hand_prefix}_back',
                                direction='r')
        for hand in (f_l, f_r, b_l, b_r):
            self.dispatcher.add_event(BearEvent('ecs_create', hand))
            hand.position.tracked_entity = entity_id
        # Even if not used, both fists should exist for correct processing of
        # item drop during character destruction. Plus, I may want to add some
        # attack that forces enemies to drop their weapons
        left_fist = self._create_fist(f'fist_{entity_id}_left',
                                      owning_entity=scientist)
        self.dispatcher.add_event(BearEvent('ecs_create', left_fist))
        right_fist = self._create_fist(f'fist_{entity_id}_right',
                                       owning_entity=scientist)
        self.dispatcher.add_event(BearEvent('ecs_create', right_fist))
        if prefix == 'scientist_m2':
            right_item = self._create_fist(f'fist_{entity_id}_right',
                                           owning_entity=scientist)
            fight_state = CombatAIState(self.dispatcher,
                                        enemy_perception_distance=65,
                                        left_range=(0, 7),
                                        right_range=(0, 7),
                                        wait_state='wait')
        else:
            right_item = self._create_emitter(f'emitter_{entity_id}',
                                              owning_entity=scientist)
            fight_state = CombatAIState(self.dispatcher,
                                          enemy_perception_distance=65,
                                          left_range=(0, 7),
                                          right_range=(8, 50),
                                          wait_state='wait')
        self.dispatcher.add_event(BearEvent('ecs_create', right_item))
        scientist.add_component(HandInterfaceComponent(self.dispatcher,
                                                       hand_entities={
                                                           'forward_l': f_l.id,
                                                           'forward_r': f_r.id,
                                                           'back_l': b_l.id,
                                                           'back_r': b_r.id},
                                                       hands_offsets={
                                                           'forward_l': (
                                                               -2, 5),
                                                           'forward_r': (0, 5),
                                                           'back_l': (-3, 4),
                                                           'back_r': (3, 4)},
                                                       item_offsets={
                                                           'forward_l': (0, 0),
                                                           'forward_r': (6, 0),
                                                           'back_l': (0, -1),
                                                           'back_r': (3, 0)},
                                                       left_item=left_fist.id,
                                                       right_item=right_item.id))
        # AI
        ai = AIComponent(self.dispatcher,
                         states={'wait': WaitAIState(self.dispatcher,
                                                     enemy_perception_distance=65,
                                                     enemy_arrival_state='combat',
                                                     check_delay=0.2),
                                 'combat': fight_state},
                         current_state='wait',
                         owner=scientist)
        scientist.add_component(ai)
        return scientist

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

    def _create_cop_jump(self, entity_id, direction='r', **kwargs):
        e = Entity(id=entity_id)
        widget = Widget(*self.atlas.get_element(f'cop_jump_{direction}'))
        e.add_component(WidgetComponent(self.dispatcher, widget))
        vx = 60 if direction == 'r' else -60
        e.add_component(PositionComponent(self.dispatcher,
                                          vx=vx))
        e.add_component(DecayComponent(self.dispatcher,
                                       destroy_condition='timeout',
                                       lifetime=0.1))
        e.add_component(DestructorComponent(self.dispatcher))
        return e

################################################################################
# PROJECTILES
################################################################################

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
                                                                 damage=5,
                                                                 depth=2))
        bullet_entity.add_component(DestructorComponent(self.dispatcher))
        return bullet_entity

    def _create_punch(self, entity_id, direction='r', z_level=10, damage=3,
                      **kwargs):
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
                                                         damage=damage,
                                                         depth=3))
        punch.add_component(DestructorComponent(self.dispatcher))
        punch.add_component(DecayComponent(self.dispatcher,
                                           destroy_condition='timeout',
                                           lifetime=0.1))
        return punch

    def _create_spark(self, entity_id, z_level=10, direction=None,
                      vx=25, vy=25, **kwargs):
        """
        A spark for science weapons and tools

        For the spark direction accepts either `vx` and `vy` which are directly
        transferred to the entity or `direction` (either 'r' or 'l')  which
        overrides vx and vy to (80, 0) and (-80, 0) respectively
        """
        # TODO: create a SparkLine kinda thing to optimize powered items
        # currently they emit about ten sparks per spike per second, thus
        # creating considerable lags. Could instead establish a permanent spark
        # line which would be a lot less costly to run. This thing would deal
        # damage in collided_by. Guess it would require a special spike-created
        # kind of spark because otherwise pistol sparks would establish
        # permanent lines from shooter to target.
        spark = Entity(id=entity_id)
        widget = SimpleAnimationWidget(Animation((self.atlas.get_element('spark_1'),
                                                  self.atlas.get_element('spark_2')),
                                                 6),
                                       z_level=z_level)
        spark.add_component(WidgetComponent(self.dispatcher, widget))
        if direction:
            if direction == 'r':
                vx = 80
                vy = 0
            else:
                vx = -80
                vy = 0
        spark.add_component(PositionComponent(self.dispatcher,
                                              vx=vx, vy =vy,
                                              affect_z=False))
        spark.add_component(PowerProjectileCollisionComponent(self.dispatcher,
                                                              damage=1,
                                                              depth=3))
        spark.add_component(DestructorComponent(self.dispatcher))
        return spark

    def _create_tall_spark(self, entity_id, direction=None,
                           vx=25, vy=25, **kwargs):
        """
        Analogous to the spark, but has 12 empty spaces below the spark to
        enable proper collisions during non-horizontal movement
        """
        spark = Entity(id=entity_id)
        ch1, col1 = self.atlas.get_element('spark_1')
        ch1 += 11*[[' ']]
        col1 += 11 * [['#000000']]
        ch2, col2 = self.atlas.get_element('spark_2')
        ch2 += 11*[[' ']]
        col2 += 11* [['#000000']]
        widget = SimpleAnimationWidget(Animation(((ch1, col1),
                                                  (ch2, col2)),
                                                 6))
        spark.add_component(WidgetComponent(self.dispatcher, widget))
        if direction:
            if direction == 'r':
                vx = 80
                vy = 0
            else:
                vx = -80
                vy = 0
        spark.add_component(PositionComponent(self.dispatcher,
                                              vx=vx, vy=vy))
        spark.add_component(PowerProjectileCollisionComponent(self.dispatcher,
                                                              damage=3,
                                                              depth=1))
        spark.add_component(DestructorComponent(self.dispatcher))
        return spark

    def _create_healing_projectile(self, entity_id, vx=0, vy=0, **kwargs):
        cross = Entity(entity_id)
        cross.add_component(WidgetComponent(self.dispatcher,
                                            Widget(*self.atlas.get_element('science_healing_projectile'))))
        cross.add_component(PositionComponent(self.dispatcher, vx=vx, vy=vy))
        cross.add_component(HealingProjectileCollisionComponent(self.dispatcher,
                                                                healing=2,
                                                                depth=2))
        cross.add_component((DestructorComponent(self.dispatcher)))
        cross.add_component(DecayComponent(self.dispatcher,
                                           destroy_condition='timeout',
                                           lifetime=2.0))
        return cross

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
            vx = 17
        else:
            widget = SimpleAnimationWidget(Animation((self.atlas.get_element('bottle_nw'),
                                                      self.atlas.get_element('bottle_sw'),
                                                      self.atlas.get_element('bottle_se'),
                                                      self.atlas.get_element('bottle_ne')),
                                                      8),
                                           z_level=z_level,
                                           emit_ecs=True)
            vx = -17
        entity.add_component(WidgetComponent(self.dispatcher, widget))
        entity.add_component(GravityPositionComponent(self.dispatcher,
                                               acceleration=40, vx=vx, vy=-35,
                                               affect_z=False))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(GrenadeComponent(self.dispatcher,
                                              explosion_sound='molotov_break',
                                              spawned_item='flame'))
        entity.add_component(GrenadeCollisionComponent(self.dispatcher))
        entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        return entity

################################################################################
# ITEMS
################################################################################

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
                                max_ammo=6,
                                use_sound='shot',
                                use_delay = 0.5,
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
                                    damage=3,
                                    use_delay=0.35,
                                    use_sound='fist',
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

    def _create_shiv(self, entity_id, owning_entity=None, **kwargs):
        entity = Entity(entity_id)
        widget = SwitchingWidget(
            images_dict={'r': self.atlas.get_element('shiv_r'),
                         'l': self.atlas.get_element('shiv_l')},
            initial_image='r')
        entity.add_component(SwitchWidgetComponent(self.dispatcher, widget))
        entity.add_component(SpawningItemBehaviourComponent(self.dispatcher,
                                    owning_entity=owning_entity,
                                    spawned_items={'punch': {'r': (-3, -2),
                                                             'l': (4, -2)}},
                                    use_delay=0.35,
                                    damage=5,
                                    item_name='Shiv',
                                    use_sound='shiv',
                                    item_description='A sharpened piece of steel,\none end wrapped in duct\ntape. Good enough for\nstabbing people.'))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False,
                                             should_hide=False))
        entity.add_component(PositionComponent(self.dispatcher, affect_z=False))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        entity.add_component(CollectableBehaviourComponent(self.dispatcher))
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
                                    damage=5,
                                    grab_offset={'r': (0, -1),
                                                 'l': (0, -1)},
                                    use_delay=0.6,
                                    use_sound='nunchaku',
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
                                    use_sound='molotov_throw',
                                    item_name='Molotov',
                                    use_delay=1,
                                    item_description='Looks cool in a riot, but\ncan only be aimed in\nthis or that general\ndirection.'))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False,
                                             should_hide=False))
        entity.add_component(PositionComponent(self.dispatcher, affect_z=False))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        return entity

    def _create_bandage(self, entity_id, owning_entity=None, **kwargs):
        entity = Entity(entity_id)
        widget = SwitchingWidget(
            images_dict={'r': self.atlas.get_element('bandage_r'),
                         'l': self.atlas.get_element('bandage_l')},
            initial_image='r')
        entity.add_component(SwitchWidgetComponent(self.dispatcher, widget))
        entity.add_component(CollectableBehaviourComponent(self.dispatcher))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False,
                                             should_hide=False))
        entity.add_component(HealingItemBehaviourComponent(self.dispatcher,
                                                    single_use=True,
                                                    use_sound='bandage',
                                                    healing=5,
                                                    owning_entity=owning_entity,
                                                    item_name='Bandage',
                                                    item_description='A piece of sterile bandage.\nIt isn\'t much, but still \na lot better than nothing.'))
        entity.add_component(PositionComponent(self.dispatcher, affect_z=False))
        entity.add_component(ParticleDestructorComponent(self.dispatcher,
                                                        spawned_item='particle_explosion',
                                                        relative_pos=(-5, -5),
                                                        size=(10, 10),
                                                        character=',',
                                                        char_count=8,
                                                        char_speed=10,
                                                        color='#4D3D26',
                                                        lifetime=0.3))
        entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        return entity

    def _create_emitter(self, entity_id, owning_entity=None, **kwargs):
        entity = Entity(entity_id)
        widget = SwitchingWidget(images_dict={
                                    'r': self.atlas.get_element('emitter_r'),
                                    'l': self.atlas.get_element('emitter_l')},
                                 initial_image='r')
        entity.add_component(SwitchWidgetComponent(self.dispatcher, widget))
        entity.add_component(CollectableBehaviourComponent(self.dispatcher))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False,
                                             should_hide=False))
        entity.add_component(PositionComponent(self.dispatcher, affect_z=False))
        entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        entity.add_component(DestructorComponent(self.dispatcher))
        entity.add_component(SpawningItemBehaviourComponent(self.dispatcher,
                                                            owning_entity=owning_entity,
                                                            spawned_items={
                                                                'spark': {'r': (9, 1),
                                                                          'l': (-1, 1)}},
                                                            grab_offset={'r': (-3, -2),
                                                                         'l': (3, -2)},
                                                            use_delay=0.5,
                                                            use_sound='emitter',
                                                            item_name='Spark emitter',
                                                            item_description='A tool for activating\nscientific devices.\nAlso usable as a very weak\ngun with infinite ammo.'))
        return entity

    def _create_spikebox(self, entity_id, owning_entity=None, **kwargs):
        entity = Entity(entity_id)
        widget = SwitchingWidget(images_dict={
                    'r': self.atlas.get_element('spikebox_r'),
                    'l': self.atlas.get_element('spikebox_l')},
                                 initial_image='r')
        entity.add_component(SwitchWidgetComponent(self.dispatcher, widget))
        entity.add_component(CollectableBehaviourComponent(self.dispatcher))
        entity.add_component(HidingComponent(self.dispatcher,
                                             hide_condition='timeout',
                                             lifetime=0.25,
                                             is_working=False,
                                             should_hide=False))
        entity.add_component(PositionComponent(self.dispatcher, affect_z=False))
        entity.add_component(SpawnerComponent(self.dispatcher, factory=self))
        entity.add_component(SpawningItemBehaviourComponent(self.dispatcher,
                                                            owning_entity=owning_entity,
                                                            spawned_items={'spike': {'r': (0, -5),
                                                                                     'l': (0, 0)}},
                                                            use_delay=0.5,
                                                            single_use=True,
                                                            item_name='Disassembled spike',
                                                            item_description='A spike. Could be installed\nas a fortification (you\nneed at least two spikes to\ncreate a spark wall) or\nto power nearby machines.'))
        entity.add_component(DestructorComponent(self.dispatcher))
        return entity

#TODO: general character creation method
