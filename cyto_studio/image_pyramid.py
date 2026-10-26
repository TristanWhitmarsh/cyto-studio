"""Build lazy planes for the legacy Zarr image pyramid."""


def multiscale_planes(datasets, section, channel, optical_slice, bscale=1, bzero=0):
    """Select one channel and optical slice before accessing any pixel data."""
    planes = []
    for dataset in datasets:
        image = dataset[section]
        if 'type' in image.dims:
            image = image.sel(type='mosaic')
        if 'z' in image.dims:
            image = image.isel(z=optical_slice)
        image = image.isel(channel=channel)
        plane = image.data.squeeze()
        if bscale != 1:
            plane = plane * bscale
        if bzero != 0:
            plane = plane + bzero
        planes.append(plane)
    return planes
