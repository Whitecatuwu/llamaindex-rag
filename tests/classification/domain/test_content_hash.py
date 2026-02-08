import unittest

from src.classification.domain.content_hash import compute_content_hash


class ContentHashTests(unittest.TestCase):
    def test_same_content_with_different_newlines_has_same_hash(self):
        a = "line1\r\nline2\r\n"
        b = "line1\nline2\n"
        self.assertEqual(compute_content_hash(a), compute_content_hash(b))

    def test_different_content_has_different_hash(self):
        self.assertNotEqual(compute_content_hash("abc"), compute_content_hash("abd"))

