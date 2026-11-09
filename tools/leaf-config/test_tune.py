import unittest
from pathlib import Path
import tune
class T(unittest.TestCase):
 def test_only_requested_values(self):
  text="config-version: '3.0'\nasync:\n  async-chunk-send:\n    enabled: false # c\n  async-mob-spawning:\n    enabled: false\n  async-entity-tracker:\n    enabled: false\nperformance:\n  optimize-block-entities: false\n  reduce-packets:\n    enabled: false\n"
  result=tune.transform(text)
  self.assertIn('    enabled: true # c',result)
  self.assertIn('  optimize-block-entities: true',result)
  self.assertIn('  async-entity-tracker:\n    enabled: false',result)
  self.assertIn('  reduce-packets:\n    enabled: false',result)
 def test_missing_duplicate_and_version_refused(self):
  text=Path(__file__).resolve().parents[2].joinpath('config/leaf-global.yml').read_text()
  self.assertEqual(tune.transform(text),text)
  with self.assertRaises(ValueError):tune.transform(text.replace("config-version: '3.0'","config-version: '4.0'"))
  with self.assertRaises(ValueError):tune.transform(text.replace('  optimize-block-entities: true','  optimize-block-entities: true\n  optimize-block-entities: false'))
  with self.assertRaises(ValueError):tune.transform(text.replace('  optimize-block-entities: true',''))
if __name__=='__main__':unittest.main()
