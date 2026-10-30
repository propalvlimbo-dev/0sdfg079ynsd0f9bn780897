import pw.elytrix.safety.GameplaySafety;
import org.bukkit.Bukkit;
import org.bukkit.entity.*;
import org.bukkit.plugin.*;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.event.player.PlayerCommandPreprocessEvent;
import org.bukkit.permissions.PermissionAttachment;
import org.bukkit.scheduler.*;
import yo.tallen.utils.Data;

public class GameplaySafetyTest {
  public static class User { boolean god; public boolean isGodModeEnabled() {return god;} }
  public static class Essentials implements Plugin { User user=new User(); public boolean isEnabled(){return true;} public User getUser(Player p){return user;} }
  public static class Manager implements PluginManager { Essentials e=new Essentials(); boolean disabled; public Plugin getPlugin(String n){return e;} public void disablePlugin(Plugin p){disabled=true;} public void registerEvents(org.bukkit.event.Listener l,Plugin p){} }
  public static class Scheduler implements BukkitScheduler { Runnable later; boolean fail; public BukkitTask runTaskLater(Plugin p,Runnable r,long delay){if(delay!=1)throw new AssertionError(); if(fail) throw new IllegalStateException("scheduler"); later=r; return null;} }
  public static class TestPlayer implements Player { PermissionAttachment attachment; boolean removed; public String getName(){return "Tester";} public PermissionAttachment addAttachment(Plugin p){return attachment=new PermissionAttachment();} public void removeAttachment(PermissionAttachment a){if (a!=attachment) throw new AssertionError();removed=true;} }
  static void check(boolean b){if(!b)throw new AssertionError();}
  public static void main(String[] args) {
    Manager mgr = new Manager(); Scheduler scheduler = new Scheduler(); Bukkit.manager=mgr; Bukkit.scheduler=scheduler;
    GameplaySafety plugin = new GameplaySafety(); plugin.onEnable(); check(!mgr.disabled);
    TestPlayer p = new TestPlayer(); EntityPickupItemEvent pickup = new EntityPickupItemEvent(p); plugin.onPickup(pickup); check(!pickup.isCancelled());
    mgr.e.user.god=true; pickup = new EntityPickupItemEvent(p); plugin.onPickup(pickup); check(pickup.isCancelled());
    pickup=new EntityPickupItemEvent(new Entity(){}); plugin.onPickup(pickup); check(!pickup.isCancelled());
    Data.active=false; plugin.onCommand(new PlayerCommandPreprocessEvent(p,"/skipquest test 1")); check(p.attachment==null);
    Data.active=true; plugin.onCommand(new PlayerCommandPreprocessEvent(p,"/fly")); check(p.attachment==null);
    plugin.onCommand(new PlayerCommandPreprocessEvent(p,"/skipquest test 1")); check(p.attachment!=null && p.attachment.name.equals("cloudquests.skipquest") && p.attachment.value); scheduler.later.run(); check(p.removed);
    p.attachment=null; p.removed=false; plugin.onCommand(new PlayerCommandPreprocessEvent(p,"/cloudquests:skipquest x 1")); check(p.attachment!=null); scheduler.later.run(); check(p.removed);
    p.attachment=null; p.removed=false; scheduler.fail=true; plugin.onCommand(new PlayerCommandPreprocessEvent(p,"/skipquest x 1")); check(p.attachment!=null && p.removed);
    System.out.println("GameplaySafety mock tests passed");
  }
}
