package pw.elytrix.elytrixfree;

import java.util.List;
import java.util.Locale;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;

/** Prevent marking a case-containing reward as claimed while BCases is unavailable. */
public final class CaseDependencyGuard {
    private CaseDependencyGuard() {}
    public static boolean canClaim(Player player, List<String> commands) {
        if (player == null || commands == null) return false;
        for (String entry : commands) {
            if (entry == null) continue;
            String command = entry.trim();
            if (command.startsWith("/")) command = command.substring(1).trim();
            if (command.isEmpty()) continue;
            String label = command.split("\\s+", 2)[0].toLowerCase(Locale.ROOT);
            if (label.equals("bcases") || label.equals("bcases:bcases")) {
                try {
                    if (Bukkit.getPluginManager() != null && Bukkit.getPluginManager().isPluginEnabled("BCases")) continue;
                } catch (RuntimeException | LinkageError ignored) {
                    // A broken plugin manager is not evidence that case delivery works.
                }
                player.sendMessage("§cПолучение награды с кейсами временно недоступно. Попробуйте позже.");
                return false;
            }
        }
        return true;
    }
}
