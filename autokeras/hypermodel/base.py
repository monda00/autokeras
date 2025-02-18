import types

import kerastuner
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.python.util import nest

from autokeras import utils


class Node(object):
    """The nodes in a network connecting the blocks."""
    # TODO: Implement get_config() and set_config(), so that the entire graph can
    # be saved.

    def __init__(self, shape=None):
        super().__init__()
        self.in_blocks = []
        self.out_blocks = []
        self.shape = shape

    def add_in_block(self, hypermodel):
        self.in_blocks.append(hypermodel)

    def add_out_block(self, hypermodel):
        self.out_blocks.append(hypermodel)

    def build(self):
        return tf.keras.Input(shape=self.shape)

    def clear_edges(self):
        self.in_blocks = []
        self.out_blocks = []


class Block(kerastuner.HyperModel):
    """The base class for different Block.

    The Block can be connected together to build the search space
    for an AutoModel. Notably, many args in the __init__ function are defaults to
    be a tunable variable when not specified by the user.

    # Arguments
        name: String. The name of the block. If unspecified, it will be set
        automatically with the class name.
    """

    def __init__(self, name=None, **kwargs):
        super().__init__(**kwargs)
        if not name:
            prefix = self.__class__.__name__
            name = prefix + '_' + str(tf.keras.backend.get_uid(prefix))
            name = utils.to_snake_case(name)
        self.name = name
        self.inputs = None
        self.outputs = None
        self._num_output_node = 1

    def __new__(cls, *args, **kwargs):
        obj = super().__new__(cls)
        build_fn = obj.build

        def build_wrapper(obj, hp, *args, **kwargs):
            with hp.name_scope(obj.name):
                return build_fn(hp, *args, **kwargs)

        obj.build = types.MethodType(build_wrapper, obj)
        return obj

    def __call__(self, inputs):
        """Functional API.

        # Arguments
            inputs: A list of input node(s) or a single input node for the block.

        # Returns
            list: A list of output node(s) of the Block.
        """
        self.inputs = nest.flatten(inputs)
        for input_node in self.inputs:
            if not isinstance(input_node, Node):
                raise TypeError('Expect the inputs to layer {name} to be '
                                'a Node, but got {type}.'.format(
                                    name=self.name,
                                    type=type(input_node)))
            input_node.add_out_block(self)
        self.outputs = []
        for _ in range(self._num_output_node):
            output_node = Node()
            output_node.add_in_block(self)
            self.outputs.append(output_node)
        return self.outputs

    def build(self, hp, inputs=None):
        """Build the Block into a real Keras Model.

        The subclasses should override this function and return the output node.

        # Arguments
            hp: Hyperparameters. The hyperparameters for building the model.
            inputs: A list of input node(s).
        """
        return super().build(hp)

    def clear_nodes(self):
        """Delete the connecting edges to the nodes."""
        self.inputs = None
        self.outputs = None

    def get_config(self):
        """Get the configuration of the preprocessor.

        # Returns
            A dictionary of configurations of the preprocessor.
        """
        return {'name': self.name}

    def set_config(self, config):
        """Set the configuration of the preprocessor.

        # Arguments
            config: A dictionary of the configurations of the preprocessor.
        """
        self.name = config['name']


class Head(Block):
    """Base class for the heads, e.g. classification, regression.

    # Arguments
        loss: A Keras loss function. Defaults to None. If None, the loss will be
            inferred from the AutoModel.
        metrics: A list of Keras metrics. Defaults to None. If None, the metrics will
            be inferred from the AutoModel.
        output_shape: Tuple of int(s). Defaults to None. If None, the output shape
            will be inferred from the AutoModel.
    """

    def __init__(self, loss=None, metrics=None, output_shape=None, **kwargs):
        super().__init__(**kwargs)
        self.output_shape = output_shape
        self.loss = loss
        self.metrics = metrics
        # Mark if the head should directly output the input tensor.
        self.identity = False

    def get_config(self):
        config = super().get_config()
        config.update({
            'output_shape': self.output_shape,
            'loss': self.loss,
            'metrics': self.metrics,
            'identity': self.identity
        })
        return config

    def set_config(self, config):
        super().set_config(config)
        self.output_shape = config['output_shape']
        self.loss = config['loss']
        self.metrics = config['metrics']
        self.identity = config['identity']

    def build(self, hp, inputs=None):
        raise NotImplementedError

    def check_data_type(self, y):
        supported_types = (tf.data.Dataset, np.ndarray, pd.DataFrame, pd.Series)
        if not isinstance(y, supported_types):
            raise TypeError('Expect the target data of {name} to be tf.data.Dataset,'
                            ' np.ndarray, pd.DataFrame or pd.Series, but got {type}.'
                            .format(name=self.name, type=type(y)))

    def fit(self, y):
        """Record any information needed by transform."""
        self.check_data_type(y)

    def transform(self, y):
        """Transform y into a compatible type (tf.data.Dataset)."""
        self.check_data_type(y)
        if isinstance(y, tf.data.Dataset):
            return y
        if isinstance(y, np.ndarray):
            if len(y.shape) == 1:
                y = y.reshape(-1, 1)
            return tf.data.Dataset.from_tensor_slices(y)
        if isinstance(y, pd.DataFrame):
            return tf.data.Dataset.from_tensor_slices(y.values)
        if isinstance(y, pd.Series):
            return tf.data.Dataset.from_tensor_slices(y.values.reshape(-1, 1))

    def postprocess(self, y):
        """Postprocess the output of the Keras Model."""
        return y


