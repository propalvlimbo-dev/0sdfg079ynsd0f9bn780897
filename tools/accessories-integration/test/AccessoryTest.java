package pw.elytrix.freakmodel;
import java.util.*;
import org.bukkit.*;
import org.bukkit.entity.*;
import org.bukkit.inventory.*;
import org.bukkit.persistence.*;
import org.bukkit.event.inventory.*;
import org.bukkit.event.player.*;
import org.bukkit.command.*;
import org.bukkit.plugin.*;
import org.bukkit.event.*;
import com.ticxo.modelengine.api.ModelEngineAPI;
import com.ticxo.modelengine.api.animation.BlueprintAnimation;
import com.ticxo.modelengine.api.animation.handler.AnimationHandler;
import com.ticxo.modelengine.api.animation.property.IAnimationProperty;
import com.ticxo.modelengine.api.entity.BaseEntity;
import com.ticxo.modelengine.api.entity.Dummy;
import com.ticxo.modelengine.api.lod.AnimationLODHandler;

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
 static class PlayerFake implements Player {
  final java.util.List<Entity> hidden=new java.util.ArrayList<>();World world;double px=0,py=1.6,pz=0;Location eye=new Location(null,0,1.62,0);float bodyYaw=15.0F;
  public Location getLocation(){return new Location(world,px,py,pz,bodyYaw,0);}
  public Location getEyeLocation(){eye=new Location(world,px,py+0.02,pz);return eye;}
  public float getBodyYaw(){return bodyYaw;}
  public void hideEntity(org.bukkit.plugin.Plugin plugin,Entity e){hidden.add(e);}
  Inv inv=new Inv(36);public PlayerInventory getInventory(){return inv;}boolean admin,use;String command;UUID uuid=UUID.fromString("00000000-0000-0000-0000-0000000000aa");public boolean performCommand(String c){command=c;return true;}public void closeInventory(){}Data data=new Data();String msg;public boolean hasPermission(String s){return admin || (use && s.equals(AccessoryController.USE_PERMISSION));}public Data getPersistentDataContainer(){return data;}public Inventory opened;public InventoryView openInventory(Inventory i){opened=i;return null;}public void sendMessage(String s){msg=s;}public java.util.UUID getUniqueId(){return uuid;}public boolean isOnline(){return true;}public String getName(){return "Tester";}}
 static FreakModelSpec spec(String id){return new FreakModelSpec(id,ModelKind.ANGEL_WINGS,id,List.of(),Material.FEATHER,"model",34,id,List.of(),1,0,0,1,1,2,0,0,0,0,0,0,0,0,0,0,0,false,false);}

 static class FakePassengers extends com.ticxo.modelengine.api.utils.data.tracker.CollectionDataTracker {
  final java.util.Set<Object> ids=new java.util.LinkedHashSet<>();boolean dirty;
  public boolean contains(Object v){return ids.contains(v);}
  public boolean add(Object v){return ids.add(v);}
  public void markDirty(){dirty=true;}
 }
 static com.ticxo.modelengine.api.model.PivotOverride makePivot(FakePassengers passengers){
  return new com.ticxo.modelengine.api.model.PivotOverride(java.util.UUID.randomUUID(),1,() -> new org.joml.Vector3f()){
   public void addPassenger(int id){passengers.add(id);}
   public void removePassenger(int id){passengers.ids.remove(id);}
   public com.ticxo.modelengine.api.utils.data.tracker.CollectionDataTracker getPassengers(){return passengers;}};
 }
 static class FakePivotRegistry extends com.ticxo.modelengine.api.model.PivotOverrideRegistry {
  FakePassengers passengers = new FakePassengers();
  com.ticxo.modelengine.api.model.PivotOverride pivot = makePivot(passengers);
  void simulateWornAngelRigDestroyAll(){
   passengers = new FakePassengers();
   pivot = makePivot(passengers);
  }
  public com.ticxo.modelengine.api.model.PivotOverride getOrCreate(Entity e){return pivot;}
 }

 static class FakeAnimHandler implements AnimationHandler {
  final Set<String> playing=new HashSet<>();
  final Map<String,FakeProp> props=new HashMap<>();
  int clearedStates;
  static class FakeProp implements IAnimationProperty {
   double speed; BlueprintAnimation.LoopMode loop;
   public double getSpeed(){return speed;}
   public void setSpeed(double s){speed=s;}
   public void setForceLoopMode(BlueprintAnimation.LoopMode m){loop=m;}
  }
  public void setDefaultProperty(DefaultProperty d){if("".equals(d.getAnimation()))clearedStates++;}
  public IAnimationProperty playAnimation(String anim,double li,double lo,double sp,boolean force){
   playing.add(anim);FakeProp fp=new FakeProp();fp.speed=sp;props.put(anim,fp);return fp;}
  public boolean isPlayingAnimation(String anim){return playing.contains(anim);}
  public IAnimationProperty getAnimation(String anim){return props.get(anim);}
 }

 static int nextPivotSeq = 4200;
 static class FakeActive implements com.ticxo.modelengine.api.model.ActiveModel {
  final com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint bp;boolean destroyed,canHurt=true,shadow=true,hitbox=true,lockPitch,lockYaw;float view;double scale=99;Boolean rotLocked;float lockedX,lockedY,lockedBody;com.ticxo.modelengine.api.model.PivotOverride pivot;FakeModeled owner;
  final FakeAnimHandler animHandler = new FakeAnimHandler();
  boolean rendererReady; final int pivotId = ++nextPivotSeq;
  FakeActive(com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint bp){this.bp=bp;}
  public boolean isDestroyed(){return destroyed;}public void destroy(){destroyed=true;}
  public com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint getBlueprint(){return bp;}
  public AnimationHandler getAnimationHandler(){return animHandler;}
  public void setBlockLight(int v){}public void setSkyLight(int v){}public void setCanHurt(boolean v){canHurt=v;}public void setShadowVisible(boolean v){shadow=v;}public void setHitboxVisible(boolean v){hitbox=v;}
  public void setLockPitch(boolean v){lockPitch=v;}public void setLockYaw(boolean v){lockYaw=v;}public void setViewRange(float v){view=v;}
  public void setScale(double v){scale=v;}public void setPivotOverride(com.ticxo.modelengine.api.model.PivotOverride v){pivot=v;}
  public com.ticxo.modelengine.api.model.render.ModelRenderer getModelRenderer(){
   return new com.ticxo.modelengine.api.model.render.DisplayRenderer(){
    public boolean isInitialized(){return rendererReady;}
    public void initialize(){rendererReady=true;}
    public Pivot getPivot(){return new Pivot(){
     public int getId(){return pivotId;}
     public boolean isOverridden(){return false;}
     public com.ticxo.modelengine.api.utils.data.tracker.DataTracker getPosition(){
      return new com.ticxo.modelengine.api.utils.data.tracker.DataTracker(){
       public Object get(){return new org.joml.Vector3f(0,1.6F,0);}};}};}};}
  public com.ticxo.modelengine.api.model.ModeledEntity getModeledEntity(){return owner;}
  public java.util.Optional<com.ticxo.modelengine.api.model.bone.ModelBone> getBone(String id){return java.util.Optional.empty();}
  public void setModelRotationLocked(Boolean v){rotLocked=v;}public void setLockedXHeadRot(float v){lockedX=v;}
  public void setLockedYHeadRot(float v){lockedY=v;}public void setLockedYBodyRot(float v){lockedBody=v;}}

 static class FakeModeled implements com.ticxo.modelengine.api.model.ModeledEntity {
  final Query q;final BaseEntity base;final AnimationLODHandler lod=new AnimationLODHandler(this);
  int adds,removes;boolean destroyed,baseVisible=true,modelRotLocked=true;Map<String,com.ticxo.modelengine.api.model.ActiveModel> models=new HashMap<>();float bodyYaw,headYaw,headPitch;int rotTick;
  FakeModeled(Query q,BaseEntity base){this.q=q;this.base=base;}
  public boolean isDestroyed(){return destroyed;}
  public void destroy(){destroyed=true;}
  public AnimationLODHandler getAnimationLodHandler(){return lod;}
  public void setBaseEntityVisible(boolean v){baseVisible=v;}
  public void setModelRotationLocked(boolean v){modelRotLocked=v;}
  public Optional<com.ticxo.modelengine.api.model.ActiveModel> addModel(com.ticxo.modelengine.api.model.ActiveModel m,boolean passenger){adds++;q.last=(FakeActive)m;((FakeActive)m).owner=this;models.put("active",m);return Optional.of(m);}
  public Optional<com.ticxo.modelengine.api.model.ActiveModel> removeModel(String id){removes++;com.ticxo.modelengine.api.model.ActiveModel m=models.remove("active");if(m instanceof FakeActive)((FakeActive)m).destroy();return Optional.ofNullable(m);}
  public Optional<com.ticxo.modelengine.api.model.ActiveModel> getModel(String id){return Optional.ofNullable(models.get("active"));}
  public void setYBodyRotImmediately(float v){bodyYaw=v;}public void setYHeadRotImmediately(float v){headYaw=v;}public void setXHeadRotImmediately(float v){headPitch=v;}public void setRotationTick(int t){rotTick=t;}
  public com.ticxo.modelengine.api.entity.BaseEntity getBase(){return base;}}

 static class FakeData extends com.ticxo.modelengine.api.entity.data.BukkitEntityData {
  Boolean verticalCull=true,backCull=true,blockedCull=true;Integer cullInterval;int baseRange=32;java.util.UUID paired;
  public com.ticxo.modelengine.api.nms.entity.wrapper.TrackedEntity getTracked(){
   return new com.ticxo.modelengine.api.nms.entity.wrapper.TrackedEntity(){
    public int getBaseRange(){return baseRange;}
    public void setBaseRange(int r){baseRange=r;}
    public void addForcedPairing(java.util.UUID u){paired=u;}
    public void removeForcedPairing(java.util.UUID u){}};}
  public void setVerticalCull(Boolean v){verticalCull=v;}
  public void setBackCull(Boolean v){backCull=v;}
  public void setBlockedCull(Boolean v){blockedCull=v;}
  public void setCullInterval(Integer v){cullInterval=v;}}

 static class Query {FakeActive last;FakeModeled lastEntity;int blueprints;int created;}
 static class FakeEngine implements ModelEngineAPI.Backend {
  final Query q=new Query();final Map<UUID,FakeModeled> entities=new HashMap<>();final FakePivotRegistry pivots=new FakePivotRegistry();
  public boolean noBlueprint; public boolean autoInitRenderer=false;
  public com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint blueprint(String id){q.blueprints++;return noBlueprint?null:new com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint();}
  public com.ticxo.modelengine.api.model.ModeledEntity modeledEntity(Entity e){throw new AssertionError("Ghoul accessories must use isolated Dummy BaseEntity, not raw Player entity!");}
  public com.ticxo.modelengine.api.model.ModeledEntity createModeledEntity(BaseEntity base){
   if(base instanceof Dummy<?> d) d.mockData=new FakeData();
   FakeModeled fm=new FakeModeled(q,base);q.lastEntity=fm;entities.put(base.getUUID(),fm);return fm;}
  public com.ticxo.modelengine.api.model.ModeledEntity removeModeledEntity(UUID uuid){return entities.remove(uuid);}
  public com.ticxo.modelengine.api.model.ActiveModel createActiveModel(com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint bp){
   q.created++;FakeActive fa=new FakeActive(bp);fa.rendererReady=autoInitRenderer;return fa;}
  public com.ticxo.modelengine.api.model.PivotOverrideRegistry pivots(){return pivots;}}

 static void check(boolean c,String s){if(!c)throw new AssertionError(s);}
 public static void main(String[] args){
  ElytrixFreakModelPlugin plugin=new ElytrixFreakModelPlugin();plugin.wings=spec("angel_wings");plugin.halo=spec("angel_halo");PlayerFake p=new PlayerFake();
  p.data.set(AccessoryController.BACK,PersistentDataType.STRING,"wings");p.data.set(AccessoryController.HALO,PersistentDataType.STRING,"halo");
  check(AccessoryController.back(plugin,p)==null && AccessoryController.halo(plugin,p)==null,"non-admin denied");
  p.admin=true;
  check(AccessoryController.back(plugin,p)==plugin.wings,"wings selected for WornAngelRig");
  check(AccessoryController.halo(plugin,p)==plugin.halo,"halo independent");
  // Kaneki Kagune intentionally returns null to WornAngelRig so it runs on isolated Dummy without angel dust!
  p.data.set(AccessoryController.BACK,PersistentDataType.STRING,"kaneki");
  check(AccessoryController.back(plugin,p)==null && AccessoryController.kanekiSelected(p),"kaneki routed to Dummy controller, not WornAngelRig");
  p.data.set(AccessoryController.BACK,PersistentDataType.STRING,"bad");check(AccessoryController.back(plugin,p)==null,"unknown rejected");
  p.admin=false;check(AccessoryController.halo(plugin,p)==null,"permission revocation applied");

  class PM implements PluginManager {Listener listener;java.util.Set<String> enabled=new java.util.HashSet<>();public void registerEvents(Listener l,Plugin p){listener=l;}public boolean isPluginEnabled(String n){return enabled.contains(n);}}
  PM pm=new PM();Bukkit.manager=pm;
  AccessoryController.install(plugin);AccessoryController controller=(AccessoryController)pm.listener;
  check(plugin.mockCommand.executor==controller,"executor registered");
  check(Bukkit.dispatched.isEmpty(),"no LuckPerms command when the plugin is absent");
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
  check(p.opened!=null,"hub menu visible to non-admin");
  check(Bukkit.size==54 && Bukkit.title.equals(AccessoryController.TITLE_HUB),"hub RP title");
  check(Bukkit.slots.get(20).meta.title.contains("Спина") && Bukkit.slots.get(20).meta.model.equals(new NamespacedKey("reallyworld","angel_wings")),"hub Спина card");
  check(Bukkit.slots.get(22).meta.title.contains("Шапки") && Bukkit.slots.get(22).meta.model.equals(new NamespacedKey("reallyworld","angel_halo")),"hub Шапки card");
  check(Bukkit.slots.get(24).meta.title.contains("Питомцы") && Bukkit.slots.get(24).meta.model.equals(new NamespacedKey("reallyworld","mini_me_icon")),"hub Питомцы card");
  ItemStack clearAll=Bukkit.slots.get(49);
  check(clearAll!=null && clearAll.getType()==Material.BARRIER && clearAll.meta.title.contains("Снять всё"),"clear-all button");
  check(Bukkit.slots.size()==4,"three category cards and clear-all on hub");

  // Non-admin can browse all 3 sections freely, and gets media message only when clicking an item!
  InventoryClickEvent click=new InventoryClickEvent();click.view=()->p.opened;click.who=p;
  click.slot=20;controller.onClick(click);
  check(Bukkit.title.equals(AccessoryController.TITLE_BACK),"opened Спина section");
  check(Bukkit.slots.get(30).meta.model.equals(new NamespacedKey("reallyworld","angel_wings")),"wings in Спина");
  check(Bukkit.slots.get(32).meta.model.equals(new NamespacedKey("reallyworld","kaneki_tentacles_icon")),"kaneki in Спина");
  check(Integer.valueOf(10002).equals(Bukkit.slots.get(45).meta.cmd),"back arrow CMD 10002");

  // Tab switch from Спина -> Шапки -> Питомцы -> Назад -> Hub
  click.slot=13;controller.onClick(click);
  check(Bukkit.title.equals(AccessoryController.TITLE_HATS) && Bukkit.slots.get(31).meta.model.equals(new NamespacedKey("reallyworld","angel_halo")),"halo in Шапки");
  click.slot=14;controller.onClick(click);
  check(Bukkit.title.equals(AccessoryController.TITLE_PETS),"opened Питомцы via tab");
  check(Bukkit.slots.get(30).meta.model.equals(new NamespacedKey("reallyworld","mini_me_icon")),"mini_me in Питомцы");
  check(Bukkit.slots.get(32).meta.model.equals(new NamespacedKey("reallyworld","centipede_icon")),"scolopendra in Питомцы");

  // Non-admin equip click denied with media rank hint
  p.data.remove(AccessoryController.PET);
  click.slot=30;controller.onClick(click);
  check(click.cancelled && !AccessoryController.miniMeSelected(p),"non-admin equip click denied");
  check(p.msg.contains("media"),"denial names donation rank");
  click.slot=45;controller.onClick(click);
  check(Bukkit.title.equals(AccessoryController.TITLE_HUB),"back arrow returns to hub");

  PlayerFake media=new PlayerFake();media.use=true;media.uuid=UUID.randomUUID();
  check(AccessoryController.allowed(media),"media permission unlocks menu");

  // Direct section command `/аксессуары спина`
  p.admin=true;p.data.remove(AccessoryController.HALO);p.data.remove(AccessoryController.BACK);
  controller.onCommand(p,new Command(),"аксессуары",new String[]{"спина"});
  check(Bukkit.title.equals(AccessoryController.TITLE_BACK),"direct Спина command arg");
  ModelEngineAPI.backend=null;click.slot=32;controller.onClick(click);
  check(!p.data.m.containsKey(AccessoryController.BACK),"missing engine denied");

  FakeEngine fe=new FakeEngine();ModelEngineAPI.backend=fe;
  Bukkit.online.clear();Bukkit.online.add(p);

  // --- 1. Kaneki Ken's Rinkaku Kagune (Спина slot 32) on isolated Dummy ---
  click.slot=32;controller.onClick(click);
  check(AccessoryController.kanekiSelected(p) && AccessoryController.wearingKaneki(p),"kaneki kagune spawned");
  check(AccessoryController.kanekiAnimating(p),"kaneki kagune playing living 'idle' loop");
  FakeActive kanekiModel=fe.q.last;
  kanekiModel.rendererReady=true;
  AccessoryController.animatePets();
  check(AccessoryController.kanekiAttached(p) && fe.pivots.passengers.contains(kanekiModel.pivotId),"kaneki pivot mounted");

  // --- 2. Equip Dancing Mini-Me Shoulder Pet (Питомцы slot 30) alongside Kaneki Kagune ---
  click.slot=14;controller.onClick(click); // switch to Питомцы
  click.slot=30;controller.onClick(click); // equip Мини-скин!
  check(AccessoryController.miniMeSelected(p) && AccessoryController.wearingMiniMe(p),"dancing mini-me spawned alongside kagune");
  check(AccessoryController.miniMeAnimating(p),"mini-me playing dance 'idle' loop");
  check(AccessoryController.wearingKaneki(p),"kagune still active alongside mini-me");
  check(!fe.entities.containsKey(p.uuid) && fe.entities.size()==2,"two isolated Dummy entities, zero player UUID collision");
  FakeActive miniModel=fe.q.last;
  miniModel.rendererReady=true;
  AccessoryController.animatePets();
  check(AccessoryController.miniMeAttached(p) && fe.pivots.passengers.contains(miniModel.pivotId),"mini-me pivot mounted");

  // --- 3. Direct Pet Swap in Питомцы: Мини-скин (slot 30) -> Сколопендра Гуля (slot 32) ---
  click.slot=32;controller.onClick(click);
  check(!AccessoryController.wearingMiniMe(p) && miniModel.destroyed,"old mini-me Dummy cleanly destroyed on pet swap");
  check(AccessoryController.centipedeSelected(p) && AccessoryController.wearingCentipede(p),"scolopendra spawned cleanly");
  check(AccessoryController.wearingKaneki(p) && fe.entities.size()==2,"kagune untouched during pet swap");
  FakeModeled centEntity=fe.q.lastEntity;
  FakeActive centModel=fe.q.last;
  check(centModel.scale==1.0D,"exact 1.0 full-body scale");
  check(Boolean.FALSE.equals(centEntity.lod.getEnabled()),"LOD disabled for smooth 20 TPS animation");
  check(Boolean.FALSE.equals(centModel.rotLocked),"model follows torso rotation");
  FakeData engineData=(FakeData)centEntity.getBase().getData();
  check(Boolean.FALSE.equals(engineData.verticalCull) && Boolean.FALSE.equals(engineData.backCull) && Boolean.FALSE.equals(engineData.blockedCull),"culling disabled");
  check(p.uuid.equals(engineData.paired) && engineData.baseRange>=96,"owner force-paired and range=96");
  check(AccessoryController.centipedeAnimating(p),"scolopendra playing living 'idle' loop");
  centModel.rendererReady=true;
  AccessoryController.animatePets();
  check(AccessoryController.centipedeAttached(p) && fe.pivots.passengers.contains(centModel.pivotId),"scolopendra pivot mounted");

  // Swap back to Мини-скин (slot 30) so we test PivotOverride wipe & teleport survival with Мини-скин!
  click.slot=30;controller.onClick(click);
  check(AccessoryController.wearingMiniMe(p) && !AccessoryController.wearingCentipede(p) && centModel.destroyed,"swapped back to mini-me cleanly");
  FakeModeled miniEntity=fe.q.lastEntity;
  miniModel=fe.q.last;
  miniModel.rendererReady=true;
  AccessoryController.animatePets();

  // --- 4. Simulate WornAngelRig.destroyAll() wiping PivotOverrideRegistry ---
  fe.pivots.simulateWornAngelRigDestroyAll();
  check(!fe.pivots.passengers.contains(miniModel.pivotId) && !fe.pivots.passengers.contains(kanekiModel.pivotId),"old pivot wiped");
  AccessoryController.animatePets();
  check(fe.pivots.passengers.contains(miniModel.pivotId) && fe.pivots.passengers.contains(kanekiModel.pivotId),
        "both mini-me & kaneki kagune automatically re-bind to new PivotOverride!");

  // --- 5. Packet-level short PlayerMoveEvent updates torso yBodyRot immediately with 0 pitch ---
  controller.onMove(new PlayerMoveEvent(p, new Location(p.world, 1.0, 1.6, 2.0, -72.5F, 45.0F)));
  check(Math.abs(miniEntity.bodyYaw - (-72.5F)) < 0.01F,"instant packet yBodyRot sync");
  check(miniEntity.headPitch == 0.0F && miniEntity.rotTick == -1,"zero camera pitch tilt & instant rotationTick=-1");

  // --- 6. TELEPORT SURVIVAL TEST (> 64-block /rtp teleport!) ---
  fe.autoInitRenderer=true;
  int oldMiniPivot = miniModel.pivotId;
  int oldKanekiPivot = kanekiModel.pivotId;
  p.px = 1500.0; p.py = 70.0; p.pz = -920.0; p.bodyYaw = 90.0F;
  controller.onTeleport(new PlayerTeleportEvent(p, p.getLocation()));
  check(!AccessoryController.wearingMiniMe(p) && !AccessoryController.wearingKaneki(p) && fe.entities.isEmpty(),
        "stale virtual entities cleanly destroyed on teleport");
  AccessoryController.animatePets(); // tick +1
  AccessoryController.animatePets(); // tick +2 -> automatic fresh respawn at destination!
  check(AccessoryController.wearingMiniMe(p) && AccessoryController.wearingKaneki(p),
        "both dancing mini-me and kaneki kagune automatically respawned after teleport!");
  check(AccessoryController.miniMeAttached(p) && AccessoryController.kanekiAttached(p),
        "fresh pivot entities mounted onto PivotOverride at destination!");
  check(!fe.pivots.passengers.contains(oldMiniPivot) && !fe.pivots.passengers.contains(oldKanekiPivot),
        "stale pre-teleport passenger IDs removed");
  check(fe.pivots.passengers.ids.size() == 2,"new post-teleport passenger IDs active");

  // --- 7. Switching to Angel Wings (Спина slot 30) cleanly removes Kaneki Dummy while keeping Mini-Me ---
  click.slot=12;controller.onClick(click); // tab to Спина
  click.slot=30;controller.onClick(click); // equip Angel Wings
  check(!AccessoryController.wearingKaneki(p) && AccessoryController.back(plugin,p)==plugin.wings,"wings replace kaneki cleanly");
  check(AccessoryController.wearingMiniMe(p) && fe.entities.size()==1,"mini-me remains untouched alongside wings");

  // --- 8. Also equip Halo in Шапки (slot 31) -> Wings + Halo + Mini-Me all 3 active together! ---
  click.slot=13;controller.onClick(click); // tab to Шапки
  click.slot=31;controller.onClick(click); // equip Halo
  check(AccessoryController.halo(plugin,p)==plugin.halo && AccessoryController.back(plugin,p)==plugin.wings && AccessoryController.wearingMiniMe(p),
        "Спина (Wings) + Шапки (Halo) + Питомцы (Mini-Me) all active simultaneously!");

  // --- 9. Clear All (slot 49) ---
  click.slot=49;controller.onClick(click);
  check(!AccessoryController.wearingMiniMe(p) && AccessoryController.back(plugin,p)==null && AccessoryController.halo(plugin,p)==null && fe.entities.isEmpty(),
        "clear-all removes back, hat, and pet cleanly");

  // --- 10. Quit cleanup ---
  click.slot=14;controller.onClick(click); // Питомцы
  click.slot=30;controller.onClick(click); // Mini-Me
  click.slot=12;controller.onClick(click); // Спина
  click.slot=32;controller.onClick(click); // Kaneki
  check(AccessoryController.wearingMiniMe(p) && AccessoryController.wearingKaneki(p),"both equipped before quit");
  controller.onQuit(new PlayerQuitEvent(p));
  check(!AccessoryController.wearingMiniMe(p) && !AccessoryController.wearingKaneki(p) && fe.entities.isEmpty(),"quit releases all rigs without leak");

  ElytrixFreakModelPlugin bare=new ElytrixFreakModelPlugin();bare.returnNullCommand=true;
  AccessoryController.install(bare);
  check(bare.mockCommand.executor==null && !bare.warnings.isEmpty(),"missing command logged safely");
  InventoryDragEvent drag=new InventoryDragEvent();drag.view=click.view;controller.onDrag(drag);check(drag.cancelled,"drag cancelled");
  System.out.println("All v3.13.0 tests passed: 3-section menu (Спина/Шапки/Питомцы), Dancing Mini-Me shoulder pet, Scolopendra, Kaneki Kagune & teleport recovery!");
 }
}
