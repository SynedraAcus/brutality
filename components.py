from collections import OrderedDict

from bear_hug.bear_utilities import BearECSException
from bear_hug.ecs import Component, PositionComponent, BearEvent, \
    WidgetComponent
from bear_hug.widgets import SwitchingWidget


class WalkerComponent(PositionComponent):
    """
    A simple PositionComponent that can change x;y on keypress
    """
    
    # TODO: Non-idiotic walking animation
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dispatcher.register_listener(self, ['key_down', 'tick'])
        self.last_move = None
        self.direction = 'r'
        self.phase = '1'
        self.moved_this_tick = False
        
    def walk(self, move):
        if self.moved_this_tick:
            return
        self.relative_move(*move)
        self.last_move = move
        self.moved_this_tick = True
        if move[0] > 0:
            self.direction = 'r'
        elif move[0] < 0:
            self.direction = 'l'
        # If move[0] == 0, the direction stays whatever it was, move is vertical
        # TODO: Support more than two phases of movement
        if self.phase == '1':
            self.phase = '2'
        else:
            self.phase = '1'
        self.owner.widget.switch_to_image(f'{self.direction}_{self.phase}')
    
    def on_event(self, event):
        if event.event_type == 'tick':
            self.moved_this_tick = False


class CollisionComponent(Component):
    """
    A component responsible for processing collisions of this object
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, name='collision', **kwargs)
        self.dispatcher.register_listener(self, 'ecs_collision')

    def on_event(self, event):
        if event.event_type == 'ecs_collision':
            if event.event_value[0] == self.owner.id:
                self.collided_into(event.event_value[1])
            elif event.event_value[1] == self.owner.id:
                self.collided_by(event.event_value[0])

    def collided_into(self, entity):
        print(f'Collided into {entity}')

    def collided_by(self, entity):
        print(f'Collided by {entity}')


class WalkerCollisionComponent(CollisionComponent):
    """
    A collision component that, upon colliding into something impassable,
    moves the entity to where it came from.
    """
    def collided_into(self, entity):
        self.owner.position.relative_move(self.owner.position.last_move[0] * -1,
                                          self.owner.position.last_move[1] * -1)


class ProjectileCollisionComponent(CollisionComponent):
    """
    A collision component that damages whatever its owner is collided into
    """
    def collided_into(self, entity):
        self.dispatcher.add_event(BearEvent(event_type='brut_damage',
                                            event_value=(entity, 1)))
        self.owner.destructor.destroy()
        

class HealthComponent(Component):
    """
    A component that monitors owner's health and updates whatever needs updating
    """
    def __init__(self, *args, hitpoints=3, **kwargs):
        super().__init__(*args, name='health', **kwargs)
        self.dispatcher.register_listener(self, 'brut_damage')
        self._hitpoints = hitpoints

    def on_event(self, event):
        if event.event_type == 'brut_damage' and event.event_value[0] == self.owner.id:
            self.hitpoints -= event.event_value[1]
        elif event.event_type == 'brut_damage' and event.event_value[0] == self.owner.id:
            self.hitpoints += event.event_value[1]

    @property
    def hitpoints(self):
        return self._hitpoints
    
    @hitpoints.setter
    def hitpoints(self, value):
        if not isinstance(value, int):
            raise BearECSException(f'Attempting to set hitpoints of {self.owner.id} to non-integer {value}')
        self._hitpoints = value
        if self._hitpoints < 0:
            self._hitpoints = 0
        self.process_hitpoint_update()
        
    def process_hitpoint_update(self):
        """
        :return:
        """
        pass


class VisualDamageHealthComponent(HealthComponent):
    """
    A health component for non-active objects.
    Tells the owner's widget to switch image upon reaching certain amounts of HP
    This should be in `widgets_dict` parameter to __init__ which is a dict from
    int HP to image ID. A corresponding image is shown while HP is not less than
    a dict key, but less than the next one (in increasing order).
    If HP reaches zero and object has a Destructor component, it is destroyed
    """
    def __init__(self, *args, widgets_dict={}, **kwargs):
        super().__init__(*args, **kwargs)
        self.widgets_dict = OrderedDict()
        for x in sorted(widgets_dict.keys()):
            self.widgets_dict[x] = widgets_dict[x]
        
    def process_hitpoint_update(self):
        if self.hitpoints == 0 and hasattr(self.owner, 'destructor'):
            self.owner.destructor.destroy()
        for x in self.widgets_dict:
            if self.hitpoints >= x:
                self.owner.widget.switch_to_image(self.widgets_dict[x])
    
    
class SwitchWidgetComponent(WidgetComponent):
    """
    A widget component that supports SwitchingWidget
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not isinstance(self.widget, SwitchingWidget):
            raise BearECSException('SwitchWidgetComponent can only be used with SwitchingWidget')
        
    def switch_to_image(self, image_id):
        self.widget.switch_to_image(image_id)
        
    def validate_image(self, image_id):
        """
        Return True if image_id is a valid ID for its widget
        :param image_id:
        :return:
        """
        return image_id in self.widget.images


