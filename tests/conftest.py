import pytest
from pyfakefs.fake_filesystem_unittest import Patcher

@pytest.fixture
def fs():
    with Patcher() as patcher:
        yield patcher.fs
