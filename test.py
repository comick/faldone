import os
import tempfile
import unittest
import uuid
from pathlib import Path

from faldone import Faldone


class FaldoneTest(unittest.TestCase):
    def test_creation(self):
        db_file = self.__temp_file()
        f = Faldone(db_file)
        f.close()
        self.assertTrue(Path(db_file).is_file())

    def __temp_file(self):
        return tempfile.gettempdir() + os.sep + str(uuid.uuid1())