class SpawnerComponent(Component):
    """
    A component responsible for spawning stuff near its owner
    For projectiles and other such things
    """
    def __init__(self, *args, factory=None, **kwargs):
        super().__init__(*args, name='spawner', **kwargs)
        self.factory = factory
        self.dispatcher.register_listener(self, 'key_down')

    def spawn(self, item, relative_pos, **kwargs):
        """
        Spawn item at self.pos+self.relative_pos
        :param item:
        :param relative_pos:
        :return:
        """
        self.factory.create_entity(item, (self.owner.position.x + relative_pos[0],
                                          self.owner.position.y + relative_pos[1]),
                                   **kwargs)
        

class InputComponent(Component):
    """
    A component that handles input.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, name='controller', **kwargs)
        self.dispatcher.register_listener(self, 'key_down')
        
    def on_event(self, event):
        #TODO: Support non-hardcoded actions and keys
        x = super().on_event(event)
        if isinstance(x, BearEvent):
            r = [x]
        elif isinstance(x, list):
            r = x
        else:
            r = []
        if event.event_type == 'key_down':
            moved = False
            if event.event_value == 'TK_SPACE':
                if self.owner.position.direction == 'r':
                    self.owner.spawner.spawn('bullet', (13, 4),
                                             direction=self.owner.position.direction,
                                             speed=(70, 0))
                else:
                    self.owner.spawner.spawn('bullet', (-1, 5),
                                             direction=self.owner.position.direction,
                                             speed=(-70, 0))
                r.append(BearEvent(event_type='play_sound',
                                   event_value='shot'))
                r.append(BearEvent(event_type='brut_temporary_focus',
                                   event_value=f"bullet_{self.owner.spawner.factory.counts['bullet']}"))
            elif event.event_value in ('TK_D', 'TK_RIGHT'):
                self.last_move = (2, 0)
                moved = True
            elif event.event_value in ('TK_A', 'TK_LEFT'):
                self.last_move = (-2, 0)
                moved = True
            elif event.event_value in ('TK_S', 'TK_DOWN'):
                self.last_move = (0, 2)
                moved = True
            elif event.event_value in ('TK_W', 'TK_UP'):
                self.last_move = (0, -2)
                moved = True
            elif event.event_value == 'TK_KP_6':
                r.append(BearEvent(event_type='ecs_scroll_by',
                                   event_value=(1, 0)))
            elif event.event_value == 'TK_KP_4':
                r.append(BearEvent(event_type='ecs_scroll_by',
                                   event_value=(-1, 0)))
            elif event.event_value == 'TK_KP_8':
                r.append(BearEvent(event_type='ecs_scroll_by',
                                   event_value=(0, -1)))
            elif event.event_value == 'TK_KP_2':
                r.append(BearEvent(event_type='ecs_scroll_by',
                                   event_value=(0, 1)))
            elif event.event_value == 'TK_KP_5':
                r.append(BearEvent(event_type='ecs_scroll_to',
                                   event_value=(0, 0)))
            if moved:
                self.owner.position.walk(self.last_move)
                r.append(BearEvent(event_type='play_sound',
                                   event_value='step'))
        return r
