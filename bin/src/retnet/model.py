from keras_retinanet import models
import cv2
from keras_retinanet.utils.image import preprocess_image, resize_image
import time
import numpy as np
from src.myutilities.image import Image
import src.myutilities.io as io
from abc import ABC, abstractmethod
import os
import skimage
from skimage import morphology

class Model(ABC):

    def __init__(self, model_path: str, confidence_cutoff=0.5):
        self.model_path = model_path
        print("Loading MODEL: {}".format(model_path))
        self.model = models.load_model(model_path, backbone_name="resnet50")
        self._confidence_cutoff = confidence_cutoff
        model_name = os.path.normpath(model_path)
        self.model_name = os.path.split(model_name)[1]


    @abstractmethod
    def detect(self, **args):
        return NotImplementedError

    @property
    def confidence_cutoff(self):
        return self._confidence_cutoff

    @confidence_cutoff.setter
    def confidence_cutoff(self, new_value):
        if 0 < new_value < 1 and isinstance(new_value, float):
            self._confidence_cutoff = new_value
        else:
            raise ValueError("Set confidence to float between 0 and 1")


#     @abstractmethod
#     def preprocessing(self, **args):
#         pass
#         # TODO add NotImplementedError once all models have been updated

    @staticmethod
    def blur(image):
        print("blur")
        return cv2.GaussianBlur(image, (9, 9), 0)



    @staticmethod
    def canny(image):
        print("canny")
        m = np.mean(image)
        lower = max(0, m * .5)
        upper = min(255, m * 1.5)
        edges = cv2.Canny(image, lower, upper)
        edges = cv2.merge((edges, edges, edges))
        return edges

    @staticmethod
    def resize(image):
        print("resize")
        return cv2.resize(image, dsize=(600, 600), interpolation=cv2.INTER_CUBIC)

    @staticmethod
    def denoise(image):
        # FutureWarning from skimage
        # Test for retinanet_testing
        grayscale = skimage.color.rgb2gray(image)
        # print(grayscale)
        binarized = np.where(grayscale > np.mean(grayscale), 1, 0)
        processed = morphology.remove_small_objects(binarized.astype(bool), min_size=100, connectivity=1).astype(int)
        # print(processed)
        # black out pixels
        mask_x, mask_y = np.where(processed == 0)
        image[mask_x, mask_y] = 0
        return image


class QrModel(Model):

    def detect(self, image_path: str=None, image_output_path=None, image_arr: np.ndarray=None):

        # confidence_cutoff = 0.5
        width = [1000 / 4000, 3000 / 4000]  # proportion of cropped width

        if image_arr is not None:
            mi = Image(image_arr)
        else:
            mi = Image(cv2.imread(image_path))
        mi.set_crop(int(width[0] * np.shape(mi.image)[1]), int(width[1] * np.shape(mi.image)[1]), 0, np.shape(mi.image)[0])

        image = preprocess_image(mi.crop)
        image, scale = resize_image(image)

        start = time.time()
        boxes, scores, labels = self.model.predict_on_batch(np.expand_dims(image, axis=0))
        print("QR RETINANET processing time: ", time.time() - start)

        boxes /= scale

        top = np.argmax(scores[0])
        box = boxes[0][top]
        score = scores[0][top]

        if score >= self._confidence_cutoff:
            print("QR code has been found!")

            if image_output_path is not None:
                color = (255, 0, 0)
                thickness = 2
                draw = mi.crop.copy()
                cv2.rectangle(draw, (box[0], box[1]), (box[2], box[3]), color, thickness, cv2.LINE_AA)
                io.save_image_from_array(draw, image_output_path + "/qrbox.png")

            mi.transform_crop_coords(int(box[0]), int(box[2]), int(box[1]), int(box[3]))
            return mi
        else:
            print("QR Confidence value not met!")
            return None

class SeedModel(Model):

    def detect(self, image_path: str=None, image_output_path=None, image_arr:np.ndarray=None, sort:bool=False):

        if image_arr is not None:
            mi = Image(image_arr)
        else:
            mi = Image(cv2.imread(image_path))

        # TODO change width to zero
        height = [500 / 3000, 2000 / 3000]  # proportion of cropped height
        width = [1 / 6, 5 / 6]  # proportion of cropped width
        height = [0, 1]
        width = [0, 1]

        mi.set_crop(int(width[0] * np.shape(mi.image)[1]),
                    int(width[1] * np.shape(mi.image)[1]),
                    int(height[0] * np.shape(mi.image)[0]),
                    int(height[1] * np.shape(mi.image)[0]))

        # create copy to draw on
        draw = mi.image.copy()

        # load label to names mapping for visualization purposes
        label_dictionary = {0: 'seed'}

        image = preprocess_image(mi.crop)
        image, scale = resize_image(image)

        start = time.time()

        # expects image array with 4 dimensions, so we must add one more dimension.
        boxes, scores, labels = self.model.predict_on_batch(np.expand_dims(image, axis=0))
        print("SEED RETINANET processing time: ", time.time() - start)

        # correct for image scale
        # equivalent to boxes = boxes/scale
        boxes /= scale

        seed_images = []
        scores_list = []

        for box, score, label in zip(boxes[0], scores[0], labels[0]):
            # score values are sorted
            if score < self._confidence_cutoff:
                break

            # round box coords to integers
            b = box.astype(int)

            coords = mi.get_transform_crop_coords(b[0], b[2], b[1], b[3])

            mi1 = Image(mi.image)
            mi1.set_crop(coords.x1, coords.x2, coords.y1, coords.y2)
            
            #keep list of all seeds as well as their associated score
            seed_images.append(mi1)
            scores_list.append(score)


            if image_output_path is not None:
                # Add boxes and captions
                color = (255, 0, 0)
                thickness = 2
                cv2.rectangle(draw, (coords.x1, coords.y1), (coords.x2, coords.y2), color, thickness, cv2.LINE_AA)
                caption = "{} {:.3f}".format(label_dictionary[label], score)

                # black outline with red text
                cv2.putText(draw, caption, (coords.x1, coords.y1 - 10), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 0, 0), 2)
                cv2.putText(draw, caption, (coords.x1, coords.y1 - 10), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 0, 0), 1)

        if image_output_path is not None:
            image_output_path = image_output_path + "/seed.png"
            io.save_image_from_array(draw, image_output_path)
            print("processing time: " + image_output_path)

        if sort:
            seed_images.sort(key=lambda i:i.x1)

        return seed_images, scores_list

    def preprocessing(self, **args):
        pass
