package me.realized.duels.util;

import me.realized.duels.DuelsPlugin;
import me.realized.duels.arena.ArenaImpl;
import me.realized.duels.arena.ArenaManagerImpl;
import me.realized.duels.util.metadata.MetadataUtil;
import org.bukkit.Bukkit;
import org.bukkit.Chunk;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.Player;

/**
 * Eliminates the rare failed-teleport race in Duels:
 *  1. DuelListener.on(PlayerTeleportEvent) honors "Duels-Teleport" metadata even after DuelManager.addPlayers
 *     has already marked isInMatch(player) == true while getChunkAtAsync was still in flight.
 *  2. Ejects passengers, leaves vehicles/seats, stops gliding/sleeping, closes open inventories,
 *     tickets the target chunk, and runs synchronous player.teleport immediately after setting
 *     "Duels-Teleport" (never leaving an async gap where another teleport can consume the token).
 *  3. Schedules verification retries at 3, 12, and 25 ticks if an active match participant is still
 *     outside the arena world/spawn area.
 */
public final class ElytrixDuelTeleportFix {

    private static final String METADATA_KEY = "Duels-Teleport";

    private ElytrixDuelTeleportFix() {
    }

    public static boolean shouldBlockTeleportInMatch(ArenaManagerImpl arenaManager, Player player) {
        if (arenaManager == null || player == null) {
            return false;
        }
        if (player.hasMetadata(METADATA_KEY)) {
            return false;
        }
        return arenaManager.isInMatch(player);
    }

    public static void tryTeleport(DuelsPlugin plugin, Loadable caller, Player player, Location location) {
        if (plugin == null || player == null || location == null) {
            return;
        }
        World world = location.getWorld();
        if (world == null) {
            Log.warn(caller, "Could not teleport " + player.getName() + "! Target world is null.");
            return;
        }
        final Location target = location.clone();
        final int cx = target.getBlockX() >> 4;
        final int cz = target.getBlockZ() >> 4;

        if (world.isChunkLoaded(cx, cz)) {
            performSyncTeleport(plugin, caller, player, target);
        } else {
            world.getChunkAtAsync(cx, cz).whenComplete((chunk, err) -> {
                if (!plugin.isEnabled()) {
                    return;
                }
                Bukkit.getScheduler().runTask(plugin, () -> performSyncTeleport(plugin, caller, player, target));
            });
        }

        // Watchdog retries at 3, 12, and 25 ticks for match arena teleports
        scheduleMatchWatchdog(plugin, caller, player, target, 3L);
        scheduleMatchWatchdog(plugin, caller, player, target, 12L);
        scheduleMatchWatchdog(plugin, caller, player, target, 25L);
    }

    private static void scheduleMatchWatchdog(
            DuelsPlugin plugin,
            Loadable caller,
            Player player,
            Location target,
            long delayTicks
    ) {
        if (!plugin.isEnabled()) {
            return;
        }
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (!plugin.isEnabled() || !player.isOnline() || player.isDead()) {
                return;
            }
            ArenaManagerImpl am = plugin.getArenaManager();
            if (am == null || !am.isInMatch(player)) {
                return;
            }
            ArenaImpl arena = am.get(player);
            if (arena == null || arena.isEndGame()) {
                return;
            }
            if (!isArenaSpawnTarget(arena, target)) {
                return;
            }
            Location cur = player.getLocation();
            if (cur.getWorld() != target.getWorld() || cur.distanceSquared(target) > 900.0D) {
                performSyncTeleport(plugin, caller, player, target);
            }
        }, delayTicks);
    }

    private static boolean isArenaSpawnTarget(ArenaImpl arena, Location target) {
        Location p1 = arena.getPosition(1);
        if (sameSpot(p1, target)) {
            return true;
        }
        Location p2 = arena.getPosition(2);
        return sameSpot(p2, target);
    }

    private static boolean sameSpot(Location a, Location b) {
        if (a == null || b == null || a.getWorld() == null || a.getWorld() != b.getWorld()) {
            return false;
        }
        return a.distanceSquared(b) <= 4.0D;
    }

    public static boolean performSyncTeleport(DuelsPlugin plugin, Loadable caller, Player player, Location target) {
        if (player == null || !player.isOnline() || player.isDead() || target == null || target.getWorld() == null) {
            return false;
        }
        try {
            player.eject();
        } catch (Throwable ignored) {
        }
        try {
            if (player.isInsideVehicle()) {
                player.leaveVehicle();
            }
        } catch (Throwable ignored) {
        }
        try {
            if (player.isGliding()) {
                player.setGliding(false);
            }
        } catch (Throwable ignored) {
        }
        try {
            if (player.isSleeping()) {
                player.wakeup(false);
            }
        } catch (Throwable ignored) {
        }
        try {
            player.closeInventory();
        } catch (Throwable ignored) {
        }

        World world = target.getWorld();
        int cx = target.getBlockX() >> 4;
        int cz = target.getBlockZ() >> 4;
        Chunk chunk = world.getChunkAt(cx, cz);
        if (plugin.isEnabled()) {
            chunk.addPluginChunkTicket(plugin);
            Bukkit.getScheduler().runTaskLater(plugin, () -> {
                if (plugin.isEnabled()) {
                    chunk.removePluginChunkTicket(plugin);
                }
            }, 60L);
        }

        MetadataUtil.put(plugin, player, METADATA_KEY, target.clone());
        boolean ok;
        try {
            ok = player.teleport(target.clone());
        } finally {
            MetadataUtil.remove(plugin, player, METADATA_KEY);
        }
        if (!ok && caller != null) {
            Log.warn(caller, "Initial teleport returned false for " + player.getName() + "; watchdog scheduled.");
        }
        return ok;
    }
}
