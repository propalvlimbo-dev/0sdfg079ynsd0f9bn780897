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
 static class Inv implements PlayerInventory {
  ItemStack helmet; final java.util.List<ItemStack> added=new java.util.ArrayList<>(); final int capacity;
  Inv(int capacity){this.capacity=capacity;}
  public ItemStack getHelmet(){return helmet;}
  public void setHelmet(ItemStack item){helmet=item;}
  public int firstEmpty(){return added.size()<capacity?added.size():-1;}
  public java.util.Map<Integer,ItemStack> addItem(ItemStack... items){
   java.util.Map<Integer,ItemStack> left=new java.util.LinkedHashMap<>();
   for(ItemStack it:items){ if(added.size()<capacity) added.add(it); else left.put(left.size(),it); }
   return left;}
 }
 static class PlayerFake implements Player {Inv inv=new Inv(36);public PlayerInventory getInventory(){return inv;}boolean admin,use;String command;UUID uuid=UUID.fromString("00000000-0000-0000-0000-0000000000aa");public boolean performCommand(String c){command=c;return true;}public void closeInventory(){}Data data=new Data();String msg;public boolean hasPermission(String s){return admin || (use && s.equals(AccessoryController.USE_PERMISSION));}public Data getPersistentDataContainer(){return data;}public Inventory opened;public InventoryView openInventory(Inventory i){opened=i;return null;}public void sendMessage(String s){msg=s;}public java.util.UUID getUniqueId(){return uuid;}public boolean isOnline(){return true;}public String getName(){return "Tester";}}
 static FreakModelSpec spec(String id){return new FreakModelSpec(id,ModelKind.ANGEL_WINGS,id,List.of(),Material.FEATHER,"model",34,id,List.of(),1,0,0,1,1,2,0,0,0,0,0,0,0,0,0,0,0,false,false);}
 // --- ModelEngine double: keeps the mock runs away from a live engine -------
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
  class PM implements PluginManager {Listener listener;java.util.Set<String> enabled=new java.util.HashSet<>();public void registerEvents(Listener l,Plugin p){listener=l;}public boolean isPluginEnabled(String n){return enabled.contains(n);}}
  PM pm=new PM();Bukkit.manager=pm;
  AccessoryController.install(plugin);AccessoryController controller=(AccessoryController)pm.listener;
  check(plugin.mockCommand.executor==controller,"executor registered");
  check(Bukkit.dispatched.isEmpty(),"no LuckPerms command when the plugin is absent");
  // with LuckPerms installed the start-up writes the media node once
  pm.enabled.add("LuckPerms");Bukkit.dispatched.clear();Bukkit.dispatchWorks=false;
  AccessoryController.install(plugin);
  check(Bukkit.dispatched.isEmpty(),"a dispatch while LuckPerms is still enabling is not counted");
  Bukkit.dispatchWorks=true;AccessoryController.install(plugin);
  check(Bukkit.dispatched.equals(List.of("lp group media permission set elytrixaccessories.use true")),
        "media group gets the node automatically");
  Bukkit.dispatched.clear();AccessoryController.install(plugin);
  check(Bukkit.dispatched.isEmpty(),"and only once");
  pm.enabled.clear();
  p.admin=false;check(controller.onCommand(p,new Command(),"аксессуары",new String[0]),"command handled");
  check(p.opened!=null,"menu visible to non-admin");
  check(Bukkit.slots.get(14).meta.model.equals(new NamespacedKey("reallyworld","kaneki_tentacles_icon")),"tentacle menu icon");
  check(Bukkit.slots.get(12).meta.model.equals(new NamespacedKey("reallyworld","angel_wings")),"wings icon");
  // кнопки «назад» больше нет, «Снять всё» переехала в нижний ряд по центру
  check(Bukkit.slots.get(31)==null,"no back button any more");
  check(Bukkit.slots.get(30)==null,"old clear-all slot stays empty");
  ItemStack clearAll=Bukkit.slots.get(49);
  check(clearAll!=null && clearAll.getType()==Material.BARRIER,"one button clears everything");
  check(clearAll.meta.title.contains("Снять всё"),"clear-all is labelled");
  check(Bukkit.slots.size()==5,"four accessories and clear-all");
  InventoryClickEvent click=new InventoryClickEvent();click.view=()->p.opened;click.who=p;click.slot=14;
  check(Bukkit.size==54 && Bukkit.title.contains("ꏠ"),"resource pack menu");
  click.slot=14;   // никакой кнопки «назад» в меню больше нет
  p.data.remove(AccessoryController.BACK);controller.onClick(click);
  check(click.cancelled && AccessoryController.back(plugin,p)==null && !p.data.m.containsKey(AccessoryController.BACK),"non-admin click denied");
  check(p.msg.contains("media"),"the denial names the donation rank");
  // the media rank reaches the same menu through its permission node
  PlayerFake media=new PlayerFake();media.use=true;media.uuid=UUID.randomUUID();
  check(AccessoryController.allowed(media),"media permission unlocks the menu");
  check(!AccessoryController.allowed(p),"no permission, no accessories");
  p.admin=true;ModelEngineAPI.backend=null;controller.onClick(click);check(!p.data.m.containsKey(AccessoryController.BACK),"missing engine denied");
  p.data.remove(AccessoryController.HALO);   // the legacy node is covered further down
  ModelEngineAPI.backend=new FakeEngine();controller.onClick(click);check(AccessoryController.back(plugin,p).blueprintId.equals("elytrix_kaneki_tentacles"),"menu selection");
  // second click on the same button takes it off again
  controller.onClick(click);check(AccessoryController.back(plugin,p)==null,"second click removes the kagune");
  check(p.msg.contains("сняты"),"and says so");
  controller.onClick(click);check(AccessoryController.back(plugin,p)!=null,"third click puts it back");
  click.slot=12;controller.onClick(click);check(AccessoryController.back(plugin,p)==plugin.wings,"wings replace tentacles");
  controller.onClick(click);check(AccessoryController.back(plugin,p)==null,"clicking the worn wings takes them off");
  click.slot=13;controller.onClick(click);check(AccessoryController.halo(plugin,p)==plugin.halo,"halo on");
  controller.onClick(click);check(AccessoryController.halo(plugin,p)==null,"halo off by the same button");
  // --- the eyepatch: a real helmet-slot item, no ModelEngine model ---------
  check(Bukkit.slots.get(15).meta.model.equals(new NamespacedKey("reallyworld","kaneki_eyepatch_icon")),"eyepatch menu icon");
  p.data.set(AccessoryController.BACK,PersistentDataType.STRING,"kaneki");
  click.slot=15;controller.onClick(click);
  check(AccessoryController.eyepatchSelected(p),"eyepatch selected from the menu");
  check(AccessoryController.wearingPatch(p),"the patch item sits on the head");
  ItemStack worn=p.inv.getHelmet();
  check(worn!=null && worn.getType()==Material.LEATHER_HELMET,"head slot holds the patch");
  check(worn.meta.equippable.slot==EquipmentSlot.HEAD,"equipped in the head slot");
  check(new NamespacedKey("reallyworld","kaneki_eyepatch").equals(worn.meta.equippable.model),"custom armour layer");
  check(new NamespacedKey("reallyworld","kaneki_eyepatch_icon").equals(worn.meta.model),"inventory icon");
  // ни одного ModelEngine-объекта: слой рисует сам клиент, поэтому в первом лице его нет
  check(AccessoryController.halo(plugin,p)==null,"no head model any more");
  check("kaneki".equals(p.data.get(AccessoryController.BACK,PersistentDataType.STRING)),"the patch does not touch the back slot");
  check(AccessoryController.back(plugin,p)!=null && AccessoryController.eyepatchSelected(p),"kagune and patch together");
  // второй клик снимает предмет и возвращает его в инвентарь
  click.slot=15;controller.onClick(click);
  check(!AccessoryController.eyepatchSelected(p) && !AccessoryController.wearingPatch(p),"second click removes the patch");
  check(p.inv.getHelmet()==null && p.inv.added.size()==1,"the patch goes back to the inventory");
  click.slot=15;controller.onClick(click);
  check(AccessoryController.wearingPatch(p),"third click wears it again");
  // нимб забирает слот головы, а вместе с ним уходит и предмет повязки
  click.slot=13;controller.onClick(click);
  check(AccessoryController.halo(plugin,p)==plugin.halo && !AccessoryController.eyepatchSelected(p),"halo replaces the patch");
  check(!AccessoryController.wearingPatch(p),"halo takes the patch item off");
  click.slot=15;controller.onClick(click);
  check(AccessoryController.eyepatchSelected(p) && AccessoryController.halo(plugin,p)==null,"patch replaces the halo");
  // настоящий шлем не теряется: он уезжает в инвентарь
  click.slot=15;controller.onClick(click);          // снимаем повязку
  p.inv.setHelmet(new ItemStack(Material.FEATHER));p.inv.added.clear();
  click.slot=15;controller.onClick(click);          // надеваем поверх шлема
  check(AccessoryController.wearingPatch(p),"patch goes over the helmet");
  check(p.inv.added.size()==1 && p.inv.added.get(0).getType()==Material.FEATHER,"the helmet is stored, not deleted");
  // инвентарь полон — надевать некуда, отказываем и шлем не трогаем
  PlayerFake full=new PlayerFake();full.admin=true;full.inv=new Inv(0);full.inv.setHelmet(new ItemStack(Material.FEATHER));
  click.who=full;click.slot=15;controller.onClick(click);
  check(!AccessoryController.wearingPatch(full) && full.inv.getHelmet().getType()==Material.FEATHER,"no room, no swap");
  check(full.msg.contains("Нет свободного слота"),"and the player is told why");
  click.who=p;
  // --- menu layout: нет кнопки «назад», «снять всё» внизу по центру -------
  check(Bukkit.slots.get(31)==null,"no back button any more");
  check(Bukkit.slots.get(30)==null,"old clear-all slot is empty");
  ItemStack bottomBarrier=Bukkit.slots.get(49);
  check(bottomBarrier!=null && bottomBarrier.getType()==Material.BARRIER,"clear-all sits in the bottom row centre");
  click.slot=49;controller.onClick(click);
  check(AccessoryController.back(plugin,p)==null && AccessoryController.halo(plugin,p)==null &&
        !AccessoryController.eyepatchSelected(p),"clear all wipes back and head");
  check(!AccessoryController.wearingPatch(p),"clear all also takes the patch item off");
  // legacy halo selection (written before the head slot existed) is honoured
  p.data.set(AccessoryController.HALO,PersistentDataType.STRING,"halo");
  check(AccessoryController.halo(plugin,p)==plugin.halo,"legacy halo key still works");
  p.data.set(AccessoryController.HEAD,PersistentDataType.STRING,"eyepatch");
  check(AccessoryController.eyepatchSelected(p) && AccessoryController.halo(plugin,p)==null,"head key wins");
  // --- a broken install must never disable the whole plugin ------------------
  ElytrixFreakModelPlugin bare=new ElytrixFreakModelPlugin();bare.returnNullCommand=true;
  AccessoryController.install(bare);
  check(bare.mockCommand.executor==null,"no executor without a command");
  check(!bare.warnings.isEmpty() && bare.warnings.get(0).contains("accessories"),
        "a missing command is logged, never thrown out of onEnable");
  InventoryDragEvent drag=new InventoryDragEvent();drag.view=click.view;controller.onDrag(drag);check(drag.cancelled,"drag cancelled");
  System.out.println("Accessory GUI, permission, selection and cached tentacle spec mock tests passed");
 }
}
