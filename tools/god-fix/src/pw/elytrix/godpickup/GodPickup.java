package pw.elytrix.godpickup;
import java.lang.reflect.Method;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.plugin.Plugin;
import org.bukkit.plugin.java.JavaPlugin;
/** Disable item pickup for Essentials god mode, never for fly alone. */
public final class GodPickup extends JavaPlugin implements Listener {
 private Object essentials; private Method getUser,isGod;
 @Override public void onEnable(){
  try{
   essentials=Bukkit.getPluginManager().getPlugin("Essentials");
   if(essentials==null || !((Plugin)essentials).isEnabled())throw new IllegalStateException("Essentials unavailable");
   getUser=essentials.getClass().getMethod("getUser",Player.class); isGod=getUser.getReturnType().getMethod("isGodModeEnabled");
  }catch(ReflectiveOperationException|RuntimeException ex){getLogger().severe("God mode pickup protection unavailable: "+ex);Bukkit.getPluginManager().disablePlugin(this);return;}
  Bukkit.getPluginManager().registerEvents(this,this);
 }
 @EventHandler(priority=EventPriority.HIGHEST,ignoreCancelled=true) public void onPickup(EntityPickupItemEvent e){
  if(!(e.getEntity() instanceof Player))return;
  try{Object user=getUser.invoke(essentials,(Player)e.getEntity());if(user==null || Boolean.TRUE.equals(isGod.invoke(user)))e.setCancelled(true);}
  catch(ReflectiveOperationException|RuntimeException ex){e.setCancelled(true);getLogger().warning("Cannot check god mode; pickup blocked: "+ex);}
 }
}
