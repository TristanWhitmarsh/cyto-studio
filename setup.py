"""Setup script for cyto-studio"""
import os.path
from setuptools import setup, find_packages

# The directory containing this file
HERE = os.path.abspath(os.path.dirname(__file__))

# The text of the README file
with open(os.path.join(HERE, "README.md")) as fid:
    README = fid.read()

# this grabs the requirements from requirements.txt
#REQUIREMENTS = [i.strip() for i in open("requirements.txt").readlines()]

# This call to setup() does all the work
setup(
    name="cyto_studio",
    version="1.0.0",
    description="napari viewer which can read multiplex images as zarr files",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/TristanWhitmarsh/cyto-studio",
    author="Tristan Whitmarsh",
    author_email="tw401@cam.ac.uk",
    license="GNU",
    classifiers=[
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Programming Language :: Python :: 3",
    ],
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "cyto_studio": ["custom.qss", "icon.png", "icon.png"],
    },
    install_requires=[
        # Modernized stack (Route A): Python >=3.11, Qt6/PySide6, zarr v3.
        # This allows reading both the legacy STPT zarr-v2 datasets (via xarray,
        # which reads v2 through zarr 3) and the new SpatialData (OME-NGFF zarr-v3)
        # datasets via the spatialdata library.
        'napari==0.5.6',
        'PySide6>=6.5',
        'xarray>=2024.1.0',
        'zarr>=3.0.0',
        'SimpleITK>=2.3.1',
        'napari-animation',
        'tifffile',
        'pyarrow',
        'opencv-python-headless>=4.5.1.48',
        'numpy>=2.0.0',
        'geopandas>=1.0.1',
        'spatialdata>=0.5.0',
        # Some deps in the spatialdata tree (e.g. xarray-schema) still import
        # pkg_resources, which setuptools>=81 no longer ships. Keep a setuptools
        # that still provides it.
        'setuptools<81',
    ],
    python_requires=">=3.11",
    entry_points={
        "console_scripts": ["cyto-studio=cyto_studio.__main__:main"]
    },
)