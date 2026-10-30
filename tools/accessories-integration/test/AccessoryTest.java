package pw.elytrix.freakmodel;
import java.util.*;
import org.bukkit.*;
import org.bukkit.entity.*;
import org.bukkit.inventory.*;
import org.bukkit.persistence.*;
import org.bukkit.event.inventory.*;
import org.bukkit.command.*;
import org.bukkit.plugin.*;
import org.bukkit.event.*;
import com.ticxo.modelengine.api.ModelEngineAPI;

public class AccessoryTest {
 static class Data implements PersistentDataContainer {Map<NamespacedKey,Object> m=new HashMap<>();@SuppressWarnings("unchecked") public <P,C>C get(NamespacedKey k,PersistentDataType<P,C> t){return (C)m.get(k);}public <P,C>void set(NamespacedKey k,PersistentDataType<P,C> t,C v){m.put(k,v);} public void remove(NamespacedKey k){m.remove(k);}}
 static class PlayerFake implements Player {boolean admin;String command;UUID uuid=UUID.fromString("00000000-0000-0000-0000-0000000000aa");public boolean performCommand(String c){command=c;return true;}public void closeInventory(){}Data data=new Data();String msg;public boolean hasPermission(String s){return admin;}public Data getPersistentDataContainer(){return data;}public Inventory opened;public InventoryView openInventory(Inventory i){opened=i;return null;}public void sendMessage(String s){msg=s;}public java.util.UUID getUniqueId(){return uuid;}public boolean isOnline(){return true;}}
 static FreakModelSpec spec(String id){return new FreakModelSpec(id,ModelKind.ANGEL_WINGS,id,List.of(),Material.FEATHER,"model",34,id,List.of(),1,0,0,1,1,2,0,0,0,0,0,0,0,0,0,0,0,false,false);}
 // --- ModelEngine double: proves tickEyepatch really attaches the patch ------
 static class FakePivot implements com.ticxo.modelengine.api.model.PivotOverride {}
 static class FakePivotRegistry implements com.ticxo.modelengine.api.model.PivotOverrideRegistry {
  public com.ticxo.modelengine.api.model.PivotOverride getOrCreate(Entity e){return new FakePivot();}}
 static class FakeActive implements com.ticxo.modelengine.api.model.ActiveModel {
  final com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint bp;boolean destroyed,canHurt=true,shadow=true,hitbox=true,lockPitch,lockYaw;float view;Boolean rotLocked;float lockedX,lockedY,lockedBody;com.ticxo.modelengine.api.model.PivotOverride pivot;
  FakeActive(com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint bp){this.bp=bp;}
  public boolean isDestroyed(){return destroyed;}public void destroy(){destroyed=true;}
  public com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint getBlueprint(){return bp;}
  public void setCanHurt(boolean v){canHurt=v;}public void setShadowVisible(boolean v){shadow=v;}public void setHitboxVisible(boolean v){hitbox=v;}
  public void setLockPitch(boolean v){lockPitch=v;}public void setLockYaw(boolean v){lockYaw=v;}public void setViewRange(float v){view=v;}
  public void setScale(double v){}public void setPivotOverride(com.ticxo.modelengine.api.model.PivotOverride v){pivot=v;}
  public void setModelRotationLocked(Boolean v){rotLocked=v;}public void setLockedXHeadRot(float v){lockedX=v;}
  public void setLockedYHeadRot(float v){lockedY=v;}public void setLockedYBodyRot(float v){lockedBody=v;}}
 static class FakeModeled implements com.ticxo.modelengine.api.model.ModeledEntity {
  final Query q;int adds,removes,syncs;boolean destroyed,baseVisible=true;Map<String,com.ticxo.modelengine.api.model.ActiveModel> models=new HashMap<>();float bodyYaw;
  FakeModeled(Query q){this.q=q;}
  public boolean isDestroyed(){return destroyed;}
  public void setBaseEntityVisible(boolean v){baseVisible=v;}
  public Optional<com.ticxo.modelengine.api.model.ActiveModel> addModel(com.ticxo.modelengine.api.model.ActiveModel m,boolean passenger){adds++;q.last=(FakeActive)m;models.put("elytrix_kaneki_eyepatch",m);return Optional.of(m);}
  public Optional<com.ticxo.modelengine.api.model.ActiveModel> removeModel(String id){removes++;com.ticxo.modelengine.api.model.ActiveModel m=models.remove(id);if(m instanceof FakeActive)((FakeActive)m).destroy();return Optional.ofNullable(m);}
  public Optional<com.ticxo.modelengine.api.model.ActiveModel> getModel(String id){return Optional.ofNullable(models.get(id));}
  public void setYBodyRotImmediately(float v){}public void setYHeadRotImmediately(float v){}public void setXHeadRotImmediately(float v){}public void setRotationTick(int t){}}
 static class Query {FakeActive last;int blueprints;int created;}
 static class FakeEngine implements ModelEngineAPI.Backend {
  final Query q=new Query();final Map<UUID,FakeModeled> entities=new HashMap<>();final FakePivotRegistry pivots=new FakePivotRegistry();
  public com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint blueprint(String id){q.blueprints++;return new com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint();}
  public com.ticxo.modelengine.api.model.ModeledEntity modeledEntity(Entity e){return entities.computeIfAbsent(e.getUniqueId(),k->new FakeModeled(q));}
  public com.ticxo.modelengine.api.model.ActiveModel createActiveModel(com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint bp){q.created++;return new FakeActive(bp);}
  public com.ticxo.modelengine.api.model.PivotOverrideRegistry pivots(){return pivots;}}
 static void check(boolean c,String s){if(!c)throw new AssertionError(s);}
 public static void main(String[] args){
  ElytrixFreakModelPlugin plugin=new ElytrixFreakModelPlugin();plugin.wings=spec("angel_wings");plugin.halo=spec("angel_halo");PlayerFake p=new PlayerFake();
  p.data.set(AccessoryController.BACK,PersistentDataType.STRING,"kaneki");p.data.set(AccessoryController.HALO,PersistentDataType.STRING,"halo");
  check(AccessoryController.back(plugin,p)==null && AccessoryController.halo(plugin,p)==null,"non-admin denied");
  p.admin=true;FreakModelSpec a=AccessoryController.back(plugin,p);check(a!=null && a.blueprintId.equals("elytrix_kaneki_tentacles"),"tentacles selected");check(a==AccessoryController.back(plugin,p),"reuses spec");check(AccessoryController.halo(plugin,p)==plugin.halo,"halo independent");
  p.data.set(AccessoryController.BACK,PersistentDataType.STRING,"wings");check(AccessoryController.back(plugin,p)==plugin.wings,"wings selected");
  p.data.set(AccessoryController.BACK,PersistentDataType.STRING,"bad");check(AccessoryController.back(plugin,p)==null,"unknown rejected");
  p.admin=false;check(AccessoryController.halo(plugin,p)==null,"permission revocation applied");
  class PM implements PluginManager {Listener listener;public void registerEvents(Listener l,Plugin p){listener=l;}} PM pm=new PM();Bukkit.manager=pm;
  AccessoryController.install(plugin);AccessoryController controller=(AccessoryController)pm.listener;
  check(plugin.mockCommand.executor==controller,"executor registered");
  p.admin=false;check(controller.onCommand(p,new Command(),"аксессуары",new String[0]),"command handled");
  check(p.opened!=null,"menu visible to non-admin");
  check(Bukkit.slots.get(14).meta.model.equals(new NamespacedKey("reallyworld","kaneki_tentacles_icon")),"tentacle menu icon");
  check(Bukkit.slots.get(12).meta.model.equals(new NamespacedKey("reallyworld","angel_wings")),"wings icon");
  InventoryClickEvent click=new InventoryClickEvent();click.view=()->p.opened;click.who=p;click.slot=14;
  check(Bukkit.size==54 && Bukkit.title.contains("ꏠ"),"resource pack menu");
  click.slot=31;controller.onClick(click);check("menu".equals(p.command),"back available to non-admin");click.slot=14;
  p.data.remove(AccessoryController.BACK);controller.onClick(click);check(click.cancelled && AccessoryController.back(plugin,p)==null && !p.data.m.containsKey(AccessoryController.BACK),"non-admin click denied");
  p.admin=true;ModelEngineAPI.backend=null;controller.onClick(click);check(!p.data.m.containsKey(AccessoryController.BACK),"missing engine denied");
  ModelEngineAPI.backend=new FakeEngine();controller.onClick(click);check(AccessoryController.back(plugin,p).blueprintId.equals("elytrix_kaneki_tentacles"),"menu selection");
  click.slot=13;controller.onClick(click);check(AccessoryController.halo(plugin,p)==plugin.halo,"independent halo click");
  click.slot=12;controller.onClick(click);check(AccessoryController.back(plugin,p)==plugin.wings,"wings replace tentacles");
  click.slot=30;controller.onClick(click);check(AccessoryController.back(plugin,p)==null && AccessoryController.halo(plugin,p)!=null,"clear only back");
  // --- the eyepatch: its own menu slot, its own head slot -------------------
  check(Bukkit.slots.get(15).meta.model.equals(new NamespacedKey("reallyworld","kaneki_eyepatch_icon")),"eyepatch menu icon");
  check(Bukkit.slots.get(32).meta.title.contains("голов"),"head slot has its own remove button");
  p.data.set(AccessoryController.BACK,PersistentDataType.STRING,"kaneki");
  click.slot=15;controller.onClick(click);
  check(AccessoryController.eyepatchSelected(p),"eyepatch selected from the menu");
  check(AccessoryController.halo(plugin,p)==null,"the patch replaces the halo on the head");
  check("kaneki".equals(p.data.get(AccessoryController.BACK,PersistentDataType.STRING)),"the patch does not touch the back slot");
  FreakModelSpec patch=AccessoryController.eyepatch(plugin);
  check(patch!=null && patch.blueprintId.equals("elytrix_kaneki_eyepatch"),"own spec for the patch");
  check(patch==AccessoryController.eyepatch(plugin),"patch spec cached");
  p.data.remove(AccessoryController.BACK);
  p.data.set(AccessoryController.BACK,PersistentDataType.STRING,"kaneki");
  check(AccessoryController.back(plugin,p)!=null && AccessoryController.eyepatchSelected(p),"kagune and patch together");
  click.slot=13;controller.onClick(click);
  check(AccessoryController.halo(plugin,p)==plugin.halo && !AccessoryController.eyepatchSelected(p),"halo replaces the patch");
  click.slot=32;controller.onClick(click);
  check(AccessoryController.halo(plugin,p)==null && !AccessoryController.eyepatchSelected(p),"head cleared");
  // legacy halo selection (written before the head slot existed) is honoured
  p.data.set(AccessoryController.HALO,PersistentDataType.STRING,"halo");
  check(AccessoryController.halo(plugin,p)==plugin.halo,"legacy halo key still works");
  p.data.set(AccessoryController.HEAD,PersistentDataType.STRING,"eyepatch");
  check(AccessoryController.eyepatchSelected(p) && AccessoryController.halo(plugin,p)==null,"head key wins");
  // --- tickEyepatch: attaches exactly one patch and cleans it up ------------
  p.data.set(AccessoryController.HEAD,PersistentDataType.STRING,"eyepatch");
  FakeEngine engine=(FakeEngine)ModelEngineAPI.backend;Query q=engine.q;
  AccessoryController.tickEyepatch(plugin,p);
  FakeModeled worn=engine.entities.get(p.getUniqueId());
  check(worn!=null && worn.adds==1,"patch attached to the shared model entity");
  check(worn.baseVisible,"the player under the patch stays visible");
  check(q.last!=null && !q.last.canHurt && !q.last.shadow && !q.last.hitbox,"patch is a pure cosmetic");
  check(q.last.lockPitch && q.last.lockYaw && q.last.view==64f,"patch follows the body");
  check(Boolean.TRUE.equals(q.last.rotLocked) && q.last.lockedX==0f && q.last.lockedY==0f && q.last.lockedBody==0f,"rotation locked like the halo");
  check(q.last.pivot!=null,"pivot override shared");
  AccessoryController.tickEyepatch(plugin,p);
  check(worn.adds==1,"ticking again does not stack a second patch");
  p.data.set(AccessoryController.HEAD,PersistentDataType.STRING,"halo");
  AccessoryController.tickEyepatch(plugin,p);
  check(worn.removes==1 && q.last.destroyed,"patch removed when the halo comes back");
  p.data.set(AccessoryController.HEAD,PersistentDataType.STRING,"eyepatch");
  q.created=0;AccessoryController.tickEyepatch(plugin,p);
  check(q.created==1 && worn.adds==2,"patch comes back after re-selecting");
  q.last.destroyed=true;AccessoryController.tickEyepatch(plugin,p);
  check(worn.adds==3,"a destroyed patch is rebuilt");
  // a reload keeps the attached model but forgets our map: adopt, never duplicate
  PlayerFake other=new PlayerFake();other.admin=true;other.uuid=UUID.randomUUID();
  other.data.set(AccessoryController.HEAD,PersistentDataType.STRING,"eyepatch");
  FakeModeled seeded=new FakeModeled(engine.q);
  FakeActive leftover=new FakeActive(new com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint());
  seeded.models.put("elytrix_kaneki_eyepatch",leftover);
  engine.entities.put(other.uuid,seeded);
  AccessoryController.tickEyepatch(plugin,other);
  check(seeded.adds==0 && !leftover.destroyed,"leftover patch is adopted, not duplicated");
  // and a player without the patch never touches ModelEngine at all
  PlayerFake idle=new PlayerFake();idle.admin=true;idle.uuid=UUID.randomUUID();
  AccessoryController.tickEyepatch(plugin,idle);
  check(!engine.entities.containsKey(idle.uuid),"no entity created for players without the patch");
  InventoryDragEvent drag=new InventoryDragEvent();drag.view=click.view;controller.onDrag(drag);check(drag.cancelled,"drag cancelled");
  System.out.println("Accessory GUI, permission, selection and cached tentacle spec mock tests passed");
 }
}
