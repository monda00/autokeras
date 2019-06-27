import tensorflow as tf
from autokeras.hypermodel import hyper_block


class Node(object):
    def __init__(self, shape=None):
        super().__init__()
        self.in_hypermodels = []
        self.out_hypermodels = []
        self.shape = shape

    def add_in_hypermodel(self, hypermodel):
        self.in_hypermodels.append(hypermodel)

    def add_out_hypermodel(self, hypermodel):
        self.out_hypermodels.append(hypermodel)

    def build(self, hp):
        raise NotImplementedError


class Input(Node):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def build(self, hp):
        return tf.keras.Input(shape=self.shape)

    def related_block(self):
        return hyper_block.ResNetBlock()


class ImageInput(Input):

    def related_block(self):
        return hyper_block.ImageBlock()


class TextInput(Input):

    def related_block(self):
        return hyper_block.TextBlock()


class StructuredInput(Input):

    def related_block(self):
        return hyper_block.StructuredBlock()


class TimeSeriesInput(Input):

    def related_block(self):
        return hyper_block.TimeSeriesBlock()
