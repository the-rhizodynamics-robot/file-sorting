import numpy as np
from typing import NamedTuple

class Image:
    def __init__(self, image: np.ndarray,
                 crop=None, x1=None, x2=None, y1=None, y2=None):
        self.image = image
        self.crop = crop
        self.x1 = x1
        self.x2 = x2
        self.y1 = y1
        self.y2 = y2

    def transform_crop_coords(self, x1: int, x2: int, y1: int, y2: int):
        self.x2 = self.x1 + x2
        self.x1 = self.x1 + x1
        self.y2 = self.y1 + y2
        self.y1 = self.y1 + y1
        self.crop = self.image[self.y1:self.y2, self.x1:self.x2]

    def set_crop(self, x1: int, x2: int, y1: int, y2: int):
        self.x1 = x1
        self.x2 = x2
        self.y1 = y1
        self.y2 = y2
        self.crop = self.image[y1:y2, x1:x2]

    def get_transform_crop_coords(self, x1: int = 0, x2: int = 0, y1: int = 0, y2: int = 0):
        coords = NamedTuple("Coords", [("x1", int), ("x2", int), ("y1", int), ("y2", int)])
        return coords(self.x1 + x1, self.x1 + x2, self.y1 + y1, self.y1 + y2)



