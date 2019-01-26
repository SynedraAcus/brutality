from bear_hug.bear_utilities import shapes_equal, copy_shape, BearException
from bear_hug.widgets import Widget


# TODO: Backport this to bear_hug lib
class SwitchingWidget(Widget):
    """
    A widget that can contain a collection of chars/colors pairs and switch
    them on command. These char/color pairs should all be the same shape.
    Does not do any transition animations.
    """
    def __init__(self, images_dict, initial_image=None):
        test_shape = None
        for image in images_dict:
            if not shapes_equal(images_dict[image][0], images_dict[image][1]):
                raise BearException(f'Chars and colors of different shape for image ID {image} in SwitchingWidget')
            if not test_shape:
                test_shape = (len(images_dict[image][0]),
                              len(images_dict[image][0][0]))
            elif len(images_dict[image][0]) != test_shape[0] or \
                len(images_dict[image][0][0]) != test_shape[1]:
                raise BearException(f'Image {image} in SwitchingWidget has incorrect size')
        if not initial_image:
            raise BearException('Initial image not set for SwitchingWidget')
        super().__init__(*images_dict[initial_image])
        self.images = images_dict
        self.current_image = initial_image
        
    def switch_to_image(self, image_id):
        if image_id != self.current_image:
            try:
                self.chars = self.images[image_id][0]
                self.colors = self.images[image_id][1]
                self.current_image = image_id
            except KeyError:
                raise BearException(f'Attempting to switch to incorrect image ID {image_id}')


class PatternGenerator:
    def __init__(self, atlas):
        self.atlas = atlas
    
    # TODO: maybe it's better to generate things in a functional-ish style?
    # The object is currently only holding the atlas reference which makes it
    # sorta redundant; on the other hand, the rest of code is purely OOP and it
    # would be spaghetti if this part alone was functional.
    def generate_tiled(self, pattern, size):
        """
        Generate a chars/colors pair, tiled with a given pattern.
        The pattern is always aligned up and left.
        :param pattern: either str or a tuple. If a tuple, should be chars
        and colors; if str, should be a valid ID in self.atlas.
        :return:
        """
        if isinstance(pattern, str):
            tile_chars, tile_colors = self.atlas.get_element(pattern)
        elif isinstance(pattern, tuple):
            tile_chars, tile_colors = pattern
            if not shapes_equal(tile_colors, tile_chars):
                raise BearException('Incorrect pattern')
        else:
            raise BearException('A pattern for PatternGenerator should be either str or tuple')
        chars = [[' ' for x in range(size[0])] for y in range(size[1])]
        colors = copy_shape(chars, 'white')
        tile_height = len(tile_chars)
        tile_width = len(tile_chars[0])
        for y in range(len(chars)):
            for x in range(len(chars[0])):
                chars[y][x] = tile_chars[y % tile_height][x % tile_width]
                colors[y][x] = tile_colors[y % tile_height][x % tile_width]
        return chars, colors

    @staticmethod
    def stack_boxes(*boxes, order='vertical'):
        """
        Stack several rectangular elements into a single (chars, colors) item.
        Expects all of them to be the same size along the direction orthogonal
        to that of stacking, ie vertically stacked elements should be equal in
        width and horizontally stacked ones should be equal in height.
        :param boxes: iterable, a collection of elements to stack
        :param order: str. Either 'vertical' or 'horizontal'
        :return:
        """
        for item in boxes[1:]:
            if not shapes_equal(item, boxes[0]):
                raise BearException('Incorrectly shaped item in stack_boxes')
        if order == 'vertical':
            height = sum(len(i[0]) for i in boxes)
            chars = []
            colors = []
            for item in boxes:
                # for y in range(len(item[0])):
                # if not shapes_equal(item[0], item[1]):
                #     raise BearException('Incorrectly shaped item')
                chars.extend(item[0])
                colors.extend(item[1])
                # for y in range(len(item)):
                #     for x in range(len(item[0])):
                #         chars[y + running_height][x] = item[y][x]
                #         colors[y+running_height][x] = item[y][x]
                # running_height += len(item)
        elif order == 'horizontal':
            width = sum(len(i[0][0][0]) for i in boxes)
            chars = []
            colors = []
            for y in range(len(boxes[0][0])):
                chars.append([])
                colors.append([])
                for item in boxes:
                    chars[y] += item[0][y]
                    colors[y] += item[1][y]
        else:
            raise BearException('Stacking order should be either vertical or horizontal')
        return chars, colors

            
            
            
