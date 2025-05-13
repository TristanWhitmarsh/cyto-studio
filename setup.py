"""Setup script for cyto-studio"""
import os.path
import subprocess
import pkg_resources
from setuptools import setup, find_packages

# Uninstall opencv-python if it's installed
try:
    dist = pkg_resources.get_distribution("opencv-python")
    print("Uninstalling opencv-python to avoid Qt conflicts...")
    subprocess.check_call(["pip", "uninstall", "-y", "opencv-python"])
except pkg_resources.DistributionNotFound:
    pass

# The directory containing this file
HERE = os.path.abspath(os.path.dirname(__file__))

# The text of the README file
with open(os.path.join(HERE, "README.md")) as fid:
    README = fid.read()

# this grabs the requirements from requirements.txt
#REQUIREMENTS = [i.strip() for i in open("requirements.txt").readlines()]

# This call to setup() does all the work
setup(
    name="cyto-studio",
    version="0.1.17",
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
        "cyto_studio": ["custom.qss", "icon.png", "logo.png"],
    },
    install_requires=[
        'napari[pyside2]==0.4.17',
        'PySide2==5.15.2.1',
        'xarray==2023.4.2',
        'zarr==2.14.2',
        'SimpleITK==2.2.1',
        'napari-animation==0.0.7',
        'tifffile==2023.4.12',
        'pyarrow==19.0.1',
        'opencv-python-headless>=4.5.1.48',
        'numpy==1.23.5',
        'pydantic==1.10.15',
    ],
    entry_points={"console_scripts": ["cyto-studio=cyto_studio.__main__:main"]},
)