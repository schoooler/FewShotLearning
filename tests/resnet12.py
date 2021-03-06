import unittest

import numpy as np
from tensorflow.keras import models
from tensorflow.keras import backend as K

from fewshot.backbones.resnet12 import Resnet12, ResidualBlock


class TestResnet12(unittest.TestCase):

    def test_forward(self):
        net = Resnet12((256, 256, 3), 'relu')
        model = net.build_model()

        input = np.random.random((2, 256, 256, 3)).astype(np.float32)
        self.assertEqual((2, 16, 16, 512), model(input).shape)

    def test_fit(self):
        net = Resnet12((256, 256, 3))
        model = net.build_model()
        model.compile(loss='mean_squared_error', optimizer='sgd')

        input = np.random.random((2, 256, 256, 3)).astype(np.float32)
        target = np.random.random((2, 16, 16, 512)).astype(np.float32)

        convs = [net.residual1.conv1.conv, net.residual1.conv2.conv, net.residual1.conv3.conv,
                 net.residual2.conv1.conv, net.residual2.conv2.conv, net.residual2.conv3.conv,
                 net.residual3.conv1.conv, net.residual3.conv2.conv, net.residual3.conv3.conv,
                 net.residual4.conv1.conv, net.residual4.conv2.conv, net.residual4.conv3.conv]

        conv_weights = self.get_conv_weights(convs)
        model.fit(input, target)
        new_conv_weights = self.get_conv_weights(convs)

        for source, target in zip(conv_weights, new_conv_weights):
            self.assertFalse(np.allclose(source, target))

    def test_freeze(self):
        net = Resnet12((256, 256, 3))
        model = net.build_model()
        net.set_trainable(False)
        model.compile(loss='mean_squared_error', optimizer='sgd')

        input = np.random.random((2, 256, 256, 3)).astype(np.float32)
        target = np.random.random((2, 16, 16, 512)).astype(np.float32)

        convs = [net.residual1.conv1.conv, net.residual1.conv2.conv, net.residual1.conv3.conv,
                 net.residual2.conv1.conv, net.residual2.conv2.conv, net.residual2.conv3.conv,
                 net.residual3.conv1.conv, net.residual3.conv2.conv, net.residual3.conv3.conv,
                 net.residual4.conv1.conv, net.residual4.conv2.conv, net.residual4.conv3.conv]

        conv_weights = self.get_conv_weights(convs)
        model.fit(input, target)
        new_conv_weights = self.get_conv_weights(convs)

        for source, target in zip(conv_weights, new_conv_weights):
            self.assertTrue(np.allclose(source, target))

    def test_compute_residual_block_output_shape(self):
        conv = ResidualBlock(512)
        actual = conv.compute_output_shape((2, 256, 256, 3))
        self.assertTrue((2, 256, 256, 512), actual)

    def get_conv_weights(self, convs):
        r = []
        for conv in convs:
            r.append(K.eval(conv.weights[0]))
        return r
