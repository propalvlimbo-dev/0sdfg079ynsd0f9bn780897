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
 static class FakeWorld implements World {
  final java.util.List<String> playedSounds=new java.util.ArrayList<>();
  public Collection<Entity> getNearbyEntities(Location location,double x,double y,double z){return List.of();}
  public void playSound(Location location,String sound,float volume,float pitch){playedSounds.add(sound);}
 }
 static class PlayerFake implements Player {
  final FakeWorld fakeWorld=new FakeWorld();
  final java.util.List<Entity> hidden=new java.util.ArrayList<>();World world=fakeWorld;double px=0,py=1.6,pz=0;Location eye=new Location(null,0,1.62,0);float bodyYaw=15.0F,pitch=0.0F;boolean sneaking;
  public Location getLocation(){return new Location(world,px,py,pz,bodyYaw,pitch);}
  public Location getEyeLocation(){eye=new Location(world,px,py+0.02,pz);return eye;}
  public float getBodyYaw(){return bodyYaw;}
  public boolean isSneaking(){return sneaking;}
  public void hideEntity(org.bukkit.plugin.Plugin plugin,Entity e){hidden.add(e);}
  Inv inv=new Inv(36);public PlayerInventory getInventory(){return inv;}boolean admin,use;String name="Tester";String command;UUID uuid=UUID.fromString("00000000-0000-0000-0000-0000000000aa");public boolean performCommand(String c){command=c;return true;}public void closeInventory(){}Data data=new Data();String msg;final java.util.List<String> messages=new java.util.ArrayList<>();public boolean hasPermission(String s){return admin && s.equals(AccessoryController.ADMIN_PERMISSION);}public Data getPersistentDataContainer(){return data;}public Inventory opened;public InventoryView openInventory(Inventory i){opened=i;return null;}public void sendMessage(String s){msg=s;messages.add(s);}public java.util.UUID getUniqueId(){return uuid;}public boolean isOnline(){return true;}public String getName(){return name;}}
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
  public void forceStopAnimation(String anim){playing.remove(anim);props.remove(anim);}
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
 public static void main(String[] args) throws Exception {
  java.nio.file.Path testDir = java.nio.file.Files.createTempDirectory("elytrix-acc-store-");
  ElytrixFreakModelPlugin plugin=new ElytrixFreakModelPlugin();
  plugin.mockDataFolder = testDir.toFile();
  plugin.wings=spec("angel_wings");plugin.halo=spec("angel_halo");
  PlayerFake p=new PlayerFake();
  p.admin=false; // REGULAR PLAYER (zero permissions!)

  // Mock PlayerPoints Риллики backend
  final Map<UUID,Integer> wallet = new HashMap<>();
  AccessoryController.pointsBackend = new AccessoryController.PointsBackend() {
   public boolean isAvailable() { return true; }
   public int look(UUID u) { return wallet.getOrDefault(u, 0); }
   public String lookFormatted(UUID u) { return AccessoryController.formatRilliki(look(u)); }
   public boolean take(UUID u, int amount) {
    int cur = look(u);
    if (amount <= 0 || cur < amount) return false;
    wallet.put(u, cur - amount);
    return true;
   }
  };

  // Unpurchased selections in PDC must NEVER render without ownership!
  p.data.set(AccessoryController.BACK,PersistentDataType.STRING,"wings");
  p.data.set(AccessoryController.HALO,PersistentDataType.STRING,"halo");
  check(AccessoryController.back(plugin,p)==null && AccessoryController.halo(plugin,p)==null,
        "unpurchased wings & halo cannot be worn without buying first");
  p.data.remove(AccessoryController.BACK);
  p.data.remove(AccessoryController.HALO);

  class PM implements PluginManager {Listener listener;java.util.Set<String> enabled=new java.util.HashSet<>();public void registerEvents(Listener l,Plugin p){listener=l;}public boolean isPluginEnabled(String n){return enabled.contains(n);}}
  PM pm=new PM();Bukkit.manager=pm;
  AccessoryController.install(plugin);AccessoryController controller=(AccessoryController)pm.listener;
  check(plugin.mockCommand.executor==controller,"executor registered");
  check(Bukkit.dispatched.isEmpty(),"no media LuckPerms gate dispatched — open to everyone!");

  // Regular player opens `/аксессуары` with 1 500 ꐃ
  wallet.put(p.uuid, 1500);
  check(controller.onCommand(p,new Command(),"аксессуары",new String[0]),"command handled for regular player");
  check(p.opened!=null,"hub menu visible to everyone");
  check(Bukkit.size==54 && Bukkit.title.equals(AccessoryController.TITLE_HUB),"hub RP title");
  check(Bukkit.slots.get(19).meta.title.contains("Спина") && Bukkit.slots.get(19).meta.model.equals(new NamespacedKey("reallyworld","angel_wings")),"hub Спина card");
  check(Bukkit.slots.get(21).meta.title.contains("Шапки") && Bukkit.slots.get(21).meta.model.equals(new NamespacedKey("reallyworld","angel_halo")),"hub Шапки card");
  check(Bukkit.slots.get(23).meta.title.contains("Питомцы") && Bukkit.slots.get(23).meta.model.equals(new NamespacedKey("reallyworld","mini_me_icon")),"hub Питомцы card");
  check(Bukkit.slots.get(25).meta.title.contains("Ауры") && Bukkit.slots.get(25).meta.model.equals(new NamespacedKey("reallyworld","heart_aura_icon")),"hub Ауры card");
  ItemStack clearAll=Bukkit.slots.get(49);
  check(clearAll!=null && clearAll.getType()==Material.BARRIER && clearAll.meta.title.contains("Снять всё"),"clear-all button");
  ItemStack infoClock=Bukkit.slots.get(53);
  check(infoClock!=null && infoClock.getType()==Material.CLOCK && Integer.valueOf(100010).equals(infoClock.meta.cmd)
        && infoClock.meta.lore.stream().anyMatch(l -> l.contains("1 500") && l.contains("ꐃ")),
        "slot 53 ИНФОРМАЦИЯ clock shows live Риллики balance with ꐃ glyph just like /shop!");
  check(Bukkit.slots.size()==6,"four category cards, clear-all, and /shop balance info on hub");

  // Browse all 3 sections and verify exact Риллики prices in lore!
  InventoryClickEvent click=new InventoryClickEvent();click.view=()->p.opened;click.who=p;
  click.slot=19;controller.onClick(click);
  check(Bukkit.title.equals(AccessoryController.TITLE_BACK) && Bukkit.title.contains("ꏧ"),
        "opened Спина section with the 3-slot ꏧ RP frame");
  check(Bukkit.slots.get(29).meta.model.equals(new NamespacedKey("reallyworld","angel_wings")),"wings in Спина");
  check(Bukkit.slots.get(29).meta.lore.stream().anyMatch(l -> l.contains("6000") && l.contains("ꐃ")),"Ангельские крылья priced at exact 6000 Рилликов!");
  check(Bukkit.slots.get(31).meta.model.equals(new NamespacedKey("reallyworld","kaneki_tentacles_icon")),"kaneki in Спина");
  check(Bukkit.slots.get(31).meta.lore.stream().anyMatch(l -> l.contains("7500") && l.contains("ꐃ")),"Щупальца Канэки priced at 7500 Рилликов!");
  check(Bukkit.slots.get(33).meta.title.contains("Крылья Зевса")
        && Bukkit.slots.get(33).meta.model.equals(new NamespacedKey("reallyworld","zeus_wings_icon")),
        "Крылья Зевса in Спина slot 33 with zeus_wings_icon!");
  check(Bukkit.slots.get(33).meta.lore.stream().anyMatch(l -> l.contains("8000") && l.contains("ꐃ")),"Крылья Зевса priced at 8000 Рилликов!");
  check(Integer.valueOf(10002).equals(Bukkit.slots.get(45).meta.cmd),"back arrow CMD 10002");

  // Tab switch Спина -> Шапки -> Питомцы
  click.slot=12;controller.onClick(click);
  check(Bukkit.title.equals(AccessoryController.TITLE_HATS) && Bukkit.title.contains("ꏧ"),
        "Шапки uses 3-slot ꏧ RP frame at slots 29, 31 & 33");
  check(Bukkit.slots.get(29).meta.model.equals(new NamespacedKey("reallyworld","angel_halo")),"halo in Шапки slot 29");
  check(Bukkit.slots.get(29).meta.lore.stream().anyMatch(l -> l.contains("3500") && l.contains("ꐃ")),"Божественный нимб priced at 3500 Рилликов!");
  check(Bukkit.slots.get(31).meta.title.contains("Круг Сатаны")
        && Bukkit.slots.get(31).meta.model.equals(new NamespacedKey("reallyworld","satan_circle_icon")),
        "Круг Сатаны in Шапки slot 31 with satan_circle_icon!");
  check(Bukkit.slots.get(31).meta.lore.stream().anyMatch(l -> l.contains("4500") && l.contains("ꐃ")),"Круг Сатаны priced at 4500 Рилликов!");
  check(Bukkit.slots.get(33).meta.title.contains("Дождевое облако")
        && Bukkit.slots.get(33).meta.model.equals(new NamespacedKey("reallyworld","lightning_hat_icon")),
        "Дождевое облако in Шапки slot 33 with lightning_hat_icon!");
  check(Bukkit.slots.get(33).meta.lore.stream().anyMatch(l -> l.contains("4000") && l.contains("ꐃ")),"Дождевое облако priced at 4000 Рилликов!");
  click.slot=14;controller.onClick(click);
  check(Bukkit.title.equals(AccessoryController.TITLE_PETS) && Bukkit.title.contains("ꏨ"),"opened Питомцы via tab with 4-slot ꏨ content glyph");
  check(Bukkit.slots.get(28).meta.title.contains("Мини-Роузи") && Bukkit.slots.get(28).meta.lore.stream().anyMatch(l -> l.contains("2000") && l.contains("ꐃ")),
        "Мини-Роузи priced at exact 2000 Рилликов!");
  check(Bukkit.slots.get(30).meta.title.contains("Милый котёнок") && Bukkit.slots.get(30).meta.lore.stream().anyMatch(l -> l.contains("2500") && l.contains("ꐃ")),
        "Милый котёнок priced at 2500 Рилликов!");
  check(Bukkit.slots.get(32).meta.title.contains("Меллстрой") && Bukkit.slots.get(32).meta.lore.stream().anyMatch(l -> l.contains("5000") && l.contains("ꐃ")),
        "Меллстрой priced at 5000 Рилликов!");
  check(Bukkit.slots.get(34).meta.lore.stream().anyMatch(l -> l.contains("4500") && l.contains("ꐃ")),
        "Сколопендра Гуля priced at 4500 Рилликов!");

  FakeEngine fe=new FakeEngine();ModelEngineAPI.backend=fe;
  Bukkit.online.clear();Bukkit.online.add(p);

  // Attempt to buy Мини-Роузи (2000 ꐃ) with only 1500 ꐃ -> denied like /shop, 0 deducted!
  click.slot=28;controller.onClick(click);
  check(click.cancelled && wallet.get(p.uuid)==1500 && !AccessoryController.owns(p, AccessoryController.AccessoryItem.MINI_ME),
        "insufficient Риллики denied cleanly without deducting balance");
  check(p.msg.contains("Недостаточно рилликов!"),"exact /shop insufficient Риллики message");

  // Top up balance to 51 500 ꐃ so our regular player can purchase all 10 accessories (total = 47 500 ꐃ -> 4 000 ꐃ left)!
  wallet.put(p.uuid, 57000);

  // Direct section command `/аксессуары спина` & missing blueprint safety check BEFORE charging Риллики!
  controller.onCommand(p,new Command(),"аксессуары",new String[]{"спина"});
  check(Bukkit.title.equals(AccessoryController.TITLE_BACK),"direct Спина command arg");
  ModelEngineAPI.backend=null;click.slot=31;controller.onClick(click);
  check(wallet.get(p.uuid)==57000 && !AccessoryController.owns(p, AccessoryController.AccessoryItem.KANEKI),
        "missing blueprint never charges Риллики!");
  ModelEngineAPI.backend=fe;

  // --- 1. Regular player BUYS Kaneki Ken's Rinkaku Kagune (7500 ꐃ, Спина slot 31 -> 49500 ꐃ) ---
  p.messages.clear();
  click.slot=31;controller.onClick(click);
  check(wallet.get(p.uuid)==49500 && AccessoryController.owns(p, AccessoryController.AccessoryItem.KANEKI),
        "7500 Рилликов deducted and Kaneki permanently unlocked!");
  check(p.messages.stream().anyMatch(m -> m.contains("Покупка успешно совершена!")),"exact /shop purchase message sent");
  check(AccessoryController.kanekiSelected(p) && AccessoryController.wearingKaneki(p),"kaneki kagune immediately equipped on purchase");
  check(AccessoryController.kanekiAnimating(p),"kaneki kagune playing living 'idle' loop");
  // Unequip & re-equip Kaneki -> 0 Рилликов charged!
  click.slot=31;controller.onClick(click);
  check(!AccessoryController.wearingKaneki(p) && wallet.get(p.uuid)==49500,"unequipping purchased item is free");
  click.slot=31;controller.onClick(click);
  check(AccessoryController.wearingKaneki(p) && wallet.get(p.uuid)==49500,"re-equipping purchased item is 100% free forever!");
  FakeActive kanekiModel=fe.q.last;
  kanekiModel.rendererReady=true;
  AccessoryController.animatePets();
  check(AccessoryController.kanekiAttached(p) && fe.pivots.passengers.contains(kanekiModel.pivotId),"kaneki pivot mounted");

  // --- 2. Buy & Equip Мини-Роузи (2000 ꐃ, Питомцы slot 28 -> 47500 ꐃ) alongside Kaneki Kagune ---
  click.slot=14;controller.onClick(click); // switch to Питомцы
  click.slot=28;controller.onClick(click); // buy & equip Мини-Роузи!
  check(wallet.get(p.uuid)==47500 && AccessoryController.owns(p, AccessoryController.AccessoryItem.MINI_ME),
        "Мини-Роузи bought for exact 2000 Рилликов!");
  check(p.msg.contains("Мини-Роузи") && !p.msg.contains("Мини-скин"),"chat message says Мини-Роузи");
  check(AccessoryController.miniMeSelected(p) && AccessoryController.wearingMiniMe(p),"dancing Мини-Роузи spawned alongside kagune");
  check(AccessoryController.miniMeAnimating(p),"Мини-Роузи playing dance 'idle' loop");
  check(AccessoryController.wearingKaneki(p),"kagune still active alongside Мини-Роузи");
  check(!fe.entities.containsKey(p.uuid) && fe.entities.size()==2,"two isolated Dummy entities, zero player UUID collision");
  FakeActive miniModel=fe.q.last;
  miniModel.rendererReady=true;
  AccessoryController.animatePets();
  check(AccessoryController.miniMeAttached(p) && fe.pivots.passengers.contains(miniModel.pivotId),"Мини-Роузи pivot mounted");

  // --- 2b. Buy & Swap to Милый котёнок (2500 ꐃ, slot 30 -> 45000 ꐃ) ---
  click.slot=30;controller.onClick(click);
  check(wallet.get(p.uuid)==45000 && AccessoryController.owns(p, AccessoryController.AccessoryItem.KITTEN),"bought kitten for 2500 ꐃ");
  check(!AccessoryController.wearingMiniMe(p) && miniModel.destroyed,"old Мини-Роузи Dummy cleanly destroyed on swap to kitten");
  check(AccessoryController.kittenSelected(p) && AccessoryController.wearingKitten(p) && AccessoryController.kittenAnimating(p),"Милый котёнок spawned & animating");
  FakeActive kittenModel=fe.q.last;
  kittenModel.rendererReady=true;
  AccessoryController.animatePets();
  check(AccessoryController.kittenAttached(p) && fe.pivots.passengers.contains(kittenModel.pivotId),"kitten pivot mounted");

  // --- 2c. Buy & Swap to Меллстрой (5000 ꐃ, slot 32 -> 40000 ꐃ) + 3D Badge Animations & Real Voice! ---
  p.messages.clear();
  p.fakeWorld.playedSounds.clear();
  click.slot=32;controller.onClick(click);
  check(wallet.get(p.uuid)==40000 && AccessoryController.owns(p, AccessoryController.AccessoryItem.MELLSTROY),"bought Mellstroy for 5000 ꐃ");
  check(!AccessoryController.wearingKitten(p) && kittenModel.destroyed,"old kitten Dummy cleanly destroyed on swap to Mellstroy");
  check(AccessoryController.mellstroySelected(p) && AccessoryController.wearingMellstroy(p) && AccessoryController.mellstroyAnimating(p),"Меллстрой spawned & animating");
  check(p.messages.size()==2 && p.messages.get(0).contains("Покупка успешно совершена!") && p.messages.get(1).contains("Меллстрой выскочил на плечо"),
        "purchase confirmation + single GUI equip status message sent (zero chat quote spam!)");
  FakeActive mellModel=fe.q.last;
  check("say_svet".equals(AccessoryController.mellstroyLastEmote(p)) && mellModel.animHandler.isPlayingAnimation("say_svet"),
        "Mellstroy immediately triggers in-model 3D 'say_svet' pop-up badge animation");
  check("reallyworld:mellstroy.privet".equals(AccessoryController.mellstroyLastSound(p))
        && p.fakeWorld.playedSounds.equals(List.of("reallyworld:mellstroy.privet")),
        "Mellstroy immediately plays real Ogg Vorbis greeting voice sound");
  mellModel.rendererReady=true;
  AccessoryController.animatePets();
  check(AccessoryController.mellstroyAttached(p) && fe.pivots.passengers.contains(mellModel.pivotId),"Mellstroy pivot mounted");

  // Verify periodic 3D pop-up badge + voice cycles NEVER write to chat, stop previous say_*, and never repeat back-to-back!
  p.messages.clear();
  String prevEmote = AccessoryController.mellstroyLastEmote(p);
  java.util.Set<String> seenEmotes = new java.util.LinkedHashSet<>();
  seenEmotes.add(prevEmote);
  for(int i=0;i<14;i++){
   AccessoryController.forceNextEmoteDue(p);
   AccessoryController.animatePets();
   String nextEmote = AccessoryController.mellstroyLastEmote(p);
   check(nextEmote!=null && !nextEmote.equals(prevEmote),"periodic Mellstroy 3D emote rotated without consecutive duplicate");
   check(mellModel.animHandler.isPlayingAnimation(nextEmote) && !mellModel.animHandler.isPlayingAnimation(prevEmote),
         "new 3D badge animation active and previous say_* cleanly stopped");
   seenEmotes.add(nextEmote);
   prevEmote = nextEmote;
  }
  check(p.messages.isEmpty(),"ZERO chat messages ever sent during periodic Mellstroy emotes!");
  check(seenEmotes.size()>=4 && p.fakeWorld.playedSounds.size()==15,"multiple distinct 3D badge animations & real voice clips played");

  // --- 3. Buy & Swap to Сколопендра Гуля (4500 ꐃ, slot 34 -> 35500 ꐃ) ---
  click.slot=34;controller.onClick(click);
  check(wallet.get(p.uuid)==35500 && AccessoryController.owns(p, AccessoryController.AccessoryItem.CENTIPEDE),"bought scolopendra for 4500 ꐃ");
  check(!AccessoryController.wearingMellstroy(p) && mellModel.destroyed,"old Mellstroy Dummy cleanly destroyed on pet swap");
  check(AccessoryController.centipedeSelected(p) && AccessoryController.wearingCentipede(p),"scolopendra spawned cleanly");
  check(AccessoryController.wearingKaneki(p) && fe.entities.size()==2,"kagune untouched during pet swap");
  FakeModeled centEntity=fe.q.lastEntity;
  FakeActive centModel=fe.q.last;
  check(centModel.scale==1.0D,"exact 1.0 full-body scale");
  check(Boolean.FALSE.equals(centEntity.lod.getEnabled()),"LOD disabled for smooth 20 TPS animation");
  check(Boolean.FALSE.equals(centModel.rotLocked),"model follows torso rotation");
  FakeData engineData=(FakeData)centEntity.getBase().getData();
  check(Boolean.FALSE.equals(engineData.verticalCull) && Boolean.FALSE.equals(engineData.backCull) && Boolean.FALSE.equals(engineData.blockedCull),"culling disabled");
  check(p.uuid.equals(engineData.paired) && engineData.baseRange>=48,"owner force-paired and range=48");
  check(AccessoryController.centipedeAnimating(p),"scolopendra playing living 'idle' loop");
  centModel.rendererReady=true;
  AccessoryController.animatePets();
  check(AccessoryController.centipedeAttached(p) && fe.pivots.passengers.contains(centModel.pivotId),"scolopendra pivot mounted");

  // Free re-equip swap back to Меллстрой (slot 32) -> 0 Рилликов deducted (still 22000 ꐃ)!
  p.messages.clear();
  click.slot=32;controller.onClick(click);
  check(wallet.get(p.uuid)==35500 && p.messages.size()==1,"re-equipping already owned Mellstroy charges 0 Рилликов");
  check(AccessoryController.wearingMellstroy(p) && !AccessoryController.wearingCentipede(p) && centModel.destroyed,"swapped to Mellstroy cleanly");
  FakeModeled mellEntity=fe.q.lastEntity;
  mellModel=fe.q.last;
  mellModel.rendererReady=true;
  AccessoryController.animatePets();

  // --- 3a. Buy & Equip NEW Круг Сатаны (4500 ꐃ, Шапки slot 31 -> 31000 ꐃ) alongside Kaneki + Меллстрой! ---
  click.slot=12;controller.onClick(click); // switch to Шапки
  click.slot=31;controller.onClick(click); // buy & equip Круг Сатаны!
  check(wallet.get(p.uuid)==31000 && AccessoryController.owns(p, AccessoryController.AccessoryItem.SATAN_CIRCLE),
        "Круг Сатаны bought for exact 4500 Рилликов!");
  check(AccessoryController.satanCircleSelected(p) && AccessoryController.wearingSatanCircle(p) && AccessoryController.satanCircleAnimating(p),
        "Круг Сатаны Dummy spawned right above the head & spinning the seamless 'idle' pentagram loop!");
  FakeModeled satanEntity=fe.q.lastEntity;
  FakeActive satanModel=fe.q.last;
  check(satanModel.lockPitch && mellModel.lockPitch && kanekiModel.lockPitch,
        "Круг Сатаны stays pitch-locked (lockPitch=true) so the pentagram halo never tilts off the head!");
  satanModel.rendererReady=true;
  AccessoryController.animatePets();
  check(AccessoryController.satanCircleAttached(p) && fe.pivots.passengers.contains(satanModel.pivotId),
        "Круг Сатаны pivot mounted on player PivotOverride");
  // Test nimbus-style head tracking: the circle follows every horizontal head turn on the exact packet tick!
  controller.onMove(new PlayerMoveEvent(p, new Location(p.world, 0.5, 1.6, 0.5, 128.0F, 35.0F)));
  check(Math.abs(satanEntity.bodyYaw - 128.0F) < 0.01F && Math.abs(satanEntity.headYaw - 128.0F) < 0.01F
        && Math.abs(satanEntity.headPitch) < 0.01F && satanEntity.rotTick == -1,
        "Круг Сатаны follows a 128 deg head turn with 0-tick lag while staying perfectly level!");
  controller.onMove(new PlayerMoveEvent(p, new Location(p.world, 0.5, 1.6, 0.5, -42.0F, -55.0F)));
  check(Math.abs(satanEntity.bodyYaw - (-42.0F)) < 0.01F && Math.abs(satanEntity.headYaw - (-42.0F)) < 0.01F
        && Math.abs(satanEntity.headPitch) < 0.01F && satanEntity.rotTick == -1,
        "Круг Сатаны follows a -42 deg head turn while looking up (-55 deg) without tilting off the head!");

  // --- 3b. Buy & Swap to Дождевое облако (4000 ꐃ, Шапки slot 33 -> 27000 ꐃ) -> cleanly replaces Круг Сатаны! ---
  click.slot=33;controller.onClick(click); // buy & equip Дождевое облако!
  check(wallet.get(p.uuid)==27000 && AccessoryController.owns(p, AccessoryController.AccessoryItem.LIGHTNING_HAT),
        "Дождевое облако bought for exact 4000 Рилликов!");
  check(!AccessoryController.wearingSatanCircle(p) && satanModel.destroyed,
        "old Круг Сатаны Dummy cleanly destroyed on swap to Дождевое облако");
  check(AccessoryController.lightningHatSelected(p) && AccessoryController.wearingLightningHat(p),
        "Дождевое облако Dummy spawned above head alongside Kaneki + Mellstroy!");
  check(AccessoryController.halo(plugin,p)==null,"WornAngelRig halo is null while wearing Дождевое облако");
  check(AccessoryController.lightningHatAnimating(p)
        && !fe.q.last.animHandler.isPlayingAnimation("strike"),
        "Дождевое облако plays ONLY the seamless 'idle' rain loop (no lightning strike animation left)!");
  FakeModeled lightningEntity=fe.q.lastEntity;
  FakeActive lightningModel=fe.q.last;
  check(lightningModel.lockPitch,"Дождевое облако keeps lockPitch=true so the cloud stays level overhead!");
  lightningModel.rendererReady=true;
  AccessoryController.animatePets();
  check(AccessoryController.lightningHatAttached(p) && fe.pivots.passengers.contains(lightningModel.pivotId),
        "Дождевое облако pivot mounted on player PivotOverride");
  check(fe.entities.size()==3,"all 3 isolated Dummy rigs (Kaneki + Дождевое облако + Меллстрой) active simultaneously!");

  // Arm swing must stay a no-op for the raincloud (no strike animation any more, tracker still notified)!
  controller.onArmSwing(new PlayerAnimationEvent(p));
  check(AccessoryController.lightningHatAnimating(p) && !lightningModel.animHandler.isPlayingAnimation("strike"),
        "arm swing never fires a removed 'strike' animation — the cloud just keeps raining!");

  // --- 4. Simulate WornAngelRig.destroyAll() wiping PivotOverrideRegistry ---
  fe.pivots.simulateWornAngelRigDestroyAll();
  check(!fe.pivots.passengers.contains(mellModel.pivotId)
        && !fe.pivots.passengers.contains(kanekiModel.pivotId)
        && !fe.pivots.passengers.contains(lightningModel.pivotId),"old pivot wiped");
  AccessoryController.animatePets();
  check(fe.pivots.passengers.contains(mellModel.pivotId)
        && fe.pivots.passengers.contains(kanekiModel.pivotId)
        && fe.pivots.passengers.contains(lightningModel.pivotId),
        "Mellstroy, Kaneki kagune & Грозовая молния all automatically re-bind to new PivotOverride!");

  // --- 5. Packet-level short PlayerMoveEvent updates torso yBodyRot & hat head yaw immediately with 0 pitch ---
  controller.onMove(new PlayerMoveEvent(p, new Location(p.world, 1.0, 1.6, 2.0, -72.5F, 45.0F)));
  check(Math.abs(mellEntity.bodyYaw - (-72.5F)) < 0.01F,"instant packet yBodyRot sync");
  check(Math.abs(lightningEntity.bodyYaw - (-72.5F)) < 0.01F && lightningEntity.headPitch == 0.0F,
        "Грозовая молния follows horizontal head yaw with 0 camera pitch tilt");
  check(mellEntity.headPitch == 0.0F && mellEntity.rotTick == -1,"zero camera pitch tilt & instant rotationTick=-1");

  // --- 6. TELEPORT SURVIVAL TEST (> 64-block /rtp teleport!) ---
  fe.autoInitRenderer=true;
  int oldMellPivot = mellModel.pivotId;
  int oldKanekiPivot = kanekiModel.pivotId;
  int oldLightningPivot = lightningModel.pivotId;
  p.px = 1500.0; p.py = 70.0; p.pz = -920.0; p.bodyYaw = 90.0F;
  controller.onTeleport(new PlayerTeleportEvent(p, p.getLocation()));
  check(!AccessoryController.wearingMellstroy(p) && !AccessoryController.wearingKaneki(p)
        && !AccessoryController.wearingLightningHat(p) && fe.entities.isEmpty(),
        "stale virtual entities cleanly destroyed on teleport");
  AccessoryController.animatePets(); // tick +1
  AccessoryController.animatePets(); // tick +2 -> automatic fresh respawn at destination!
  check(AccessoryController.wearingMellstroy(p) && AccessoryController.wearingKaneki(p)
        && AccessoryController.wearingLightningHat(p),
        "Mellstroy, Kaneki kagune & Грозовая молния all automatically respawned after teleport!");
  check(AccessoryController.mellstroyAttached(p) && AccessoryController.kanekiAttached(p)
        && AccessoryController.lightningHatAttached(p),
        "fresh pivot entities mounted onto PivotOverride at destination!");
  check(!fe.pivots.passengers.contains(oldMellPivot)
        && !fe.pivots.passengers.contains(oldKanekiPivot)
        && !fe.pivots.passengers.contains(oldLightningPivot),
        "stale pre-teleport passenger IDs removed");
  check(fe.pivots.passengers.ids.size() == 3,"new post-teleport passenger IDs active for all 3 slots");

  // --- 7. Buy & Switch to Angel Wings (6000 ꐃ, Спина slot 29 -> 21000 ꐃ) ---
  click.slot=10;controller.onClick(click); // tab to Спина
  click.slot=29;controller.onClick(click); // buy & equip Angel Wings!
  check(wallet.get(p.uuid)==21000 && AccessoryController.owns(p, AccessoryController.AccessoryItem.WINGS),
        "Ангельские крылья bought for exact 6000 Рилликов!");
  check(!AccessoryController.wearingKaneki(p) && AccessoryController.back(plugin,p)==plugin.wings,"wings replace kaneki cleanly");
  check(AccessoryController.wearingMellstroy(p) && AccessoryController.wearingLightningHat(p) && fe.entities.size()==2,
        "Mellstroy & Грозовая молния remain untouched alongside wings");

  // --- 8. Buy & Switch to Halo in Шапки (3500 ꐃ, slot 29 -> 4000 ꐃ) -> mutual exclusion destroys Грозовая молния Dummy! ---
  click.slot=12;controller.onClick(click); // tab to Шапки
  click.slot=29;controller.onClick(click); // buy & equip Halo!
  check(wallet.get(p.uuid)==17500 && AccessoryController.owns(p, AccessoryController.AccessoryItem.HALO_ITEM),
        "Божественный нимб bought for 3500 Рилликов (12 000 ꐃ remaining after 9 purchases!)");
  check(!AccessoryController.wearingLightningHat(p) && fe.entities.size()==1,
        "switching to Божественный нимб cleanly destroys Грозовая молния Dummy");
  check(AccessoryController.halo(plugin,p)==plugin.halo && AccessoryController.back(plugin,p)==plugin.wings && AccessoryController.wearingMellstroy(p),
        "Спина (Wings) + Шапки (Halo) + Питомцы (Меллстрой) all active simultaneously!");
  // Switch back to Круг Сатаны (slot 31) for free (still 4000 ꐃ)!
  click.slot=31;controller.onClick(click);
  check(wallet.get(p.uuid)==17500 && AccessoryController.halo(plugin,p)==null && AccessoryController.wearingSatanCircle(p),
        "re-equipping Круг Сатаны is free and disables WornAngelRig halo!");
  check(Bukkit.slots.get(53).meta.lore.stream().anyMatch(l -> l.contains("17 500") && l.contains("ꐃ")),
        "slot 53 ИНФОРМАЦИЯ clock updated live to 12 000 ꐃ!");

  // --- 8b. Buy & Equip NEW Крылья Зевса (8000 ꐃ, Спина slot 33 -> 9500 ꐃ) -> two wings woven from lightning! ---
  click.slot=10;controller.onClick(click); // tab to Спина
  click.slot=33;controller.onClick(click); // buy & equip Крылья Зевса!
  check(wallet.get(p.uuid)==9500 && AccessoryController.owns(p, AccessoryController.AccessoryItem.ZEUS_WINGS),
        "Крылья Зевса bought for exact 8000 Рилликов!");
  check(AccessoryController.zeusWingsSelected(p) && AccessoryController.wearingZeusWings(p) && AccessoryController.zeusWingsAnimating(p),
        "Крылья Зевса Dummy spawned on the back & playing the seamless 'idle' lightning-beat loop!");
  check(AccessoryController.back(plugin,p)==null,
        "Крылья Зевса take over the isolated back rig slot from the WornAngelRig wings!");
  FakeActive zeusModel=fe.q.last;
  check(zeusModel.view > 2.5F,"the huge 3-block wingspan gets an enlarged render sphere");
  zeusModel.rendererReady=true;
  AccessoryController.animatePets();
  check(AccessoryController.zeusWingsAttached(p) && fe.pivots.passengers.contains(zeusModel.pivotId),
        "Крылья Зевса pivot mounted on player PivotOverride");
  check(fe.entities.size()==3,"Крылья Зевса, Круг Сатаны & Меллстрой all riding their own isolated Dummy entity");

  // --- 8c. Buy & Equip NEW Аура сердечек (5500 ꐃ, Ауры tab slot 16 -> card slot 30 -> 4000 ꐃ) ---
  click.slot=16;controller.onClick(click); // tab to Ауры
  check(Bukkit.title.equals(AccessoryController.TITLE_AURAS),"opened brand-new Ауры section via tab slot 16");
  check(Bukkit.slots.get(29).meta.title.contains("Аура сердечек")
        && Bukkit.slots.get(29).meta.model.equals(new NamespacedKey("reallyworld","heart_aura_icon")),
        "Аура сердечек in Ауры slot 29 with heart_aura_icon!");
  check(Bukkit.slots.get(29).meta.lore.stream().anyMatch(l -> l.contains("5500") && l.contains("ꐃ")),
        "Аура сердечек priced at 5500 Рилликов!");
  click.slot=29;controller.onClick(click); // buy & equip Аура сердечек!
  check(wallet.get(p.uuid)==4000 && AccessoryController.owns(p, AccessoryController.AccessoryItem.HEART_AURA),
        "Аура сердечек bought for exact 5500 Рилликов!");
  check(AccessoryController.heartAuraSelected(p) && AccessoryController.wearingHeartAura(p)
        && AccessoryController.heartAuraAnimating(p),
        "Аура сердечек Dummy spawned around the player & playing the seamless 'idle' rise loop!");
  check(AccessoryController.wearingZeusWings(p) && AccessoryController.wearingSatanCircle(p)
        && AccessoryController.wearingMellstroy(p),
        "Аура lives in its own 4th slot and never collides with Спина, Шапки or Питомцы!");
  check(fe.entities.size()==4,"Аура сердечек rides a 4th isolated Dummy entity, zero UUID collision");
  FakeActive auraModel=fe.q.last;
  auraModel.rendererReady=true;
  AccessoryController.animatePets();
  check(AccessoryController.heartAuraAttached(p) && fe.pivots.passengers.contains(auraModel.pivotId),
        "Аура сердечек pivot mounted on player PivotOverride");
  // Unequip & re-equip the aura -> always free!
  click.slot=29;controller.onClick(click);
  check(!AccessoryController.wearingHeartAura(p) && wallet.get(p.uuid)==4000,"unequipping the aura is free");
  click.slot=29;controller.onClick(click);
  check(AccessoryController.wearingHeartAura(p) && wallet.get(p.uuid)==4000,"re-equipping the aura is free forever!");
  controller.onMove(new PlayerMoveEvent(p, new Location(p.world, p.px, p.py, p.pz, -61.0F, 0.0F)));
  check(Math.abs(auraModel.owner.bodyYaw - 0.0F) < 0.01F && Math.abs(auraModel.owner.headYaw - 0.0F) < 0.01F,
        "Аура сердечек never turns with the body: its rig yaw stays pinned to 0 (world space)!");

  // --- 8d. Buy & Equip NEW Аура бабочек (5500 ꐃ, Ауры card slot 32 -> 4500 ꐃ) ---
  wallet.put(p.uuid, 10000); // top the test wallet up for the second aura
  check(Bukkit.slots.get(31).meta.title.contains("Аура бабочек")
        && Bukkit.slots.get(31).meta.model.equals(new NamespacedKey("reallyworld","butterfly_aura_icon")),
        "Аура бабочек in Ауры slot 31 with butterfly_aura_icon!");
  check(Bukkit.slots.get(31).meta.lore.stream().anyMatch(l -> l.contains("5500") && l.contains("ꐃ")),
        "Аура бабочек priced at 5500 Рилликов!");
  click.slot=31;controller.onClick(click); // buy & equip Аура бабочек!
  check(wallet.get(p.uuid)==4500 && AccessoryController.owns(p, AccessoryController.AccessoryItem.BUTTERFLY_AURA),
        "Аура бабочек bought for exact 5500 Рилликов!");
  check(AccessoryController.butterflyAuraSelected(p) && AccessoryController.wearingButterflyAura(p)
        && AccessoryController.butterflyAuraAnimating(p),
        "Аура бабочек Dummy spawned around the player & playing the seamless 'idle' circling loop!");
  check(!AccessoryController.wearingHeartAura(p) && AccessoryController.wearingZeusWings(p),
        "both auras share the ONE aura slot: equipping Аура бабочек swaps out Аура сердечек!");
  check(fe.entities.size()==4,"the swapped aura still rides the 4th isolated Dummy entity, no leak");
  FakeActive butterflyModel=fe.q.last;
  butterflyModel.rendererReady=true;
  AccessoryController.animatePets();
  check(AccessoryController.butterflyAuraAttached(p) && fe.pivots.passengers.contains(butterflyModel.pivotId),
        "Аура бабочек pivot mounted on player PivotOverride");
  controller.onMove(new PlayerMoveEvent(p, new Location(p.world, p.px, p.py, p.pz, 122.0F, 0.0F)));
  check(Math.abs(butterflyModel.owner.bodyYaw - 0.0F) < 0.01F && Math.abs(butterflyModel.owner.headYaw - 0.0F) < 0.01F,
        "Аура бабочек never turns with the body: its rig yaw stays pinned to 0 (world space)!");
  // Unequip & re-equip -> always free!
  click.slot=31;controller.onClick(click);
  check(!AccessoryController.wearingButterflyAura(p) && wallet.get(p.uuid)==4500,"unequipping Аура бабочек is free");
  click.slot=31;controller.onClick(click);
  check(AccessoryController.wearingButterflyAura(p) && wallet.get(p.uuid)==4500,"re-equipping Аура бабочек is free forever!");

  // --- 8e. Buy & Equip NEW Смертельная аура (5500 ꐃ, Ауры card slot 33 -> 4500 ꐃ) ---
  wallet.put(p.uuid, 10000); // top the test wallet up for the third aura
  check(Bukkit.slots.get(33).meta.title.contains("Смертельная аура")
        && Bukkit.slots.get(33).meta.model.equals(new NamespacedKey("reallyworld","death_aura_icon")),
        "Смертельная аура in Ауры slot 33 with death_aura_icon!");
  check(Bukkit.slots.get(33).meta.lore.stream().anyMatch(l -> l.contains("5500") && l.contains("ꐃ")),
        "Смертельная аура priced at 5500 Рилликов!");
  click.slot=33;controller.onClick(click); // buy & equip Смертельная аура!
  check(wallet.get(p.uuid)==4500 && AccessoryController.owns(p, AccessoryController.AccessoryItem.DEATH_AURA),
        "Смертельная аура bought for exact 5500 Рилликов!");
  check(AccessoryController.deathAuraSelected(p) && AccessoryController.wearingDeathAura(p)
        && AccessoryController.deathAuraAnimating(p),
        "Смертельная аура Dummy spawned around the player & playing the seamless 'idle' ash-rise loop!");
  check(!AccessoryController.wearingButterflyAura(p) && !AccessoryController.wearingHeartAura(p)
        && AccessoryController.wearingZeusWings(p),
        "all three auras share the ONE aura slot: equipping Смертельная аура swaps out the other two!");
  check(fe.entities.size()==4,"the swapped aura still rides the 4th isolated Dummy entity, no leak");
  FakeActive deathModel=fe.q.last;
  deathModel.rendererReady=true;
  AccessoryController.animatePets();
  check(AccessoryController.deathAuraAttached(p) && fe.pivots.passengers.contains(deathModel.pivotId),
        "Смертельная аура pivot mounted on player PivotOverride");
  controller.onMove(new PlayerMoveEvent(p, new Location(p.world, p.px, p.py, p.pz, -173.0F, 0.0F)));
  check(Math.abs(deathModel.owner.bodyYaw - 0.0F) < 0.01F && Math.abs(deathModel.owner.headYaw - 0.0F) < 0.01F,
        "Смертельная аура never turns with the body: its rig yaw stays pinned to 0 (world space)!");
  click.slot=33;controller.onClick(click);
  check(!AccessoryController.wearingDeathAura(p) && wallet.get(p.uuid)==4500,"unequipping Смертельная аура is free");
  click.slot=33;controller.onClick(click);
  check(AccessoryController.wearingDeathAura(p) && wallet.get(p.uuid)==4500,"re-equipping Смертельная аура is free forever!");

  // --- 9. Clear All (slot 49) ---
  click.slot=49;controller.onClick(click);
  check(!AccessoryController.wearingMellstroy(p) && !AccessoryController.wearingSatanCircle(p)
        && !AccessoryController.wearingLightningHat(p) && !AccessoryController.wearingZeusWings(p)
        && !AccessoryController.wearingHeartAura(p) && !AccessoryController.wearingButterflyAura(p)
        && !AccessoryController.wearingDeathAura(p)
        && AccessoryController.back(plugin,p)==null && AccessoryController.halo(plugin,p)==null && fe.entities.isEmpty(),
        "clear-all removes back, hat, pet and both auras cleanly");

  // --- 10. Quit cleanup + Dual Persistence (owned_accessories.yml survives PDC wipe + server restart!) ---
  click.slot=14;controller.onClick(click); // Питомцы
  click.slot=28;controller.onClick(click); // Мини-Роузи (free!)
  click.slot=12;controller.onClick(click); // Шапки
  click.slot=31;controller.onClick(click); // Круг Сатаны (free!)
  click.slot=16;controller.onClick(click); // Ауры
  click.slot=29;controller.onClick(click); // Аура сердечек (free!)
  click.slot=31;controller.onClick(click); // Аура бабочек (free!) -> takes over the shared aura slot
  click.slot=10;controller.onClick(click); // Спина
  click.slot=33;controller.onClick(click); // Крылья Зевса (free!)
  check(wallet.get(p.uuid)==4500 && AccessoryController.wearingMiniMe(p)
        && AccessoryController.wearingSatanCircle(p) && AccessoryController.wearingZeusWings(p)
        && !AccessoryController.wearingHeartAura(p) && AccessoryController.wearingButterflyAura(p),
        "all 4 Dummy slots (Крылья Зевса + Круг Сатаны + Мини-Роузи + Аура бабочек) equipped for free before quit");
  controller.onQuit(new PlayerQuitEvent(p));
  check(!AccessoryController.wearingMiniMe(p) && !AccessoryController.wearingSatanCircle(p)
        && !AccessoryController.wearingZeusWings(p) && !AccessoryController.wearingHeartAura(p)
        && !AccessoryController.wearingButterflyAura(p) && fe.entities.isEmpty(),
        "quit releases all 4 Dummy rigs without leak");

  // Simulate full server restart + playerdata PDC wipe: owned_accessories.yml restores all 12 purchases!
  p.data.m.clear();
  AccessoryController.install(plugin);
  for (AccessoryController.AccessoryItem item : AccessoryController.AccessoryItem.values()) {
   check(AccessoryController.owns(p, item), "owned_accessories.yml persisted " + item.id + " across server restart & PDC wipe!");
  }

  // Test console `/accessories grant <player> satan` for a brand-new player
  PlayerFake newbie = new PlayerFake();
  newbie.name = "Newbie";
  newbie.uuid = UUID.randomUUID();
  Bukkit.online.add(newbie);
  check(!AccessoryController.owns(newbie, AccessoryController.AccessoryItem.SATAN_CIRCLE), "newbie owns nothing initially");
  controller.onCommand(Bukkit.getConsoleSender(), new Command(), "accessories", new String[]{"grant", "Newbie", "satan"});
  check(AccessoryController.owns(newbie, AccessoryController.AccessoryItem.SATAN_CIRCLE)
        && !AccessoryController.owns(newbie, AccessoryController.AccessoryItem.KANEKI),
        "console /accessories grant satan unlocks the satan circle hat permanently");

  ElytrixFreakModelPlugin bare=new ElytrixFreakModelPlugin();bare.returnNullCommand=true;
  AccessoryController.install(bare);
  check(bare.mockCommand.executor==null && !bare.warnings.isEmpty(),"missing command logged safely");
  InventoryDragEvent drag=new InventoryDragEvent();drag.view=click.view;controller.onDrag(drag);check(drag.cancelled,"drag cancelled");
  System.out.println("All v3.26.1 tests passed: public /accessories (/acc, /акс) Риллики shop + Ауры section with THREE auras (Аура сердечек 5500 ꐃ, 12 hearts rising at random, no spiral + Аура бабочек 5500 ꐃ, 10 pink butterflies with filled wings, horizontal body and antennae + Смертельная аура 5500 ꐃ, 26 ash flakes rising in ONE swirling vortex from under the feet, glowing embers, never re-created on teleport) + Крылья Зевса (8000 ꐃ, wings woven from lightning + new cloud rim over the wing arc) + Круг Сатаны (4500 ꐃ, spinning pentagram halo) + Дождевое облако (4000 ꐃ, 3D drizzle) + all 13 3D models!");
 }
}
