package topka.simbay.rwitems.utils;

import java.lang.reflect.Field;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.block.Block;
import org.bukkit.entity.Player;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.plugin.Plugin;
import topka.simbay.rwitems.items.ItemRegistry;

/**
 * Prevents using TrapItem / EnderTrapItem on or around an active AirDrop (ElytrixAir)
 * so players cannot encase the AirDrop block and solo-loot all rewards.
 */
public final class ElytrixAirTrapGuard {

    private static final double AIRDROP_TRAP_DENY_RADIUS = 20.0D;
    private static final double AIRDROP_TRAP_DENY_RADIUS_SQ = AIRDROP_TRAP_DENY_RADIUS * AIRDROP_TRAP_DENY_RADIUS;
    private static final String DENY_MSG =
            "\u00a7x\u00a7F\u00a78\u00a7B\u00a7E\u00a7F\u00a7BАирДроп \u00a78\u00bb \u00a7cНельзя использовать ловушку рядом с АирДропом!";

    private static volatile Class<?> cachedAirClass;
    private static volatile Field isRunningField;
    private static volatile Field airBlockField;
    private static volatile Field activationLocField;

    private ElytrixAirTrapGuard() {
    }

    public static ItemRegistry.Items validateTrapUse(
            ItemStack stack,
            ItemRegistry.Items expected,
            PlayerInteractEvent event
    ) {
        ItemRegistry.Items matched = ItemRegistry.Items.getItem(stack, expected);
        if (matched == null) {
            return null;
        }
        if (event != null && isBlockedNearAirDrop(event.getPlayer())) {
            event.setCancelled(true);
            event.getPlayer().sendMessage(DENY_MSG);
            return null;
        }
        return matched;
    }

    public static boolean isBlockedNearAirDrop(Player player) {
        if (player == null) {
            return false;
        }
        org.bukkit.plugin.PluginManager pm = Bukkit.getPluginManager();
        Plugin air = pm != null ? pm.getPlugin("ElytrixAir") : null;
        if (air == null || !air.isEnabled()) {
            return false;
        }
        try {
            Class<?> cls = air.getClass();
            if (cls != cachedAirClass || isRunningField == null) {
                Field fRun = cls.getDeclaredField("isRunning");
                fRun.setAccessible(true);
                Field fBlock = cls.getDeclaredField("airBlock");
                fBlock.setAccessible(true);
                Field fLoc = cls.getDeclaredField("activationBlockLoc");
                fLoc.setAccessible(true);
                isRunningField = fRun;
                airBlockField = fBlock;
                activationLocField = fLoc;
                cachedAirClass = cls;
            }
            if (!isRunningField.getBoolean(air)) {
                return false;
            }
            Block airBlock = (Block) airBlockField.get(air);
            Location center = airBlock != null ? airBlock.getLocation() : (Location) activationLocField.get(air);
            if (center == null || center.getWorld() == null) {
                return false;
            }
            Location ploc = player.getLocation();
            if (!center.getWorld().equals(ploc.getWorld())) {
                return false;
            }
            double dx = (ploc.getX() - (center.getBlockX() + 0.5D));
            double dy = Math.abs(ploc.getY() - (center.getBlockY() + 0.5D));
            double dz = (ploc.getZ() - (center.getBlockZ() + 0.5D));
            return (dx * dx + dz * dz) <= AIRDROP_TRAP_DENY_RADIUS_SQ && dy <= AIRDROP_TRAP_DENY_RADIUS;
        } catch (Throwable ignored) {
            return false;
        }
    }
}
