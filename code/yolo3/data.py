import tensorflow as tf
from functools import reduce
from yolo3.utils import get_random_data, preprocess_true_boxes
from yolo3.enums import DATASET_MODE

AUTOTUNE = tf.data.experimental.AUTOTUNE


class Dataset(object):

    def parse_tfrecord(self, example_proto):
        feature_description = {
            'image/encoded': tf.io.FixedLenFeature([], tf.string),
            'image/object/bbox/xmin': tf.io.VarLenFeature(tf.float32),
            'image/object/bbox/xmax': tf.io.VarLenFeature(tf.float32),
            'image/object/bbox/ymin': tf.io.VarLenFeature(tf.float32),
            'image/object/bbox/ymax': tf.io.VarLenFeature(tf.float32),
            'image/object/bbox/label': tf.io.VarLenFeature(tf.int64)
        }
        features = tf.io.parse_single_example(example_proto,
                                              feature_description)
        image = tf.image.decode_image(features['image/encoded'],
                                      channels=3,
                                      dtype=tf.float32)
        image.set_shape([None, None, 3])
        xmins = features['image/object/bbox/xmin'].values
        xmaxs = features['image/object/bbox/xmax'].values
        ymins = features['image/object/bbox/ymin'].values
        ymaxs = features['image/object/bbox/ymax'].values
        labels = features['image/object/bbox/label'].values
        image, bbox = get_random_data(image,
                                      xmins,
                                      xmaxs,
                                      ymins,
                                      ymaxs,
                                      labels,
                                      self.input_shape,
                                      zoom_in = self.zoom_in,
                                      train=self.mode == DATASET_MODE.TRAIN)

        if(self.num_scales==1):
            y1 = tf.py_function(
                preprocess_true_boxes,
                [bbox, self.input_shape, self.anchors, self.num_classes, self.num_scales],
                [tf.float32])
            y1.set_shape([None, None, len(self.anchors) // self.num_scales, self.num_classes + 5])

            return image, (y1[0])

        elif(self.num_scales==2):
            y1, y2 = tf.py_function(
                preprocess_true_boxes,
                [bbox, self.input_shape, self.anchors, self.num_classes, self.num_scales],
                [tf.float32, tf.float32])
            y1.set_shape([None, None, len(self.anchors) // self.num_scales, self.num_classes + 5])
            y2.set_shape([None, None, len(self.anchors) // self.num_scales, self.num_classes + 5])

            return image, (y1, y2)

        else:
            y1, y2, y3 = tf.py_function(
                preprocess_true_boxes,
                [bbox, self.input_shape, self.anchors, self.num_classes, self.num_scales],
                [tf.float32, tf.float32, tf.float32])
            y1.set_shape([None, None, len(self.anchors) // self.num_scales, self.num_classes + 5])
            y2.set_shape([None, None, len(self.anchors) // self.num_scales, self.num_classes + 5])
            y3.set_shape([None, None, len(self.anchors) // self.num_scales, self.num_classes + 5])

            return image, (y1, y2, y3)

    def parse_text(self, line):
        values = tf.strings.split([line], ' ').values
        print(values)
        image = tf.image.decode_image(tf.io.read_file(values[0]),
                                      channels=3,
                                      dtype=tf.float32)
        image.set_shape([None, None, 3])
        reshaped_data = tf.reshape(values[1:], [-1, 5])
        xmins = tf.strings.to_number(reshaped_data[:, 0], tf.float32)
        xmaxs = tf.strings.to_number(reshaped_data[:, 2], tf.float32)
        ymins = tf.strings.to_number(reshaped_data[:, 1], tf.float32)
        ymaxs = tf.strings.to_number(reshaped_data[:, 3], tf.float32)
        labels = tf.strings.to_number(reshaped_data[:, 4], tf.int64)

        image, bbox = get_random_data(image,
                                      xmins,
                                      xmaxs,
                                      ymins,
                                      ymaxs,
                                      labels,
                                      self.input_shape,
                                      zoom_in = self.zoom_in,
                                      train=self.mode == DATASET_MODE.TRAIN)
        if(self.num_scales==1):
            y1 = tf.py_function(
                preprocess_true_boxes,
                [bbox, self.input_shape, self.anchors, self.num_classes, self.num_scales],
                [tf.float32])
            y1[0].set_shape([None, None, len(self.anchors) // self.num_scales, self.num_classes + 5])

            return image, (y1[0])

        elif(self.num_scales==2):
            y1, y2 = tf.py_function(
                preprocess_true_boxes,
                [bbox, self.input_shape, self.anchors, self.num_classes, self.num_scales],
                [tf.float32, tf.float32])
            y1.set_shape([None, None, len(self.anchors) // self.num_scales, self.num_classes + 5])
            y2.set_shape([None, None, len(self.anchors) // self.num_scales, self.num_classes + 5])

            return image, (y1, y2)

        else:
            y1, y2, y3 = tf.py_function(
                preprocess_true_boxes,
                [bbox, self.input_shape, self.anchors, self.num_classes, self.num_scales],
                [tf.float32, tf.float32, tf.float32])
            y1.set_shape([None, None, len(self.anchors) // self.num_scales, self.num_classes + 5])
            y2.set_shape([None, None, len(self.anchors) // self.num_scales, self.num_classes + 5])
            y3.set_shape([None, None, len(self.anchors) // self.num_scales, self.num_classes + 5])

            return image, (y1, y2, y3)

    def _dataset_internal(self, files, dataset_builder, parser):
        dataset = tf.data.Dataset.from_tensor_slices(files)
        print("hi")
        for element in dataset:
            print("weeeee")
            print(element)

        if self.mode == DATASET_MODE.TRAIN:
            train_num = reduce(
                lambda x, y: x + y,
                map(lambda file: int(self._get_num_from_name(file)), files))
            dataset = dataset.interleave(
                lambda file: dataset_builder(file),
                cycle_length=AUTOTUNE,
                num_parallel_calls=AUTOTUNE).shuffle(train_num).map(
                    parser, num_parallel_calls=AUTOTUNE).prefetch(
                        self.batch_size).batch(self.batch_size)
        elif self.mode == DATASET_MODE.VALIDATE:
            dataset = dataset.interleave(
                lambda file: dataset_builder(file),
                cycle_length=AUTOTUNE,
                num_parallel_calls=AUTOTUNE).map(
                    parser, num_parallel_calls=AUTOTUNE).prefetch(
                        self.batch_size).batch(self.batch_size)
        elif self.mode == DATASET_MODE.TEST:
            dataset = dataset.interleave(
                lambda file: dataset_builder(file),
                cycle_length=AUTOTUNE,
                num_parallel_calls=AUTOTUNE).map(
                    parser, num_parallel_calls=AUTOTUNE).prefetch(
                        self.batch_size).batch(self.batch_size)
        return dataset

    def __init__(self,
                 glob_path: str,
                 batch_size: int,
                 anchors=None,
                 num_classes=None,
                 input_shape=None,
                 num_scales=None,
                 mode=DATASET_MODE.TRAIN,
                 zoom_in=False):
        self.glob_path = glob_path
        self.batch_size = batch_size
        self.input_shape = input_shape
        self.anchors = anchors
        self.num_classes = num_classes
        self.num_scales = num_scales
        self.mode = mode
        self.zoom_in = zoom_in

    def _get_num_from_name(self, name):
        return int(name.split('/')[-1].split('.')[0].split('_')[-1])

    def build(self, split=None):
        if self.glob_path is None:
            return None,0
        files = tf.io.gfile.glob(self.glob_path)
        if len(files) == 0:
            raise ValueError('No file found')
        try:
            num = reduce(lambda x, y: x + y,
                         map(lambda file: self._get_num_from_name(file), files))
        except Exception:
            raise ValueError(
                'Please format file name like <name>_<number>.<extension>')
        else:
            tfrecords = list(
                filter(lambda file: file.endswith('.tfrecords'), files))
            txts = list(filter(lambda file: file.endswith('.txt'), files))
            print(txts)
            if len(tfrecords) > 0:
                tfrecords_dataset = self._dataset_internal(
                    tfrecords, tf.data.TFRecordDataset, self.parse_tfrecord)
            if len(txts) > 0:
                txts_dataset = self._dataset_internal(txts,
                                                      tf.data.TextLineDataset,
                                                      self.parse_text)
            if len(tfrecords) > 0 and len(txts) > 0:
                return tfrecords_dataset.concatenate(txts_dataset), num
            elif len(tfrecords) > 0:
                return tfrecords_dataset, num
            elif len(txts) > 0:
                return txts_dataset, num
