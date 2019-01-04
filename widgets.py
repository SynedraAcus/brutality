from bear_hug.bear_utilities import shapes_equal, BearException
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
        try:
            self.chars = self.images[image_id][0]
            self.colors = self.images[image_id][1]
        except KeyError:
            raise BearException(f'Attempting to switch to incorrect image ID {image_id}')
