package pw.elytrix.safety;

import java.lang.reflect.Method;
import java.util.Locale;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.event.player.PlayerCommandPreprocessEvent;
import org.bukkit.permissions.PermissionAttachment;
import org.bukkit.plugin.Plugin;
import org.bukkit.plugin.java.JavaPlugin;
import yo.tallen.utils.Data;

/** Minimal opt-in bridge. Does not store permissions or inventory state. */
public final class GameplaySafety extends JavaPlugin implements Listener {
    private Object essentials;
    private Method getUser;
    private Method isGod;

    @Override public void onEnable() {
        try {
            essentials = Bukkit.getPluginManager().getPlugin("Essentials");
            if (essentials == null || !((Plugin) essentials).isEnabled()) throw new IllegalStateException("Essentials unavailable");
            getUser = essentials.getClass().getMethod("getUser", Player.class);
            isGod = getUser.getReturnType().getMethod("isGodModeEnabled");
        } catch (ReflectiveOperationException | RuntimeException ex) {
            getLogger().severe("God pickup protection unavailable; disabling GameplaySafety: " + ex);
            Bukkit.getPluginManager().disablePlugin(this);
            return;
        }
        Bukkit.getPluginManager().registerEvents(this, this);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onPickup(EntityPickupItemEvent event) {
        if (!(event.getEntity() instanceof Player)) return;
        try {
            Object user = getUser.invoke(essentials, (Player) event.getEntity());
            if (user != null && Boolean.TRUE.equals(isGod.invoke(user))) event.setCancelled(true);
        } catch (ReflectiveOperationException | RuntimeException ex) {
            // Fail closed for this one pickup rather than allow a potential bypass.
            event.setCancelled(true);
            getLogger().warning("Cannot check Essentials god mode; pickup blocked: " + ex);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onCommand(PlayerCommandPreprocessEvent event) {
        String line = event.getMessage().trim();
        if (!line.startsWith("/")) return;
        String command = line.substring(1).split("\\s+", 2)[0].toLowerCase(Locale.ROOT);
        if (!command.equals("skipquest") && !command.equals("cloudquests:skipquest")) return;
        Player player = event.getPlayer();
        try {
            Plugin cake = Bukkit.getPluginManager().getPlugin("CakeSub");
            if (cake == null || !cake.isEnabled() || !Data.hasActive(player.getName())) return;
            PermissionAttachment grant = player.addAttachment(this);
            try {
                grant.setPermission("cloudquests.skipquest", true);
                Bukkit.getScheduler().runTaskLater(this, () -> {
                    try { player.removeAttachment(grant); } catch (IllegalArgumentException ignored) { }
                }, 1L);
            } catch (RuntimeException ex) {
                try { player.removeAttachment(grant); } catch (IllegalArgumentException ignored) { }
                throw ex;
            }
        } catch (RuntimeException | LinkageError ex) {
            getLogger().warning("CakeSub check failed; skip permission not granted: " + ex);
        }
    }
}
