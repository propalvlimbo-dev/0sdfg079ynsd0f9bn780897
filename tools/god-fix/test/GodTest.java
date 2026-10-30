import org.bukkit.Bukkit;import org.bukkit.entity.*;import org.bukkit.event.entity.EntityPickupItemEvent;import org.bukkit.plugin.*;import pw.elytrix.godpickup.GodPickup;
public class GodTest {
 public static class User {boolean god; public boolean isGodModeEnabled(){return god;}}
 public static class Ess implements Plugin {User user=new User();public boolean isEnabled(){return true;}public User getUser(Player p){return user;}}
 public static class Mgr implements PluginManager {Ess e=new Ess();boolean disabled;public Plugin getPlugin(String n){return e;}public void disablePlugin(Plugin p){disabled=true;}public void registerEvents(org.bukkit.event.Listener l,Plugin p){}}
 public static class P implements Player {public String getName(){return "p";}public org.bukkit.permissions.PermissionAttachment addAttachment(Plugin p){return null;}public void removeAttachment(org.bukkit.permissions.PermissionAttachment a){}}
 public static void main(String[]x){Mgr m=new Mgr();Bukkit.manager=m;GodPickup g=new GodPickup();g.onEnable();if(m.disabled)throw new AssertionError();P p=new P();EntityPickupItemEvent e=new EntityPickupItemEvent(p);g.onPickup(e);if(e.isCancelled())throw new AssertionError();m.e.user.god=true;e=new EntityPickupItemEvent(p);g.onPickup(e);if(!e.isCancelled())throw new AssertionError();System.out.println("God pickup mock tests passed");}
}