class HyperBlock(Block):
    """HyperBlock uses hyperparameters to decide inner Block graph.

    A HyperBlock should be build into connected Blocks instead of individual Keras
    layers. The main purpose of creating the HyperBlock class is for the ease of
    parsing the graph for preprocessors. The graph would be hard to parse if a Block,
    whose inner structure is decided by hyperparameters dynamically, contains both
    preprocessors and Keras layers.

    When the preprocessing layers of Keras are ready to cover all the preprocessors
    in AutoKeras, the preprocessors should be handled by the Keras Model. The
    HyperBlock class should be removed. The subclasses should extend Block class
    directly and the build function should build connected Keras layers instead of
    Blocks.

    # Arguments
        output_shape: Tuple of int(s). Defaults to None. If None, the output shape
            will be inferred from the AutoModel.
        name: String. The name of the block. If unspecified, it will be set
            automatically with the class name.
    """

    def __init__(self, output_shape=None, **kwargs):
        super().__init__(**kwargs)
        self.output_shape = output_shape

    def build(self, hp, inputs=None):
        """Build the HyperModel instead of Keras Model.

        # Arguments
            hp: Hyperparameters. The hyperparameters for building the model.
            inputs: A list of instances of Node.

        # Returns
            An Node instance, the output node of the output Block.
        """
        raise NotImplementedError


class Preprocessor(Block):
    """Hyper preprocessing block base class."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hp = None

    def build(self, hp, inputs=None):
        """Build into part of a Keras Model.

        Since they are for preprocess data before feeding into the Keras Model,
        they are not part of the Keras Model. They only pass the inputs
        directly to outputs.
        """
        return inputs

    def set_hp(self, hp):
        """Set Hyperparameters for the Preprocessor.

        Since the `update` and `transform` function are all for single training
        instances instead of the entire dataset, the Hyperparameters needs to be
        set in advance of call them.

        # Arguments
            hp: Hyperparameters. The hyperparameters for tuning the preprocessor.
        """
        self._hp = hp

    def update(self, x, y=None):
        """Incrementally fit the preprocessor with a single training instance.

        # Arguments
            x: EagerTensor. A single instance in the training dataset.
            y: EagerTensor. The targets of the tasks. Defaults to None.
        """
        raise NotImplementedError

    def transform(self, x, fit=False):
        """Incrementally fit the preprocessor with a single training instance.

        # Arguments
            x: EagerTensor. A single instance in the training dataset.
            fit: Boolean. Whether it is in fit mode.

        Returns:
            A transformed instanced which can be converted to a tf.Tensor.
        """
        raise NotImplementedError

    def output_types(self):
        """The output types of the transformed data, e.g. tf.int64.

        The output types are required by tf.py_function, which is used for transform
        the dataset into a new one with a map function.

        # Returns
            A tuple of data types.
        """
        raise NotImplementedError

    @property
    def output_shape(self):
        """The output shape of the transformed data.

        The output shape is needed to build the Keras Model from the AutoModel.
        The output shape of the preprocessor is the input shape of the Keras Model.

        # Returns
            A tuple of int(s) or a TensorShape.
        """
        raise NotImplementedError

    def finalize(self):
        """Training process of the preprocessor after update with all instances."""
        pass

    def clear_weights(self):
        """Delete the trained weights of the preprocessor."""
        pass

    def get_weights(self):
        """Get the trained weights of the preprocessor.

        # Returns
            A dictionary of trained weights of the preprocessor.
        """
        return {}

    def set_weights(self, weights):
        """Set the trained weights of the preprocessor.

        # Arguments
            weights: A dictionary of trained weights of the preprocessor.
        """
        pass
