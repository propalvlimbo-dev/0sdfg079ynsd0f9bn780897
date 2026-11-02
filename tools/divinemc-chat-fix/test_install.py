import os,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import install
ROOT=Path(__file__).resolve().parents[2]
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.root=self.base/'server';self.root.mkdir();self.back=self.base/'backup';self.back.mkdir()
  self.jar=self.root/'server.jar';self.jar.write_bytes(b'mock-divine');self.start=self.root/'start.sh';self.original=(ROOT/'start.sh').read_bytes();self.start.write_bytes(self.original);self.start.chmod(0o755)
  self.agent=self.root/'elytrix-divine-chat-fix.jar'
  for p in (patch.object(install,'HERE',Path(os.environ.get('CHAT_FIX_PACKAGE','/tmp/divine-chat-package'))),patch.object(install,'CORE_SHA',install.sha(self.jar.read_bytes())),patch.object(install.core_safety,'check_stopped')):
   p.start();self.addCleanup(p.stop)
 def test_install_rollback(self):
  install.install(self.root,self.back);self.assertTrue(self.agent.exists());self.assertIn(b'-javaagent:',self.start.read_bytes());self.assertEqual(self.start.stat().st_mode&0o777,0o755)
  subprocess.run(['bash','-n',str(self.start)],check=True)
  install.rollback(self.root,next(self.back.iterdir()));self.assertEqual(self.start.read_bytes(),self.original);self.assertFalse(self.agent.exists())
 def test_jar_mismatch(self):
  self.jar.write_bytes(b'other')
  with self.assertRaises(ValueError):install.install(self.root,self.back)
  self.assertEqual(self.start.read_bytes(),self.original);self.assertFalse(self.agent.exists())
 def test_wrong_script(self):
  self.start.write_text('java -jar server.jar\n')
  with self.assertRaises(ValueError):install.install(self.root,self.back)
  self.assertFalse(self.agent.exists());self.assertEqual(list(self.back.iterdir()),[])
 def test_process_running(self):
  install.core_safety.check_stopped.side_effect=ValueError('running')
  with self.assertRaises(ValueError):install.install(self.root,self.back)
  self.assertFalse(self.agent.exists());self.assertEqual(list(self.back.iterdir()),[])
 def test_failure_rolls_back(self):
  orig=install.atomic;calls=[0]
  def fail_once(*a,**k):
   calls[0]+=1
   if calls[0]==2:raise OSError('test error')
   return orig(*a,**k)
  with patch.object(install,'atomic',side_effect=fail_once),self.assertRaises(OSError):install.install(self.root,self.back)
  self.assertEqual(self.start.read_bytes(),self.original);self.assertFalse(self.agent.exists())
 def test_rollback_refuses_modified(self):
  install.install(self.root,self.back);self.start.write_bytes(self.start.read_bytes()+b'# changed\n')
  with self.assertRaises(ValueError):install.rollback(self.root,next(self.back.iterdir()))
  self.assertTrue(self.agent.exists())
if __name__=='__main__':unittest.main()
