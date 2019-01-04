from bear_hug.ecs import Component, PositionComponent, BearEvent


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
        print('Collided into {}'.format(entity))
    
    def collided_by(self, entity):
        print('Collided by {}'.format(entity))


class WalkerComponent(PositionComponent):
    """
    A simple PositionComponent that can change x;y on keypress
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dispatcher.register_listener(self, ['key_down'])
        self.last_move = None
    
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
                self.relative_move(*self.last_move)
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
