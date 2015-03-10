
# python imports
import os
import shutil


# Commonly used paths.
TEST_DIR = os.path.dirname(__file__)
TMP_DIR = os.path.join(TEST_DIR, 'tmp')
DATA_DIR = os.path.join(TEST_DIR, 'data')
SRC_DIR = os.path.dirname(TEST_DIR)


def clean_dir(path):
    """Remove the directory or file if it exists."""
    if os.path.exists(path):
        shutil.rmtree(path)


def makedirs(path):
    """Make the directory oath if it does not exist."""
    if not os.path.exists(path):
        os.makedirs(path)


def make_clean_dir(path):
    """Remove and make the directory path."""
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)
