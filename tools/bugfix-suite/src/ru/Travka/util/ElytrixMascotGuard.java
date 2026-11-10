package ru.Travka.util;

import java.lang.reflect.Method;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.entity.Player;
import org.bukkit.event.player.PlayerMoveEvent;
import org.bukkit.plugin.Plugin;
import ru.Travka.NMascot;
import ru.Travka.manager.MascotManager;
import ru.Travka.mascot.Mascot;
import ru.Travka.state.States;

/**
 * Enforces disabling both /fly and /god inside the active NMascot Talisman region
 * without dead CMI references.
 */
public final class ElytrixMascotGuard {

    private static final String PREFIX = "\u00a7x\u00a7F\u00a78\u00a7B\u00a7E\u00a7F\u00a7BТалисман \u00a77\u00bb \u00a7f";
    private static final String ACCENT = "\u00a7x\u00a7F\u00a78\u00a7B\u00a7E\u00a7F\u00a7B";

    private static volatile Method essGetUserMethod;
    private static volatile Method userIsGodMethod;
    private static volatile Method userSetGodMethod;

    private ElytrixMascotGuard() {
    }

    public static void onPlayerMove(PlayerMoveEvent event) {
        if (event == null) {
            return;
        }
        NMascot instance = NMascot.getInstance();
        if (instance == null) {
            return;
        }
        MascotManager mgr = instance.getMascotManager();
        if (mgr == null || mgr.getMascot() == null || mgr.getState() != States.STARTED) {
            return;
        }
        Mascot mascot = mgr.getMascot();
        Location mascotLoc = mascot.getLocation();
        if (mascotLoc == null || mascotLoc.getWorld() == null) {
            return;
        }
        Player player = event.getPlayer();
        if (!mascotLoc.getWorld().equals(player.getWorld())) {
            return;
        }
        Location from = event.getFrom();
        Location to = event.getTo();
        if (to == null) {
            return;
        }
        if (from.getBlockX() == to.getBlockX()
                && from.getBlockY() == to.getBlockY()
                && from.getBlockZ() == to.getBlockZ()) {
            return;
        }
        String regionName = mgr.getRegionName();
        if (regionName != null && RegionUtil.isPlayerInRegion(player, regionName)) {
            stripFlyAndGod(player);
        }
    }

    public static void stripFlyAndGod(Player player) {
        if (player == null) {
            return;
        }
        GameMode gm = player.getGameMode();
        if (gm != GameMode.CREATIVE && gm != GameMode.SPECTATOR
                && !eventGuardKeepsFly(player)
                && (player.isFlying() || player.getAllowFlight())) {
            player.setFlying(false);
            player.setAllowFlight(false);
            player.sendMessage(PREFIX + "В зоне талисмана автоматически выключен " + ACCENT + "/fly\u00a7f!");
        }
        org.bukkit.plugin.PluginManager pm = Bukkit.getPluginManager();
        Plugin ess = pm != null ? pm.getPlugin("Essentials") : null;
        if (ess != null && ess.isEnabled()) {
            try {
                if (essGetUserMethod == null) {
                    essGetUserMethod = ess.getClass().getMethod("getUser", Player.class);
                }
                Object user = essGetUserMethod.invoke(ess, player);
                if (user != null) {
                    if (userIsGodMethod == null) {
                        userIsGodMethod = user.getClass().getMethod("isGodModeEnabled");
                        userSetGodMethod = user.getClass().getMethod("setGodModeEnabled", boolean.class);
                    }
                    if (Boolean.TRUE.equals(userIsGodMethod.invoke(user))) {
                        userSetGodMethod.invoke(user, Boolean.FALSE);
                        player.sendMessage(PREFIX + "В зоне талисмана автоматически выключен " + ACCENT + "/god\u00a7f!");
                    }
                }
            } catch (Throwable ignored) {
            }
        }
    }

    /** LuckPerms moder and above (and *) keep /fly on the Talisman: ElytrixEventGuard
     *  owns that rule, and when it is absent we keep the old behaviour. */
    private static boolean eventGuardKeepsFly(Player player) {
        try {
            Plugin guard = Bukkit.getPluginManager().getPlugin("ElytrixEventGuard");
            if (guard == null || !guard.isEnabled()) {
                return false;
            }
            Object result = guard.getClass()
                    .getMethod("isFlyExempt", Player.class).invoke(guard, player);
            return Boolean.TRUE.equals(result);
        } catch (Throwable ignored) {
            return false;
        }
    }
}
