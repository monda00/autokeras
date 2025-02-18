# -*- coding: utf-8 -*-
import pathlib
import shutil

import keras_autodoc

from autokeras import auto_model
from autokeras import task
from autokeras.hypermodel import block
from autokeras.hypermodel import head
from autokeras.hypermodel import hyperblock

EXCLUDE = {
    'Optimizer',
    'TFOptimizer',
    'Wrapper',
    'get_session',
    'set_session',
    'CallbackList',
    'serialize',
    'deserialize',
    'get',
    'set_image_dim_ordering',
    'normalize_data_format',
    'image_dim_ordering',
    'get_variable_shape',
    'Constraint'
}

# For each class to document, it is possible to:
# 1) Document only the class: [classA, classB, ...]
# 2) Document all its methods: [classA, (classB, '*')]
# 3) Choose which methods to document (methods listed as strings):
# [classA, (classB, ['method1', 'method2', ...]), ...]
# 4) Choose which methods to document (methods listed as qualified names):
# [classA, (classB, [module.classB.method1, module.classB.method2, ...]), ...]
PAGES = [
    {
        'page': 'auto_model.md',
        'classes': [
            (auto_model.AutoModel, [
                auto_model.AutoModel.fit,
                auto_model.AutoModel.predict,
            ]),
        ]
    },
    {
        'page': 'graph_auto_model.md',
        'classes': [
            (auto_model.GraphAutoModel, [
                auto_model.GraphAutoModel.fit,
                auto_model.GraphAutoModel.predict,
            ]),
        ]
    },
    {
        'page': 'block.md',
        'classes': [hyperblock.ImageBlock,
                    hyperblock.TextBlock,
                    hyperblock.StructuredDataBlock,
                    block.ResNetBlock,
                    block.XceptionBlock,
                    block.ConvBlock,
                    block.RNNBlock,
                    block.Merge],
    },
    {
        'page': 'task.md',
        'classes': [task.ImageClassifier,
                    task.ImageRegressor,
                    task.TextClassifier,
                    task.TextRegressor],
    },
    {
        'page': 'head.md',
        'classes': [head.ClassificationHead,
                    head.RegressionHead],
    }
]

ROOT = 'http://autokeras.com/'

autokeras_dir = pathlib.Path(__file__).resolve().parents[1]


def generate(dest_dir):
    template_dir = autokeras_dir / 'docs' / 'templates'
    keras_autodoc.generate(
        dest_dir,
        template_dir,
        PAGES,
        'https://github.com/keras-team/autokeras/blob/master',
        autokeras_dir / 'examples',
        EXCLUDE,
    )
    readme = (autokeras_dir / 'README.md').read_text()
    index = (template_dir / 'index.md').read_text()
    index = index.replace('{{autogenerated}}', readme[readme.find('##'):])
    (dest_dir / 'index.md').write_text(index, encoding='utf-8')
    shutil.copyfile(autokeras_dir / '.github' / 'CONTRIBUTING.md',
                    dest_dir / 'contributing.md')


if __name__ == '__main__':
    generate(autokeras_dir / 'docs' / 'sources')
