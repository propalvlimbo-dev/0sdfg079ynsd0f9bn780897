import unittest
from patch import rewrite
class TestClanFormat(unittest.TestCase):
    def test_crlf_comment_and_other_settings_survive(self):
        old=b'# before\r\nclanNameFormat: "&8[%clan%&8]" # original\r\nother: true\r\n'
        self.assertEqual(rewrite(old),b'# before\r\nclanNameFormat: "%clan%" # original\r\nother: true\r\n')
    def test_already_fixed(self):
        raw=b"clanNameFormat: '%clan%'\n"
        self.assertEqual(rewrite(raw),raw)
    def test_refuse_custom_or_duplicate(self):
        for raw in (b'clanNameFormat: "[%clan%]"\n', b'clanNameFormat: "&8[%clan%&8]"\nclanNameFormat: "%clan%"\n', b'clanNameFormat: [%clan%]\n'):
            with self.assertRaises(ValueError): rewrite(raw)
if __name__=='__main__': unittest.main()
