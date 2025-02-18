import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.python.util import nest

from autokeras.hypermodel import base


class TextNode(base.Node):
    pass


class Input(base.Node):
    """Input node for tensor data.

    The data should be numpy.ndarray or tf.data.Dataset.
    """

    def fit(self, y):
        """Record any information needed by transform."""
        pass

    def transform(self, x):
        """Transform x into a compatible type (tf.data.Dataset)."""
        if isinstance(x, tf.data.Dataset):
            return x
        if isinstance(x, np.ndarray):
            if x.dtype == np.float64:
                x = x.astype(np.float32)
            return tf.data.Dataset.from_tensor_slices(x)
        raise TypeError('Unsupported type {type} for '
                        '{name}.'.format(type=type(x),
                                         name=self.__class__.__name__))


class ImageInput(Input):
    """Input node for image data.

    The input data should be numpy.ndarray or tf.data.Dataset. The shape of the data
    should be 3 or 4 dimensional, the last dimension of which should be channel
    dimension.
    """

    def transform(self, x):
        if isinstance(x, np.ndarray):
            if x.ndim == 3:
                x = np.expand_dims(x, axis=3)
        if x.ndim != 4:
            raise ValueError('Expect image input to have 2 or 3 dimensions (not '
                             'including batch dimension), but got input shape '
                             '{shape} with {ndim} dimensions'.format(shape=x.shape,
                                                                     ndim=x.ndim))
        return super().transform(x)


class TextInput(Input, TextNode):
    """Input node for text data.

    The input data should be numpy.ndarray or tf.data.Dataset. The data should be one
    dimensional. Each element in the data should be a string which is a full
    sentence.
    """
    pass


class StructuredDataInput(Input):
    """Input node for structured data.

    The input data should be numpy.ndarray, pandas.DataFrame or tensorflow.Dataset.

    # Arguments
        column_names: A list of strings specifying the names of the columns. The
            length of the list should be equal to the number of columns of the data.
            Defaults to None. If None, it will obtained from the header of the csv
            file or the pandas.DataFrame.
        column_types: Dict. The keys are the column names. The values should either
            be 'numerical' or 'categorical', indicating the type of that column.
            Defaults to None. If not None, the column_names need to be specified.
            If None, it will be inferred from the data. A column will be judged as
            categorical if the number of different values is less than 5% of the
            number of instances.
    """

    def __init__(self, column_names=None, column_types=None, **kwargs):
        super().__init__(**kwargs)
        self.column_names = column_names
        self.column_types = column_types
        # Variables for inferring column types.
        self.count_nan = None
        self.count_numerical = None
        self.count_categorical = None
        self.count_unique_numerical = []
        self.num_col = None

    def fit(self, x):
        if not isinstance(x, (pd.DataFrame, np.ndarray)):
            raise TypeError('Unsupported type {type} for '
                            '{name}.'.format(type=type(x),
                                             name=self.__class__.__name__))

        # Extract column_names from pd.DataFrame.
        if isinstance(x, pd.DataFrame) and self.column_names is None:
            self.column_names = list(x.columns)
            # column_types is provided by user
            if self.column_types:
                for column_name in self.column_types:
                    if column_name not in self.column_names:
                        raise ValueError('Column_names and column_types are '
                                         'mismatched. Cannot find column name '
                                         '{name} in the data.'.format(
                                             name=column_name))

        # Generate column_names.
        if self.column_names is None:
            if self.column_types:
                raise ValueError('Column names must be specified.')
            self.column_names = [index for index in range(x.shape[1])]

        # Check if column_names has the correct length.
        if len(self.column_names) != x.shape[1]:
            raise ValueError('Expect column_names to have length {expect} '
                             'but got {actual}.'.format(
                                 expect=x.shape[1],
                                 actual=len(self.column_names)))

    def transform(self, x):
        if isinstance(x, pd.DataFrame):
            # Convert x, y, validation_data to tf.Dataset.
            x = tf.data.Dataset.from_tensor_slices(
                x.values.astype(np.unicode))
        if isinstance(x, np.ndarray):
            x = tf.data.Dataset.from_tensor_slices(x.astype(np.unicode))
        dataset = super().transform(x)
        for x in dataset:
            self.update(x)
        self.infer_column_types()
        return dataset

    def update(self, x):
        # Calculate the statistics.
        x = nest.flatten(x)[0].numpy()
        if self.num_col is None:
            self.num_col = len(x)
            self.count_nan = np.zeros(self.num_col)
            self.count_numerical = np.zeros(self.num_col)
            self.count_categorical = np.zeros(self.num_col)
            for i in range(len(x)):
                self.count_unique_numerical.append({})
        for i in range(self.num_col):
            x[i] = x[i].decode('utf-8')
            if x[i] == 'nan':
                self.count_nan[i] += 1
            elif x[i] == 'True':
                self.count_categorical[i] += 1
            elif x[i] == 'False':
                self.count_categorical[i] += 1
            else:
                try:
                    tmp_num = float(x[i])
                    self.count_numerical[i] += 1
                    if tmp_num not in self.count_unique_numerical[i]:
                        self.count_unique_numerical[i][tmp_num] = 1
                    else:
                        self.count_unique_numerical[i][tmp_num] += 1
                except ValueError:
                    self.count_categorical[i] += 1

    def infer_column_types(self):
        column_types = {}
        for i in range(self.num_col):
            if self.count_categorical[i] > 0:
                column_types[self.column_names[i]] = 'categorical'
            elif len(self.count_unique_numerical[i])/self.count_numerical[i] < 0.05:
                column_types[self.column_names[i]] = 'categorical'
            else:
                column_types[self.column_names[i]] = 'numerical'
        # Partial column_types is provided.
        if self.column_types is None:
            self.column_types = {}
        for key, value in column_types.items():
            if key not in self.column_types:
                self.column_types[key] = value


class TimeSeriesInput(Input):
    pass
