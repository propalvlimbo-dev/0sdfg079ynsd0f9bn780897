package cs.cloudstudio.deobf;
import java.lang.reflect.Method;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.plugin.Plugin;

/** Preserve permission semantics, additionally honour an active CakeSub subscription. */
public final class CakeSubPermission {
    private CakeSubPermission() {}
    public static boolean check(Player player, String permission) {
        if(player.hasPermission(permission)) return true;
        if(!"cloudquests.skipquest".equalsIgnoreCase(permission)) return false;
        Plugin cake=Bukkit.getPluginManager().getPlugin("CakeSub");
        if(cake==null || !cake.isEnabled()) return false;
        try {
            Class<?> type=Class.forName("yo.tallen.utils.Data",true,cake.getClass().getClassLoader());
            Method method=type.getMethod("hasActive",String.class);
            return Boolean.TRUE.equals(method.invoke(null,player.getName()));
        } catch (ReflectiveOperationException | RuntimeException | LinkageError ex) {
            Bukkit.getLogger().warning("CloudQuests: cannot verify CakeSub: " + ex);
            return false;
        }
    }
}
