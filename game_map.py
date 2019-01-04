from bear_hug.ecs import Component
from bear_hug.ecs_widgets import ECSLayout
from bear_hug.widgets import Widget

#  Game map stores *data* about the cells. Objects are expected to do their
# drawing themselves, probably by emitting appropriate events


class MapCell:
    """
    A single cell for the map
    """
    def __init__(self, background, object):
        self._background = None
        self._object = None
        if background:
            self.background = background
        if object:
            self.object = object
    
    @property
    def background(self):
        return self._background
    
    @background.setter
    def background(self, background):
        if not isinstance(background, Widget):
            raise MapException('A MapCell background should be a widget')
        self._background = background
        
    @property
    def object(self):
        return self._object
    
    @object.setter
    def object(self, map_object):
        if not isinstance(map_object, MapObject):
            raise MapException('A MapCell object should be a MapObject')
        self._object = map_object
    
    
class Map:
    """
    A container for cells.
    Currently just a fancy list, but it's expected to be extended
    """
    def __init__(self, width=10, height=5):
        self.cells = [[MapCell() for x in width] for y in height]
        
    def __getitem__(self, item):
        return self.cells[item]
    
    
class MapException(Exception):
    """
    An exception for stuff related to maps
    """
    pass
