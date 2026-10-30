import gzip, json, sqlite3, struct, tempfile, unittest, uuid
from pathlib import Path
import audit

def u16(n):return struct.pack('>H',n)
def i32(n):return struct.pack('>i',n)
def s(x):b=x.encode();return u16(len(b))+b
def fixture(slots):
 # Root compound, EnderItems list of item compounds with Slot byte and id string.
 data=b'\x0a'+s('')+b'\x09'+s('EnderItems')+b'\x0a'+i32(len(slots))
 for slot in slots:data+=b'\x01'+s('Slot')+bytes([slot])+b'\x08'+s('id')+s('minecraft:stone')+b'\x00'
 return data+b'\x00'
class Tests(unittest.TestCase):
 def test_parser_and_bad_slot(self):
  self.assertEqual(audit.NBT(fixture([0,26])).slots(),[0,26])
  with self.assertRaises(ValueError):audit.NBT(fixture([27])).slots()
  with self.assertRaises(ValueError):audit.NBT(fixture([0,0])).slots()
  with self.assertRaises(ValueError):audit.NBT(fixture([1])[:-2]).slots()
 def test_aggregate_only_and_capacity(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'plugins/NEnderChest').mkdir(parents=True); (root/'plugins/NEnderChest/config.yml').write_text('itemsDatabase: "SQLite"\nplayersDatabase: "SQLite"\n'); (root/'world/playerdata').mkdir(parents=True)
   id=str(uuid.uuid4());(root/'usercache.json').write_text(json.dumps([{'uuid':id,'name':'SomePlayer'}]))
   with gzip.open(root/'world/playerdata'/f'{id}.dat','wb') as f:f.write(fixture([0,1,2]))
   with sqlite3.connect(root/'plugins/NEnderChest/items.db') as c:
    c.execute('CREATE TABLE itemsTable(player TEXT, slot INT, item_data BLOB)');c.executemany('INSERT INTO itemsTable VALUES(?,?,?)',[('SomePlayer',i,b'x') for i in range(25)])
   with sqlite3.connect(root/'plugins/NEnderChest/playerTimes.db') as c:c.execute('CREATE TABLE playerTimes(playerName TEXT, rowNumber INT, forWipe INT, forever INT)')
   result=audit.audit(root)
   self.assertEqual(result['vanilla_chests_with_items'],1);self.assertEqual(result['both_stores_nonempty'],1)
   self.assertEqual(result['definitely_not_enough_slots_without_stacking'],1)
   self.assertNotIn('SomePlayer',json.dumps(result))
   (root/'plugins/NEnderChest/items.db-wal').write_bytes(b'pending')
   with self.assertRaises(ValueError):audit.audit(root)
 def test_unmatched_user(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'plugins/NEnderChest').mkdir(parents=True); (root/'plugins/NEnderChest/config.yml').write_text('itemsDatabase: "SQLite"\nplayersDatabase: "SQLite"\n'); (root/'world/playerdata').mkdir(parents=True);(root/'usercache.json').write_text('[]')
   with sqlite3.connect(root/'plugins/NEnderChest/items.db') as c:c.execute('CREATE TABLE itemsTable(player TEXT, slot INT, item_data BLOB)')
   with sqlite3.connect(root/'plugins/NEnderChest/playerTimes.db') as c:c.execute('CREATE TABLE playerTimes(playerName TEXT, rowNumber INT, forWipe INT, forever INT)')
   with gzip.open(root/'world/playerdata'/f'{uuid.uuid4()}.dat','wb') as f:f.write(fixture([0]))
   self.assertEqual(audit.audit(root)['unknown_or_ambiguous_names'],1)
if __name__=='__main__':unittest.main()
