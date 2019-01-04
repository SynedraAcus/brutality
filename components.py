from bear_hug.bear_utilities import BearECSException
from bear_hug.ecs import Component, PositionComponent, BearEvent, \
    WidgetComponent

from widgets import SwitchingWidget


class CollisionComponent(Component):
    """
    A component responsible for processing collisions of this object
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, name='collision', **kwargs)
        self.dispatcher.register_listener(self, 'ecs_collision')
    
    def on_event(self, event):
        print(event.event_type, event.event_value)
        if event.event_type == 'ecs_collision':
            if event.event_value[0] == self.owner.id:
                self.collided_into(event.event_value[1])
            elif event.event_value[1] == self.owner.id:
                self.collided_by(event.event_value[0])
    
    def collided_into(self, entity):
        print(f'Collided into {entity}')
    
    def collided_by(self, entity):
        print(f'Collided by {entity}')


class WalkerComponent(PositionComponent):
    """
    A simple PositionComponent that can change x;y on keypress
    """
    
    # TODO: Non-moronic working animation
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dispatcher.register_listener(self, ['key_down'])
        self.last_move = None
        self.direction = 'r'
        self.phase = '1'
        
    def walk(self, move):
        self.relative_move(*move)
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
        r = []
        if event.event_type == 'key_down':
            moved = False
            if event.event_value in ('TK_D', 'TK_RIGHT'):
                self.last_move = (1, 0)
                moved = True
            elif event.event_value in ('TK_A', 'TK_LEFT'):
                self.last_move = (-1, 0)
                moved = True
            elif event.event_value in ('TK_S', 'TK_DOWN'):
                self.last_move = (0, 1)
                moved = True
            elif event.event_value in ('TK_W', 'TK_UP'):
                self.last_move = (0, -1)
                moved = True
            if moved:
                # events
                self.walk(self.last_move)
                r.append(BearEvent(event_type='play_sound',
                                   event_value='step'))
        x = super().on_event(event)
        if x:
            if isinstance(x, BearEvent):
                r.append(x)
            else:
                # multiple return
                r += x
        return r


class WalkerCollisionComponent(CollisionComponent):
    """
    A collision component that, upon colliding into something impassable,
    moves the entity to where it came from.
    """
    def collided_into(self, entity):
        self.owner.position.relative_move(self.owner.position.last_move[0] * -1,
                                          self.owner.position.last_move[1] * -1)


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
