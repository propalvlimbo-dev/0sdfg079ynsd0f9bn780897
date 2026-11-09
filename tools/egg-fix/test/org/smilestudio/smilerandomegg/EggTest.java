package org.smilestudio.smilerandomegg;
import org.bukkit.*; import org.bukkit.block.*; import org.bukkit.command.*; import org.bukkit.entity.*; import org.bukkit.event.player.PlayerInteractEvent; import org.bukkit.inventory.*; import org.bukkit.plugin.*; import org.black_ixx.playerpoints.*; import java.util.*;
public class EggTest {
 static void check(boolean v){if(!v)throw new AssertionError();}
 static class P implements Player { final UUID uuid=UUID.randomUUID(); Inv inv=new Inv(); public String getName(){return "Test";} public UUID getUniqueId(){return uuid;} public PlayerInventory getInventory(){return inv;} public GameMode getGameMode(){return GameMode.SURVIVAL;} public boolean isValid(){return true;} public boolean hasPermission(String p){return true;} public void sendMessage(String s){} }
 static class Inv implements PlayerInventory { ItemStack[] a=new ItemStack[36]; boolean fail; public ItemStack[] getStorageContents(){return a.clone();} public void setStorageContents(ItemStack[] x){a=x;} public HashMap<Integer,ItemStack> addItem(ItemStack... xs){HashMap<Integer,ItemStack> out=new HashMap<>(); if(fail){a[0]=xs[0];out.put(0,xs[0]);}else{for(int i=0;i<a.length;i++)if(a[i]==null){a[i]=xs[0];return out;}out.put(0,xs[0]);}return out;} }
 static class Mgr implements PluginManager { public void registerEvents(org.bukkit.event.Listener l,Plugin p){} public Plugin getPlugin(String s){return ()->true;} }
 static class S implements Server {Mgr m=new Mgr(); public PluginManager getPluginManager(){return m;} }
 static class W implements World {boolean allowed=true; public Entity spawnEntity(Location loc,EntityType type){return ()->allowed;} }
 static class B implements Block {W world; B(W w){world=w;} public Block getRelative(BlockFace f){return this;} public Location getLocation(){return new Location(world);} }
 public static void main(String[] x){
  Bukkit.server=new S(); P p=new P(); Bukkit.player=p; PlayerPoints.instance=new PlayerPoints(); PlayerPoints.instance.api=new PlayerPointsAPI(); PlayerPoints.instance.api.balance=200;
  SmileRandomEgg plugin=new SmileRandomEgg();plugin.onEnable();
  plugin.onCommand(p,new Command("randomeggbuy"),"randomeggbuy",new String[]{"Test"});
  check(PlayerPoints.instance.api.balance==81); check(p.inv.a[0]!=null && p.inv.a[0].getAmount()==3);
  // Insufficient funds: no additional eggs.
  plugin.onCommand(p,new Command("randomeggbuy"),"randomeggbuy",new String[]{"Test"}); check(PlayerPoints.instance.api.balance==81 && p.inv.a[1]==null);
  // Inventory full: no payment.
  PlayerPoints.instance.api.balance=200; for(int i=0;i<36;i++)p.inv.a[i]=new ItemStack(Material.PIG_SPAWN_EGG,64);
  plugin.onCommand(p,new Command("randomeggbuy"),"randomeggbuy",new String[]{"Test"}); check(PlayerPoints.instance.api.balance==200);
  // Unexpected insertion failure restores inventory and balance.
  p.inv.a=new ItemStack[36];p.inv.fail=true;plugin.onCommand(p,new Command("randomeggbuy"),"randomeggbuy",new String[]{"Test"}); check(PlayerPoints.instance.api.balance==200 && p.inv.a[0]==null);p.inv.fail=false;
  plugin.onCommand(p,new Command("randomegg"),"randomegg",new String[]{});check(p.inv.a[0].getAmount()==1);
  W w=new W(); PlayerInteractEvent e=new PlayerInteractEvent();e.player=p;e.item=p.inv.a[0];e.block=new B(w);w.allowed=false;plugin.onPlayerInteract(e);check(e.cancelled && e.item.getAmount()==1);
  e.cancelled=false;w.allowed=true;plugin.onPlayerInteract(e);check(e.cancelled && e.item.getAmount()==0);
  System.out.println("Egg mock tests passed");
 }
}
