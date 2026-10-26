import unittest

import dask.array as da
from dask import delayed
import numpy as np
import xarray as xr

from cyto_studio.image_pyramid import multiscale_planes


class ImagePyramidTests(unittest.TestCase):
    def test_reads_only_requested_channel_slice_and_level(self):
        reads = []

        @delayed
        def read_plane(level, z, channel):
            reads.append((level, z, channel))
            return np.full((8, 8), z * 10 + channel, dtype=np.uint16)

        datasets = []
        for level in range(3):
            stack = da.stack([
                da.stack([
                    da.from_delayed(read_plane(level, z, channel),
                                    shape=(8, 8), dtype=np.uint16)
                    for channel in range(3)
                ]) for z in range(2)
            ])
            image = xr.DataArray(stack, dims=('z', 'channel', 'y', 'x'))
            datasets.append(xr.Dataset({'S001': image.expand_dims(type=['mosaic'])}))

        planes = multiscale_planes(datasets, 'S001', 2, 1)
        self.assertEqual(reads, [])  # Constructing the pyramid performs no reads.
        np.testing.assert_array_equal(planes[-1].compute(), np.full((8, 8), 12))
        self.assertEqual(reads, [(2, 1, 2)])

    def test_eager_image_without_type_or_z_and_intensity_scaling(self):
        image = xr.DataArray(np.arange(32).reshape(2, 4, 4),
                             dims=('channel', 'y', 'x'))
        dataset = xr.Dataset({'S002': image})
        plane = multiscale_planes([dataset], 'S002', 1, 0, 2, 5)[0]
        np.testing.assert_array_equal(plane, image.data[1] * 2 + 5)

    def test_optical_slice_axis_is_removed(self):
        image = xr.DataArray(np.ones((1, 2, 3, 3)),
                             dims=('z', 'channel', 'y', 'x'))
        plane = multiscale_planes([xr.Dataset({'S001': image})], 'S001', 1, 0)[0]
        self.assertEqual(plane.shape, (3, 3))


if __name__ == '__main__':
    unittest.main()
