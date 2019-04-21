import cv2
import numpy as np
import numbers
import random


class Augmentation:
    def __init__(self,
                 mode='train',
                 flip_prob=0,
                 center=None,
                 crop_size=None,
                 color_jitter_prob=0,
                 hue_range=(1, 1),
                 saturation_range=(1, 1),
                 value_range=(1, 1),
                 mixup_prob=0,
                 noisy_mixup_prob=0,
                 between_class_prob=0,
                 vertical_concat_prob=0,
                 horizontal_concat_prob=0,
                 mixed_concat_prob=0,
                 beta_distr_param=1,
                 num_images_in_mixup=1,
                 mixing_coeff=None):
        self.mode = mode
        self.flip_prob = flip_prob
        self.center = center
        self.crop_size = crop_size
        self.color_jitter_prob = color_jitter_prob
        self.hsv_ranges = (hue_range, saturation_range, value_range)
        self.mixup_prob = mixup_prob
        self.noisy_mixup_prob = noisy_mixup_prob
        self.between_class_prob = between_class_prob
        self.vertical_concat_prob = vertical_concat_prob
        self.horizontal_concat_prob = horizontal_concat_prob
        self.mixed_concat_prob = mixed_concat_prob
        self.beta_distr_param = beta_distr_param
        self.num_images_in_mixup = num_images_in_mixup
        self.mixing_coeff = mixing_coeff
        self.basic_transforms = [
                                 self.random_flip,
                                 self.random_color_jitter
                                ]
        self.mixed_transforms = [
                                 self.mixup, self.noisy_mixup,
                                 self.between_class, self.vertical_concat,
                                 self.horizontal_concat,
                                 self.mixed_concat
                                ]
        self.basic_probs = [
                            self.flip_prob,
                            self.color_jitter_prob
                           ]
        self.mixed_probs = [
                            self.mixup_prob, self.noisy_mixup_prob, self.between_class_prob,
                            self.vertical_concat_prob, self.horizontal_concat_prob,
                            self.mixed_concat_prob
                           ]
        self.mixup_stage = (sum(self.mixed_probs) > 0)
        if self.mixup_stage and self.num_images_in_mixup == 1:
            raise ValueError('Need more than 1 image to apply mix-ups')

        if not self.mixup_stage and self.num_images_in_mixup > 1:
            raise ValueError('Need precisely 1 image to apply basic augmentations')

        if self.num_images_in_mixup > 2:
            raise ValueError('''Need precisely 2 images to apply mix-ups;
                                other values are not currently supported''')

        if self.mode == 'test':
            self.center = True

        self.make_crop = self.crop_size is not None
        if isinstance(self.crop_size, numbers.Number):
            self.crop_size = (int(self.crop_size), int(self.crop_size))

    def get_crop_size(self):
        return self.crop_size

    def get_num_images_in_augmentation(self):
        return self.num_images_in_mixup

    def apply_random_basic_transform(self, images):
        for index, (transform, p) in enumerate(zip(self.basic_transforms,
                                                   self.basic_probs)):
            images = transform(images, p)
        return images

    def apply_random_mixed_transform(self, images, labels, mixing_coeff=None):
        f = np.random.choice(self.mixed_transforms, p=self.mixed_probs)
        if mixing_coeff is None:
            mixing_coeff = np.random.beta(self.beta_distr_param, self.beta_distr_param)
        return f(images, labels, mixing_coeff)

    def apply_random_transform(self, images, labels=None):
        assert all([images[index].dtype == np.uint8 for index in range(len(images))])
        # crop
        images = self.random_crop(images)
        # basic stage
        images = self.apply_random_basic_transform(images)
        # mixup stage
        if self.mixup_stage:
            labels = np.stack(labels).astype(np.float32)
            img, label = self.apply_random_mixed_transform(images, labels, self.mixing_coeff)
        else:
            img, label = images[0], labels[0]
        img = np.array(np.clip(img, 0, 255), dtype='uint8')
        return img, label

    def crop(self, img, x, y):
        return img[y:y + self.crop_size[0], x:x + self.crop_size[1]]

    def random_crop(self, images):
        if not self.make_crop:
            return images

        crops = np.zeros((len(images), self.crop_size[0], self.crop_size[1], 3))
        for index in range(len(images)):
            dw = images[index].shape[1] - self.crop_size[1]
            dh = images[index].shape[0] - self.crop_size[0]
            if min(dw, dh) < 0:
                raise ValueError('Bad crop size: should be not greater than ({}, {})'
                                 .format(images[index].shape[0], images[index].shape[1]))
            if dw and dh:
                x = dw // 2 if self.center else np.random.randint(dw)
                y = dh // 2 if self.center else np.random.randint(dh)
                crops[index] = self.crop(images[index], x, y)
            else:
                crops[index] = images[index]
        return crops

    def random_flip(self, images, p=0.5):
        images = [img if random.random() > p else cv2.flip(img, 0)
                  for img in images]
        return images

    def color_jitter(self, img, hsv_factors):
        hue, saturation, value = hsv_factors
        hsv_img = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        hsv_img = hsv_img.astype(dtype=np.float32)
        hsv_img[:, :, 0] *= hue
        hsv_img[:, :, 1] *= saturation
        hsv_img[:, :, 2] *= value
        hsv_img = np.clip(hsv_img, 0, 255).astype(dtype=np.uint8)
        return cv2.cvtColor(hsv_img, cv2.COLOR_HSV2RGB)

    def random_color_jitter(self, images, p=0.5):
        if random.random() > p:
            return images
        hue, saturation, value = self.hsv_ranges
        for index in range(len(images)):
            hue_factor = np.random.uniform(hue[0], hue[1])
            saturation_factor = np.random.uniform(saturation[0], saturation[1])
            value_factor = np.random.uniform(value[0], value[1])
            hsv_factors = (hue_factor, saturation_factor, value_factor)
            images[index] = self.color_jitter(images[index], hsv_factors)
        return images

    def mixup(self, inputs, labels, mixing_coeff):
        return self.noisy_mixup(inputs, labels, mixing_coeff, noisy=False)

    def noisy_mixup(self, inputs, labels, mixing_coeff, noisy=True, scale=0.025):
        '''Mixup augmentation method.
        # Reference
        - [mixup: Beyond Empirical Risk Minimization]
        (https://arxiv.org/pdf/1710.09412.pdf)
        '''
        y = mixing_coeff * labels[0] + (1 - mixing_coeff) * labels[1]
        if noisy:
            mixing_coeff += np.random.normal(scale=scale, size=(inputs[0].shape[0],
                                             inputs[0].shape[1]))
            mixing_coeff = np.clip(mixing_coeff, 0, 1)
            mixing_coeff = mixing_coeff[:, :, None]
        img = mixing_coeff * inputs[0] + (1 - mixing_coeff) * inputs[1]
        return (img, y)

    def between_class(self, inputs, labels, mixing_coeff):
        '''Between class+ augmentation method.
        # Reference
        - [Learning from Between-class Examples for Deep Sound Recognition]
        (https://arxiv.org/pdf/1711.10282.pdf)
        '''
        y = mixing_coeff * labels[0] + (1 - mixing_coeff) * labels[1]
        sigma1 = inputs[0].std()
        sigma2 = inputs[1].std()
        p = 1 / (1 + (sigma1 / sigma2) * ((1 - mixing_coeff) / mixing_coeff))
        img = (p * inputs[0] + (1 - p) * inputs[1]) / np.sqrt(p ** 2 + (1 - p) ** 2)
        return img, y

    def _concat(self, inputs, labels, mixing_coeff, axis=0):
        '''Horizontal and vertical mixed concats.
        # Reference
        - [Improved Mixed-Example Data Augmentation]
      (https://arxiv.org/pdf/1805.11272.pdf)
        '''
        y = mixing_coeff * labels[0] + (1 - mixing_coeff) * labels[1]
        boundary = int(mixing_coeff * inputs[0].shape[axis])
        first_slice = [slice(None)] * inputs[0].ndim
        first_slice[axis] = slice(boundary)
        second_slice = [slice(None)] * inputs[0].ndim
        second_slice[axis] = slice(boundary, None)
        return (np.concatenate((inputs[0][first_slice], inputs[1][second_slice]), axis=axis), y)

    def vertical_concat(self, inputs, labels, mixing_coeff):
        return self._concat(inputs, labels, mixing_coeff, axis=0)

    def horizontal_concat(self, inputs, labels, mixing_coeff):
        return self._concat(inputs, labels, mixing_coeff, axis=1)

    def mixed_concat(self, inputs, labels, mixing_coeff):
        '''Mixed concat.
        # Reference
        - [Improved Mixed-Example Data Augmentation]
      (https://arxiv.org/pdf/1805.11272.pdf)
        '''
        img1, y1 = self.vertical_concat([inputs[0], inputs[1]], [labels[0], labels[1]],
                                        mixing_coeff)
        img2, y2 = self.vertical_concat([inputs[1], inputs[0]], [labels[1], labels[0]],
                                        mixing_coeff)
        return self.horizontal_concat([img1, img2], [y1, y2], mixing_coeff)
