package pw.elytrix.godpickup;

import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.BiPredicate;
import java.util.function.Consumer;
import java.util.function.Predicate;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockState;
import org.bukkit.block.Container;
import org.bukkit.block.DoubleChest;
import org.bukkit.entity.AreaEffectCloud;
import org.bukkit.entity.ArmorStand;
import org.bukkit.entity.EnderCrystal;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Hanging;
import org.bukkit.entity.HumanEntity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.entity.TNTPrimed;
import org.bukkit.entity.Tameable;
import org.bukkit.entity.ThrownPotion;
import org.bukkit.event.Cancellable;
import org.bukkit.event.Event;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockIgniteEvent;
import org.bukkit.event.block.BlockMultiPlaceEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.block.SignChangeEvent;
import org.bukkit.event.entity.AreaEffectCloudApplyEvent;
import org.bukkit.event.entity.EntityChangeBlockEvent;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.event.entity.PlayerLeashEntityEvent;
import org.bukkit.event.entity.PotionSplashEvent;
import org.bukkit.event.hanging.HangingBreakByEntityEvent;
import org.bukkit.event.hanging.HangingPlaceEvent;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.inventory.InventoryType;
import org.bukkit.event.player.PlayerArmorStandManipulateEvent;
import org.bukkit.event.player.PlayerAttemptPickupItemEvent;
import org.bukkit.event.player.PlayerBucketEmptyEvent;
import org.bukkit.event.player.PlayerBucketEntityEvent;
import org.bukkit.event.player.PlayerBucketFillEvent;
import org.bukkit.event.player.PlayerCommandPreprocessEvent;
import org.bukkit.event.player.PlayerFishEvent;
import org.bukkit.event.player.PlayerInteractAtEntityEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerMoveEvent;
import org.bukkit.event.player.PlayerPickupArrowEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerShearEntityEvent;
import org.bukkit.event.player.PlayerTeleportEvent;
import org.bukkit.event.player.PlayerToggleFlightEvent;
import org.bukkit.event.player.PlayerUnleashEntityEvent;
import org.bukkit.event.server.PluginEnableEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.plugin.EventExecutor;
import org.bukkit.plugin.Plugin;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.projectiles.ProjectileSource;

/**
 * ElytrixGodPickup v2.1.0:
 * - /god & /fly:
 *     * Block item & arrow pickup while /god or /fly is active (NMS setCanPickupItems(false) + LOWEST/HIGHEST guards)
 *     * Allow opening world chests/containers ONLY inside the player's own WorldGuard region (owner or member)
 *     * Allow hitting mobs (non-Player LivingEntity) in both /god and /fly
 *     * Block PvP (hitting Players) while /god or /fly is active AND for 5,000 ms after disabling /god or /fly
 * - Talisman (NMascot):
 *     * Forbid enabling /fly and /god inside the active Talisman region
 *     * Automatically disable active /fly and /god upon entering or standing inside the Talisman region
 * - 100% reflection-based cross-plugin bridges (Essentials, WorldGuard, NMascot) so PlugManX hot-reload never breaks.
 */
public final class GodPickup extends JavaPlugin implements Listener {

    public static final long POST_GOD_COOLDOWN_MS = 5000L;
    public static final long POST_FLY_COOLDOWN_MS = 5000L;
    private static final long NOTIFY_THROTTLE_MS = 900L;

    private static final String PREFIX = "\u00a7x\u00a7F\u00a78\u00a7B\u00a7E\u00a7F\u00a7BElytrix \u00a78\u00bb \u00a7f";
    private static final String ACCENT = "\u00a7x\u00a7F\u00a78\u00a7B\u00a7E\u00a7F\u00a7B";

    private static final Set<String> GOD_TOGGLE_COMMANDS = Collections.unmodifiableSet(new HashSet<>(Arrays.asList(
            "god", "egod", "godmode", "egodmode", "tgm", "etgm", "ungod", "eungod"
    )));

    private static final Set<String> FLY_TOGGLE_COMMANDS = Collections.unmodifiableSet(new HashSet<>(Arrays.asList(
            "fly", "efly"
    )));

    private static final Set<String> ENDERCHEST_COMMANDS = Collections.unmodifiableSet(new HashSet<>(Arrays.asList(
            "ec", "eec", "enderchest", "eenderchest"
    )));

    private static final Set<String> AUTH_COMMANDS = Collections.unmodifiableSet(new HashSet<>(Arrays.asList(
            "l", "login", "reg", "register"
    )));

    private static final Set<String> BLOCKED_IN_GOD_ABUSE_COMMANDS = Collections.unmodifiableSet(new HashSet<>(Arrays.asList(
            "endersee", "eendersee", "invsee", "einvsee",
            "thor", "ethor", "lightning", "elightning", "shock", "eshock", "smite", "esmite",
            "fireball", "efireball", "nuke", "enuke", "antioch", "eantioch",
            "break", "ebreak", "burn", "eburn", "suicide", "esuicide", "kill",
            "tpahere", "etpahere", "tphere", "etphere", "duel"
    )));

    public enum Restriction {
        NONE,
        ACTIVE_GOD,
        POST_GOD_COOLDOWN
    }

    public enum PvpState {
        NONE,
        ACTIVE_GOD,
        ACTIVE_FLY,
        POST_GOD_COOLDOWN,
        POST_FLY_COOLDOWN
    }

    private Predicate<Player> customGodReader;
    private Predicate<Player> customFlyReader;
    private BiPredicate<Player, Location> customOwnRegionChecker;
    private Predicate<Player> customTalismanChecker;
    private Consumer<Player> customDisableGodAction;
    private Consumer<Player> customDisableFlyAction;

    // Cached reflection handles for Essentials, WorldGuard, and NMascot
    private volatile ClassLoader hookedEssLoader;
    private volatile Method essGetUserMethod;
    private volatile Method userIsGodRawMethod;
    private volatile Method userIsGodMethod;
    private volatile Method userSetGodMethod;

    private volatile ClassLoader cachedWgLoader;
    private volatile Object wgRegionContainer;
    private volatile Method wgContainerGetMethod;
    private volatile Method weAdaptWorldMethod;
    private volatile Method weBlockVecAtMethod;
    private volatile Method wgGetApplicableMethod;
    private volatile Method wgSetGetRegionsMethod;
    private volatile Method wgRegionGetIdMethod;
    private volatile Method wgRegionGetPriorityMethod;
    private volatile Method wgRegionGetOwnersMethod;
    private volatile Method wgRegionGetMembersMethod;
    private volatile Method wgDomainContainsUuidMethod;
    private volatile Method wgDomainContainsNameMethod;

    private volatile ClassLoader cachedMascotLoader;
    private volatile Method mascotGetManagerMethod;
    private volatile Method mascotMgrGetMascotMethod;
    private volatile Method mascotMgrGetStateMethod;
    private volatile Method mascotMgrGetRegionNameMethod;
    private volatile Method mascotGetLocMethod;
    private volatile Method mascotIsInRegionMethod;

    private final Map<UUID, Boolean> lastGodState = new ConcurrentHashMap<>();
    private final Map<UUID, Boolean> lastFlyState = new ConcurrentHashMap<>();
    private final Map<UUID, Long> godCooldownUntil = new ConcurrentHashMap<>();
    private final Map<UUID, Long> flyCooldownUntil = new ConcurrentHashMap<>();
    private final Set<UUID> wasGodOnQuit = ConcurrentHashMap.newKeySet();
    private final Set<UUID> wasFlyOnQuit = ConcurrentHashMap.newKeySet();
    private final Set<UUID> pickupDisabledByUs = ConcurrentHashMap.newKeySet();
    private final Map<UUID, Long> lastNotifyAt = new ConcurrentHashMap<>();
    private final Map<UUID, UUID> crystalDetonator = new ConcurrentHashMap<>();

    /** Test hook for unit tests without live Bukkit server. */
    public void initForTest(Predicate<Player> godReader) {
        this.customGodReader = godReader;
    }

    /** Extended test hook covering /god, /fly, WorldGuard own-region, and Talisman enforcement. */
    public void initForTestFull(
            Predicate<Player> godReader,
            Predicate<Player> flyReader,
            BiPredicate<Player, Location> ownRegionChecker,
            Predicate<Player> talismanChecker,
            Consumer<Player> disableGodAction,
            Consumer<Player> disableFlyAction
    ) {
        this.customGodReader = godReader;
        this.customFlyReader = flyReader;
        this.customOwnRegionChecker = ownRegionChecker;
        this.customTalismanChecker = talismanChecker;
        this.customDisableGodAction = disableGodAction;
        this.customDisableFlyAction = disableFlyAction;
    }

    @Override
    public void onEnable() {
        Bukkit.getPluginManager().registerEvents(this, this);
        tryHookEssentialsEvents();
        long now = System.currentTimeMillis();
        for (Player online : Bukkit.getOnlinePlayers()) {
            evaluateState(online, now);
        }
        Bukkit.getScheduler().runTaskTimer(this, this::pollOnlinePlayers, 2L, 2L);
        getLogger().info("ElytrixGodPickup v2.1.0 enabled (/god + /fly rules, WG own-region chests, mob combat, Talisman guard).");
    }

    @Override
    public void onDisable() {
        for (Player online : Bukkit.getOnlinePlayers()) {
            if (pickupDisabledByUs.remove(online.getUniqueId())) {
                online.setCanPickupItems(true);
            }
        }
        pickupDisabledByUs.clear();
        lastGodState.clear();
        lastFlyState.clear();
        lastNotifyAt.clear();
        crystalDetonator.clear();
    }

    @EventHandler
    public void onPluginEnable(PluginEnableEvent event) {
        String name = event.getPlugin().getName();
        if ("Essentials".equalsIgnoreCase(name)) {
            tryHookEssentialsEvents();
        } else if ("WorldGuard".equalsIgnoreCase(name)) {
            cachedWgLoader = null;
            wgRegionContainer = null;
        } else if ("NMascot".equalsIgnoreCase(name)) {
            cachedMascotLoader = null;
        }
    }

    @SuppressWarnings("unchecked")
    private void tryHookEssentialsEvents() {
        Plugin ess = Bukkit.getPluginManager().getPlugin("Essentials");
        if (ess == null || !ess.isEnabled()) {
            return;
        }
        ClassLoader cl = ess.getClass().getClassLoader();
        if (cl == hookedEssLoader) {
            return;
        }
        try {
            essGetUserMethod = ess.getClass().getMethod("getUser", Player.class);
            Class<? extends Event> godEvtClass = (Class<? extends Event>) Class.forName(
                    "net.ess3.api.events.GodStatusChangeEvent", true, cl);
            EventExecutor godExec = (listener, event) -> {
                if (godEvtClass.isInstance(event)) {
                    handleReflectiveGodStatusEvent(event);
                }
            };
            Bukkit.getPluginManager().registerEvent(godEvtClass, this, EventPriority.HIGHEST, godExec, this, true);

            Class<? extends Event> flyEvtClass = (Class<? extends Event>) Class.forName(
                    "net.ess3.api.events.FlyStatusChangeEvent", true, cl);
            EventExecutor flyExec = (listener, event) -> {
                if (flyEvtClass.isInstance(event)) {
                    handleReflectiveFlyStatusEvent(event);
                }
            };
            Bukkit.getPluginManager().registerEvent(flyEvtClass, this, EventPriority.HIGHEST, flyExec, this, true);
            hookedEssLoader = cl;
        } catch (Throwable ex) {
            getLogger().warning("Failed to hook Essentials status events: " + ex);
        }
    }

    private void handleReflectiveGodStatusEvent(Event event) {
        try {
            Method getAffected = event.getClass().getMethod("getAffected");
            Method getController = event.getClass().getMethod("getController");
            Method getValue = event.getClass().getMethod("getValue");
            Object affected = getAffected.invoke(event);
            if (affected == null) {
                return;
            }
            Player target = (Player) affected.getClass().getMethod("getBase").invoke(affected);
            if (target == null) {
                return;
            }
            Player actor = null;
            Object controller = getController.invoke(event);
            if (controller != null) {
                actor = (Player) controller.getClass().getMethod("getBase").invoke(controller);
            }
            boolean enabling = Boolean.TRUE.equals(getValue.invoke(event));
            handleGodToggleAttempt(target, actor, enabling, (Cancellable) event);
        } catch (Throwable ignored) {
        }
    }

    private void handleReflectiveFlyStatusEvent(Event event) {
        try {
            Method getAffected = event.getClass().getMethod("getAffected");
            Method getValue = event.getClass().getMethod("getValue");
            Object affected = getAffected.invoke(event);
            if (affected == null) {
                return;
            }
            Player target = (Player) affected.getClass().getMethod("getBase").invoke(affected);
            if (target == null) {
                return;
            }
            boolean enabling = Boolean.TRUE.equals(getValue.invoke(event));
            handleFlyToggleAttempt(target, enabling, (Cancellable) event);
        } catch (Throwable ignored) {
        }
    }

    /** Direct entry point usable by tests or status listeners for /god toggle. */
    public void handleGodToggleAttempt(Player target, Player actor, boolean enabling, Cancellable event) {
        UUID targetId = target.getUniqueId();
        long now = System.currentTimeMillis();

        if (actor != null && !actor.getUniqueId().equals(targetId) && !actor.hasPermission("elytrix.god.others")) {
            if (event != null) {
                event.setCancelled(true);
            }
            actor.sendMessage(PREFIX + "Вы не можете переключать " + ACCENT + "/god \u00a7fдругим игрокам!");
            return;
        }

        if (enabling) {
            if (isInActiveTalismanRegion(target, target.getLocation())) {
                if (event != null) {
                    event.setCancelled(true);
                }
                sendThrottled(target, now, PREFIX + "На ивенте " + ACCENT + "Талисман \u00a7cзапрещено использовать /fly и /god!");
                return;
            }
            long remMs = getRemainingGodCooldownMs(targetId, now);
            if (remMs > 0L) {
                if (event != null) {
                    event.setCancelled(true);
                }
                sendPvpNotice(target, PvpState.POST_GOD_COOLDOWN, now);
                return;
            }
            lastGodState.put(targetId, Boolean.TRUE);
            syncCanPickupFlag(target, true);
            closeUnauthorizedOpenContainer(target);
        } else {
            lastGodState.put(targetId, Boolean.FALSE);
            godCooldownUntil.put(targetId, now + POST_GOD_COOLDOWN_MS);
            syncCanPickupFlag(target, isFlyActive(target));
            target.sendMessage(PREFIX + "Режим " + ACCENT + "/god \u00a7fвыключен. Бить игроков можно через " + ACCENT + "5.0 сек.\u00a7f!");
        }
    }

    /** Direct entry point usable by tests or status listeners for /fly toggle. */
    public void handleFlyToggleAttempt(Player target, boolean enabling, Cancellable event) {
        UUID targetId = target.getUniqueId();
        long now = System.currentTimeMillis();

        if (enabling) {
            if (isInActiveTalismanRegion(target, target.getLocation())) {
                if (event != null) {
                    event.setCancelled(true);
                }
                sendThrottled(target, now, PREFIX + "На ивенте " + ACCENT + "Талисман \u00a7cзапрещено использовать /fly и /god!");
                return;
            }
            lastFlyState.put(targetId, Boolean.TRUE);
            syncCanPickupFlag(target, true);
            closeUnauthorizedOpenContainer(target);
        } else {
            lastFlyState.put(targetId, Boolean.FALSE);
            flyCooldownUntil.put(targetId, now + POST_FLY_COOLDOWN_MS);
            syncCanPickupFlag(target, isGodActive(target));
            target.sendMessage(PREFIX + "Режим " + ACCENT + "/fly \u00a7fвыключен. Бить игроков можно через " + ACCENT + "5.0 сек.\u00a7f!");
        }
    }

    private void closeUnauthorizedOpenContainer(Player player) {
        try {
            if (player.getOpenInventory() != null) {
                Inventory top = player.getOpenInventory().getTopInventory();
                if (top != null && isWorldContainerInventory(top) && !isAuthorizedOwnRegionInventory(player, top)) {
                    player.closeInventory();
                }
            }
        } catch (Throwable ignored) {
        }
    }

    private void pollOnlinePlayers() {
        long now = System.currentTimeMillis();
        if (crystalDetonator.size() > 256) {
            crystalDetonator.clear();
        }
        for (Player player : Bukkit.getOnlinePlayers()) {
            evaluateState(player, now);
        }
    }

    public boolean isGodActive(Player player) {
        if (player == null) {
            return false;
        }
        if (customGodReader != null) {
            return customGodReader.test(player);
        }
        Plugin ess = Bukkit.getPluginManager().getPlugin("Essentials");
        if (ess == null || !ess.isEnabled()) {
            return false;
        }
        try {
            if (essGetUserMethod == null || ess.getClass().getClassLoader() != hookedEssLoader) {
                tryHookEssentialsEvents();
                if (essGetUserMethod == null) {
                    essGetUserMethod = ess.getClass().getMethod("getUser", Player.class);
                }
            }
            Object user = essGetUserMethod.invoke(ess, player);
            if (user == null) {
                return false;
            }
            if (userIsGodRawMethod == null && userIsGodMethod == null) {
                try {
                    userIsGodRawMethod = user.getClass().getMethod("isGodModeEnabledRaw");
                } catch (NoSuchMethodException ignored) {
                }
                userIsGodMethod = user.getClass().getMethod("isGodModeEnabled");
            }
            if (userIsGodRawMethod != null) {
                return Boolean.TRUE.equals(userIsGodRawMethod.invoke(user));
            }
            return Boolean.TRUE.equals(userIsGodMethod.invoke(user));
        } catch (Throwable ignored) {
            return false;
        }
    }

    public boolean isFlyActive(Player player) {
        if (player == null) {
            return false;
        }
        if (customFlyReader != null) {
            return customFlyReader.test(player);
        }
        GameMode gm = player.getGameMode();
        if (gm == GameMode.CREATIVE || gm == GameMode.SPECTATOR) {
            return false;
        }
        return player.getAllowFlight() || player.isFlying();
    }

    private void disableEssentialsGod(Player player) {
        if (customDisableGodAction != null) {
            customDisableGodAction.accept(player);
            return;
        }
        Plugin ess = Bukkit.getPluginManager().getPlugin("Essentials");
        if (ess == null || !ess.isEnabled()) {
            return;
        }
        try {
            if (essGetUserMethod == null) {
                essGetUserMethod = ess.getClass().getMethod("getUser", Player.class);
            }
            Object user = essGetUserMethod.invoke(ess, player);
            if (user == null) {
                return;
            }
            if (userSetGodMethod == null) {
                userSetGodMethod = user.getClass().getMethod("setGodModeEnabled", boolean.class);
            }
            userSetGodMethod.invoke(user, Boolean.FALSE);
        } catch (Throwable ignored) {
        }
    }

    private void disablePlayerFly(Player player) {
        if (customDisableFlyAction != null) {
            customDisableFlyAction.accept(player);
            return;
        }
        GameMode gm = player.getGameMode();
        if (gm == GameMode.CREATIVE || gm == GameMode.SPECTATOR) {
            return;
        }
        try {
            if (player.isFlying()) {
                player.setFlying(false);
            }
            if (player.getAllowFlight()) {
                player.setAllowFlight(false);
            }
        } catch (Throwable ignored) {
        }
    }

    /** True when ElytrixEventGuard says this player must keep /fly on event zones
     *  (LuckPerms group moder and above, or *). Fail-open: no guard => no bypass. */
    private static boolean eventGuardKeepsFly(Player player) {
        if (player == null) {
            return false;
        }
        try {
            org.bukkit.plugin.Plugin guard =
                    Bukkit.getPluginManager().getPlugin("ElytrixEventGuard");
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

    private void syncCanPickupFlag(Player player, boolean blockPickup) {
        UUID uuid = player.getUniqueId();
        if (blockPickup) {
            pickupDisabledByUs.add(uuid);
            player.setCanPickupItems(false);
        } else if (pickupDisabledByUs.remove(uuid)) {
            player.setCanPickupItems(true);
        }
    }

    public void enforceTalismanAt(Player player, Location loc, long now) {
        if (player == null || !isInActiveTalismanRegion(player, loc)) {
            return;
        }
        UUID uuid = player.getUniqueId();
        boolean hadGod = isGodActive(player);
        if (hadGod) {
            disableEssentialsGod(player);
            lastGodState.put(uuid, Boolean.FALSE);
            godCooldownUntil.merge(uuid, now + POST_GOD_COOLDOWN_MS, Math::max);
            player.sendMessage(PREFIX + "На ивенте " + ACCENT + "Талисман \u00a7fавтоматически выключен режим " + ACCENT + "/god\u00a7f!");
        }
        // moder and above (and *) keep their fly on the Talisman — ElytrixEventGuard
        // owns that rule, so ask it before touching anything.
        if (eventGuardKeepsFly(player)) {
            return;
        }
        boolean hadFly = isFlyActive(player);
        if (hadFly) {
            disablePlayerFly(player);
            lastFlyState.put(uuid, Boolean.FALSE);
            flyCooldownUntil.merge(uuid, now + POST_FLY_COOLDOWN_MS, Math::max);
            player.sendMessage(PREFIX + "На ивенте " + ACCENT + "Талисман \u00a7fавтоматически выключен режим " + ACCENT + "/fly\u00a7f!");
        }
        if (hadGod || hadFly) {
            syncCanPickupFlag(player, false);
        }
    }

    public Restriction evaluateState(Player player, long now) {
        if (player == null) {
            return Restriction.NONE;
        }
        enforceTalismanAt(player, player.getLocation(), now);

        UUID uuid = player.getUniqueId();
        boolean currentlyGod = isGodActive(player);
        boolean currentlyFly = isFlyActive(player);

        Boolean prevGod = lastGodState.put(uuid, currentlyGod);
        if (!currentlyGod && Boolean.TRUE.equals(prevGod)) {
            godCooldownUntil.merge(uuid, now + POST_GOD_COOLDOWN_MS, Math::max);
        }

        Boolean prevFly = lastFlyState.put(uuid, currentlyFly);
        if (!currentlyFly && Boolean.TRUE.equals(prevFly)) {
            flyCooldownUntil.merge(uuid, now + POST_FLY_COOLDOWN_MS, Math::max);
        }

        Long godUntil = godCooldownUntil.get(uuid);
        boolean inGodCd = false;
        if (godUntil != null) {
            if (now < godUntil) {
                inGodCd = true;
            } else {
                godCooldownUntil.remove(uuid, godUntil);
            }
        }

        Long flyUntil = flyCooldownUntil.get(uuid);
        if (flyUntil != null && now >= flyUntil) {
            flyCooldownUntil.remove(uuid, flyUntil);
        }

        // Item pickup is disabled whenever /god OR /fly is active
        syncCanPickupFlag(player, currentlyGod || currentlyFly);

        if (currentlyGod) {
            return Restriction.ACTIVE_GOD;
        }
        if (inGodCd) {
            return Restriction.POST_GOD_COOLDOWN;
        }
        return Restriction.NONE;
    }

    public PvpState getPvpRestriction(Player player, long now) {
        if (player == null) {
            return PvpState.NONE;
        }
        evaluateState(player, now);
        UUID uuid = player.getUniqueId();
        if (Boolean.TRUE.equals(lastGodState.get(uuid))) {
            return PvpState.ACTIVE_GOD;
        }
        if (Boolean.TRUE.equals(lastFlyState.get(uuid))) {
            return PvpState.ACTIVE_FLY;
        }
        long godRem = getRemainingGodCooldownMs(uuid, now);
        long flyRem = getRemainingFlyCooldownMs(uuid, now);
        if (godRem > 0L && godRem >= flyRem) {
            return PvpState.POST_GOD_COOLDOWN;
        }
        if (flyRem > 0L) {
            return PvpState.POST_FLY_COOLDOWN;
        }
        return PvpState.NONE;
    }

    public boolean isPickupOrChestRestricted(Player player, long now) {
        if (player == null) {
            return false;
        }
        evaluateState(player, now);
        UUID uuid = player.getUniqueId();
        return Boolean.TRUE.equals(lastGodState.get(uuid)) || Boolean.TRUE.equals(lastFlyState.get(uuid));
    }

    public long getRemainingCooldownMs(UUID uuid, long now) {
        return Math.max(getRemainingGodCooldownMs(uuid, now), getRemainingFlyCooldownMs(uuid, now));
    }

    public long getRemainingGodCooldownMs(UUID uuid, long now) {
        Long until = godCooldownUntil.get(uuid);
        return until == null ? 0L : Math.max(0L, until - now);
    }

    public long getRemainingFlyCooldownMs(UUID uuid, long now) {
        Long until = flyCooldownUntil.get(uuid);
        return until == null ? 0L : Math.max(0L, until - now);
    }

    private void sendThrottled(Player player, long now, String message) {
        UUID uuid = player.getUniqueId();
        Long prev = lastNotifyAt.get(uuid);
        if (prev != null && (now - prev) < NOTIFY_THROTTLE_MS) {
            return;
        }
        lastNotifyAt.put(uuid, now);
        player.sendMessage(message);
    }

    private void sendPvpNotice(Player player, PvpState state, long now) {
        UUID uuid = player.getUniqueId();
        if (state == PvpState.ACTIVE_GOD) {
            sendThrottled(player, now, PREFIX + "В режиме " + ACCENT + "/god \u00a7fнельзя бить игроков!");
        } else if (state == PvpState.ACTIVE_FLY) {
            sendThrottled(player, now, PREFIX + "В режиме " + ACCENT + "/fly \u00a7fнельзя бить игроков!");
        } else if (state == PvpState.POST_GOD_COOLDOWN) {
            double sec = Math.max(0.1D, Math.ceil(getRemainingGodCooldownMs(uuid, now) / 100.0D) / 10.0D);
            sendThrottled(player, now, String.format(Locale.US,
                    PREFIX + "Подождите " + ACCENT + "%.1f сек. \u00a7fпосле выключения " + ACCENT + "/god \u00a7fперед ударом игроков!",
                    sec));
        } else if (state == PvpState.POST_FLY_COOLDOWN) {
            double sec = Math.max(0.1D, Math.ceil(getRemainingFlyCooldownMs(uuid, now) / 100.0D) / 10.0D);
            sendThrottled(player, now, String.format(Locale.US,
                    PREFIX + "Подождите " + ACCENT + "%.1f сек. \u00a7fпосле выключения " + ACCENT + "/fly \u00a7fперед ударом игроков!",
                    sec));
        }
    }

    private void sendContainerNotice(Player player, long now) {
        boolean god = Boolean.TRUE.equals(lastGodState.get(player.getUniqueId()));
        String mode = god ? "/god" : "/fly";
        sendThrottled(player, now,
                PREFIX + "В режиме " + ACCENT + mode + " \u00a7fоткрывать сундуки можно только в своём регионе!");
    }

    /**
     * Checks whether {@code loc} is inside a non-global WorldGuard region where {@code player}
     * is an explicit owner or member on the highest-priority region covering {@code loc}.
     */
    public boolean isOwnWorldGuardRegion(Player player, Location loc) {
        if (player == null || loc == null) {
            return false;
        }
        if (customOwnRegionChecker != null) {
            return customOwnRegionChecker.test(player, loc);
        }
        World world = loc.getWorld();
        if (world == null) {
            return false;
        }
        Plugin wgPlugin = Bukkit.getPluginManager().getPlugin("WorldGuard");
        if (wgPlugin == null || !wgPlugin.isEnabled()) {
            return false;
        }
        try {
            ClassLoader wgCl = wgPlugin.getClass().getClassLoader();
            if (wgRegionContainer == null || wgCl != cachedWgLoader) {
                Class<?> wgClass = Class.forName("com.sk89q.worldguard.WorldGuard", true, wgCl);
                Object wgInst = wgClass.getMethod("getInstance").invoke(null);
                Object platform = wgClass.getMethod("getPlatform").invoke(wgInst);
                wgRegionContainer = platform.getClass().getMethod("getRegionContainer").invoke(platform);

                Class<?> weWorldClass = Class.forName("com.sk89q.worldedit.world.World", true, wgCl);
                Class<?> adapterClass = Class.forName("com.sk89q.worldedit.bukkit.BukkitAdapter", true, wgCl);
                weAdaptWorldMethod = adapterClass.getMethod("adapt", World.class);
                wgContainerGetMethod = wgRegionContainer.getClass().getMethod("get", weWorldClass);

                Class<?> blockVecClass = Class.forName("com.sk89q.worldedit.math.BlockVector3", true, wgCl);
                weBlockVecAtMethod = blockVecClass.getMethod("at", int.class, int.class, int.class);

                Class<?> rmClass = Class.forName("com.sk89q.worldguard.protection.managers.RegionManager", true, wgCl);
                wgGetApplicableMethod = rmClass.getMethod("getApplicableRegions", blockVecClass);

                Class<?> appSetClass = Class.forName("com.sk89q.worldguard.protection.ApplicableRegionSet", true, wgCl);
                wgSetGetRegionsMethod = appSetClass.getMethod("getRegions");

                Class<?> prClass = Class.forName("com.sk89q.worldguard.protection.regions.ProtectedRegion", true, wgCl);
                wgRegionGetIdMethod = prClass.getMethod("getId");
                wgRegionGetPriorityMethod = prClass.getMethod("getPriority");
                wgRegionGetOwnersMethod = prClass.getMethod("getOwners");
                wgRegionGetMembersMethod = prClass.getMethod("getMembers");

                Class<?> ddClass = Class.forName("com.sk89q.worldguard.domains.DefaultDomain", true, wgCl);
                wgDomainContainsUuidMethod = ddClass.getMethod("contains", UUID.class);
                wgDomainContainsNameMethod = ddClass.getMethod("contains", String.class);
                cachedWgLoader = wgCl;
            }

            Object weWorld = weAdaptWorldMethod.invoke(null, world);
            Object regionManager = wgContainerGetMethod.invoke(wgRegionContainer, weWorld);
            if (regionManager == null) {
                return false;
            }
            Object pt = weBlockVecAtMethod.invoke(null, loc.getBlockX(), loc.getBlockY(), loc.getBlockZ());
            Object appSet = wgGetApplicableMethod.invoke(regionManager, pt);
            Collection<?> regions = (Collection<?>) wgSetGetRegionsMethod.invoke(appSet);
            if (regions == null || regions.isEmpty()) {
                return false;
            }

            int maxPrio = Integer.MIN_VALUE;
            boolean foundNonGlobal = false;
            for (Object reg : regions) {
                String id = (String) wgRegionGetIdMethod.invoke(reg);
                if ("__global__".equalsIgnoreCase(id)) {
                    continue;
                }
                foundNonGlobal = true;
                int prio = ((Number) wgRegionGetPriorityMethod.invoke(reg)).intValue();
                if (prio > maxPrio) {
                    maxPrio = prio;
                }
            }
            if (!foundNonGlobal) {
                return false;
            }

            UUID uuid = player.getUniqueId();
            String name = player.getName();
            boolean memberOfTop = false;
            for (Object reg : regions) {
                String id = (String) wgRegionGetIdMethod.invoke(reg);
                if ("__global__".equalsIgnoreCase(id)) {
                    continue;
                }
                int prio = ((Number) wgRegionGetPriorityMethod.invoke(reg)).intValue();
                if (prio < maxPrio) {
                    continue;
                }
                Object owners = wgRegionGetOwnersMethod.invoke(reg);
                Object members = wgRegionGetMembersMethod.invoke(reg);
                boolean inThis = isDomainMember(owners, uuid, name) || isDomainMember(members, uuid, name);
                if (!inThis) {
                    // A highest-priority region at this block is NOT owned/membered by this player
                    return false;
                }
                memberOfTop = true;
            }
            return memberOfTop;
        } catch (Throwable ignored) {
            return false;
        }
    }

    private boolean isDomainMember(Object domain, UUID uuid, String name) throws Exception {
        if (domain == null) {
            return false;
        }
        if (uuid != null && Boolean.TRUE.equals(wgDomainContainsUuidMethod.invoke(domain, uuid))) {
            return true;
        }
        return name != null && Boolean.TRUE.equals(wgDomainContainsNameMethod.invoke(domain, name));
    }

    /**
     * Checks whether {@code loc} (or {@code player}) is inside an active NMascot Talisman region.
     */
    public boolean isInActiveTalismanRegion(Player player, Location loc) {
        if (customTalismanChecker != null) {
            return customTalismanChecker.test(player);
        }
        Plugin mascotPlugin = Bukkit.getPluginManager().getPlugin("NMascot");
        if (mascotPlugin == null || !mascotPlugin.isEnabled()) {
            return false;
        }
        try {
            ClassLoader cl = mascotPlugin.getClass().getClassLoader();
            if (cl != cachedMascotLoader || mascotGetManagerMethod == null) {
                mascotGetManagerMethod = mascotPlugin.getClass().getMethod("getMascotManager");
                Class<?> mgrClass = Class.forName("ru.Travka.manager.MascotManager", true, cl);
                mascotMgrGetMascotMethod = mgrClass.getMethod("getMascot");
                mascotMgrGetStateMethod = mgrClass.getMethod("getState");
                mascotMgrGetRegionNameMethod = mgrClass.getMethod("getRegionName");
                Class<?> mascotClass = Class.forName("ru.Travka.mascot.Mascot", true, cl);
                mascotGetLocMethod = mascotClass.getMethod("getLocation");
                Class<?> regionUtilClass = Class.forName("ru.Travka.util.RegionUtil", true, cl);
                mascotIsInRegionMethod = regionUtilClass.getMethod("isPlayerInRegion", Player.class, String.class);
                cachedMascotLoader = cl;
            }
            Object mgr = mascotGetManagerMethod.invoke(mascotPlugin);
            if (mgr == null) {
                return false;
            }
            Object mascot = mascotMgrGetMascotMethod.invoke(mgr);
            Object state = mascotMgrGetStateMethod.invoke(mgr);
            if (mascot == null || state == null || !"STARTED".equalsIgnoreCase(String.valueOf(state))) {
                return false;
            }
            Location center = (Location) mascotGetLocMethod.invoke(mascot);
            Location checkLoc = loc != null ? loc : (player != null ? player.getLocation() : null);
            if (center != null && checkLoc != null && center.getWorld() != null && center.getWorld().equals(checkLoc.getWorld())) {
                int left = mascotPlugin.getConfig().getInt("region.left", 50);
                int right = mascotPlugin.getConfig().getInt("region.right", 50);
                int front = mascotPlugin.getConfig().getInt("region.front", 50);
                int back = mascotPlugin.getConfig().getInt("region.back", 50);
                int down = mascotPlugin.getConfig().getInt("region.down", 50);
                int height = mascotPlugin.getConfig().getInt("region.height", 100);
                int bx = center.getBlockX();
                int by = center.getBlockY();
                int bz = center.getBlockZ();
                int px = checkLoc.getBlockX();
                int py = checkLoc.getBlockY();
                int pz = checkLoc.getBlockZ();
                if (px >= bx - left && px <= bx + right
                        && py >= by - down && py <= by + height
                        && pz >= bz - back && pz <= bz + front) {
                    return true;
                }
            }
            if (player != null && (loc == null || loc == player.getLocation())) {
                String regionName = (String) mascotMgrGetRegionNameMethod.invoke(mgr);
                if (regionName != null && Boolean.TRUE.equals(mascotIsInRegionMethod.invoke(null, player, regionName))) {
                    return true;
                }
            }
        } catch (Throwable ignored) {
        }
        return false;
    }

    private static boolean isContainerLikeMaterial(Material mat) {
        if (mat == null) {
            return false;
        }
        String n = mat.name();
        return n.endsWith("CHEST")
                || n.endsWith("SHULKER_BOX")
                || "BARREL".equals(n)
                || "HOPPER".equals(n)
                || "DISPENSER".equals(n)
                || "DROPPER".equals(n)
                || n.endsWith("FURNACE")
                || "SMOKER".equals(n)
                || "BREWING_STAND".equals(n)
                || "CRAFTER".equals(n)
                || "CHISELED_BOOKSHELF".equals(n)
                || "DECORATED_POT".equals(n)
                || "LECTERN".equals(n)
                || "JUKEBOX".equals(n)
                || n.endsWith("_SHELF");
    }

    private static boolean isContainerBlock(Block block) {
        if (block == null) {
            return false;
        }
        if (isContainerLikeMaterial(block.getType())) {
            return true;
        }
        try {
            BlockState state = block.getState();
            return state instanceof Container || state instanceof InventoryHolder;
        } catch (Throwable ignored) {
            return false;
        }
    }

    private static boolean isWorldContainerInventory(Inventory inv) {
        if (inv == null) {
            return false;
        }
        InventoryType type = inv.getType();
        if (type == InventoryType.CRAFTING || type == InventoryType.CREATIVE || type == InventoryType.PLAYER) {
            return false;
        }
        if (type == InventoryType.ENDER_CHEST) {
            return true;
        }
        InventoryHolder holder = inv.getHolder();
        if (holder instanceof BlockState || holder instanceof DoubleChest) {
            return true;
        }
        if (holder instanceof Entity && !(holder instanceof HumanEntity)) {
            // StorageMinecart, HopperMinecart, ChestBoat, horse/llama chest
            return type != InventoryType.MERCHANT;
        }
        Location loc = inv.getLocation();
        return loc != null && type != InventoryType.MERCHANT;
    }

    private boolean isAuthorizedOwnRegionInventory(Player player, Inventory inv) {
        if (inv == null) {
            return true;
        }
        InventoryHolder holder = inv.getHolder();
        if (holder instanceof DoubleChest) {
            DoubleChest dc = (DoubleChest) holder;
            InventoryHolder left = dc.getLeftSide();
            InventoryHolder right = dc.getRightSide();
            Location l1 = left instanceof BlockState ? ((BlockState) left).getLocation() : dc.getLocation();
            Location l2 = right instanceof BlockState ? ((BlockState) right).getLocation() : dc.getLocation();
            return isOwnWorldGuardRegion(player, l1) && isOwnWorldGuardRegion(player, l2);
        }
        if (holder instanceof BlockState) {
            return isOwnWorldGuardRegion(player, ((BlockState) holder).getLocation());
        }
        if (holder instanceof Entity && !(holder instanceof HumanEntity)) {
            return isOwnWorldGuardRegion(player, ((Entity) holder).getLocation());
        }
        Location loc = inv.getLocation();
        if (loc != null) {
            return isOwnWorldGuardRegion(player, loc);
        }
        if (inv.getType() == InventoryType.ENDER_CHEST) {
            return isOwnWorldGuardRegion(player, player.getLocation());
        }
        return false;
    }

    private static boolean isCombatOrConsumableMaterial(Material mat) {
        if (mat == null) {
            return false;
        }
        if (mat.isEdible()) {
            return true;
        }
        String n = mat.name();
        return "BOW".equals(n)
                || "CROSSBOW".equals(n)
                || "TRIDENT".equals(n)
                || "SHIELD".equals(n)
                || "POTION".equals(n)
                || "SPLASH_POTION".equals(n)
                || "LINGERING_POTION".equals(n)
                || "FISHING_ROD".equals(n)
                || "ENDER_PEARL".equals(n)
                || "WIND_CHARGE".equals(n)
                || "FIREWORK_ROCKET".equals(n)
                || n.endsWith("_SWORD")
                || n.endsWith("_AXE")
                || "MACE".equals(n);
    }

    private Player resolvePlayerDamager(Entity damager) {
        if (damager instanceof Player) {
            return (Player) damager;
        }
        if (damager instanceof Projectile) {
            ProjectileSource shooter = ((Projectile) damager).getShooter();
            if (shooter instanceof Player) {
                return (Player) shooter;
            }
        }
        if (damager instanceof TNTPrimed) {
            Entity source = ((TNTPrimed) damager).getSource();
            if (source instanceof Player) {
                return (Player) source;
            }
        }
        if (damager instanceof AreaEffectCloud) {
            ProjectileSource source = ((AreaEffectCloud) damager).getSource();
            if (source instanceof Player) {
                return (Player) source;
            }
        }
        if (damager instanceof Tameable) {
            Object owner = ((Tameable) damager).getOwner();
            if (owner instanceof Player) {
                return (Player) owner;
            }
        }
        if (damager instanceof EnderCrystal) {
            UUID detonatorId = crystalDetonator.get(damager.getUniqueId());
            if (detonatorId != null) {
                return Bukkit.getPlayer(detonatorId);
            }
        }
        return null;
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onJoin(PlayerJoinEvent event) {
        Player player = event.getPlayer();
        UUID uuid = player.getUniqueId();
        long now = System.currentTimeMillis();
        boolean currentlyGod = isGodActive(player);
        boolean currentlyFly = isFlyActive(player);
        lastGodState.put(uuid, currentlyGod);
        lastFlyState.put(uuid, currentlyFly);
        if (wasGodOnQuit.remove(uuid) && !currentlyGod) {
            godCooldownUntil.merge(uuid, now + POST_GOD_COOLDOWN_MS, Math::max);
        }
        if (wasFlyOnQuit.remove(uuid) && !currentlyFly) {
            flyCooldownUntil.merge(uuid, now + POST_FLY_COOLDOWN_MS, Math::max);
        }
        evaluateState(player, now);
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onQuit(PlayerQuitEvent event) {
        Player player = event.getPlayer();
        UUID uuid = player.getUniqueId();
        long now = System.currentTimeMillis();
        if (isGodActive(player) || Boolean.TRUE.equals(lastGodState.remove(uuid))) {
            wasGodOnQuit.add(uuid);
            godCooldownUntil.merge(uuid, now + POST_GOD_COOLDOWN_MS, Math::max);
        }
        if (isFlyActive(player) || Boolean.TRUE.equals(lastFlyState.remove(uuid))) {
            wasFlyOnQuit.add(uuid);
            flyCooldownUntil.merge(uuid, now + POST_FLY_COOLDOWN_MS, Math::max);
        }
        // Restore vanilla CanPickUpLoot before world saves playerdata/<uuid>.dat
        if (pickupDisabledByUs.remove(uuid)) {
            player.setCanPickupItems(true);
        }
        lastNotifyAt.remove(uuid);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onMove(PlayerMoveEvent event) {
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
        enforceTalismanAt(event.getPlayer(), to, System.currentTimeMillis());
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onTeleport(PlayerTeleportEvent event) {
        Location to = event.getTo();
        if (to != null) {
            enforceTalismanAt(event.getPlayer(), to, System.currentTimeMillis());
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onToggleFlight(PlayerToggleFlightEvent event) {
        Player player = event.getPlayer();
        GameMode gm = player.getGameMode();
        if (gm == GameMode.CREATIVE || gm == GameMode.SPECTATOR) {
            return;
        }
        long now = System.currentTimeMillis();
        if (event.isFlying()) {
            if (isInActiveTalismanRegion(player, player.getLocation())) {
                event.setCancelled(true);
                disablePlayerFly(player);
                sendThrottled(player, now,
                        PREFIX + "На ивенте " + ACCENT + "Талисман \u00a7cзапрещено использовать /fly и /god!");
                return;
            }
            if (getRemainingFlyCooldownMs(player.getUniqueId(), now) > 0L) {
                event.setCancelled(true);
                disablePlayerFly(player);
                sendPvpNotice(player, PvpState.POST_FLY_COOLDOWN, now);
                return;
            }
            lastFlyState.put(player.getUniqueId(), Boolean.TRUE);
            syncCanPickupFlag(player, true);
            closeUnauthorizedOpenContainer(player);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onCommandPreprocess(PlayerCommandPreprocessEvent event) {
        String raw = event.getMessage();
        if (raw == null) {
            return;
        }
        String trimmed = raw.trim();
        if (!trimmed.startsWith("/")) {
            return;
        }
        String[] parts = trimmed.substring(1).split("\\s+");
        if (parts.length == 0 || parts[0].isEmpty()) {
            return;
        }
        String cmd = parts[0].toLowerCase(Locale.ROOT);
        int colon = cmd.lastIndexOf(':');
        if (colon >= 0) {
            cmd = cmd.substring(colon + 1);
        }
        if (AUTH_COMMANDS.contains(cmd)) {
            return;
        }

        Player player = event.getPlayer();
        long now = System.currentTimeMillis();

        // 1. Talisman event forbids /fly and /god completely
        if ((GOD_TOGGLE_COMMANDS.contains(cmd) || FLY_TOGGLE_COMMANDS.contains(cmd))
                && isInActiveTalismanRegion(player, player.getLocation())) {
            if (parts.length > 1 && ("off".equalsIgnoreCase(parts[1]) || "disable".equalsIgnoreCase(parts[1]))) {
                return;
            }
            if ("ungod".equals(cmd) || "eungod".equals(cmd)) {
                return;
            }
            event.setCancelled(true);
            enforceTalismanAt(player, player.getLocation(), now);
            sendThrottled(player, now, PREFIX + "На ивенте " + ACCENT + "Талисман \u00a7cзапрещено использовать /fly и /god!");
            return;
        }

        // 2. Prevent /god <otherPlayer> without explicit permission
        if (GOD_TOGGLE_COMMANDS.contains(cmd) && parts.length > 1 && !player.hasPermission("elytrix.god.others")) {
            String arg = parts[1];
            if (!arg.equalsIgnoreCase("on") && !arg.equalsIgnoreCase("off")
                    && !arg.equalsIgnoreCase("enable") && !arg.equalsIgnoreCase("disable")
                    && !arg.equalsIgnoreCase(player.getName())) {
                event.setCancelled(true);
                player.sendMessage(PREFIX + "Вы не можете переключать " + ACCENT + "/god \u00a7fдругим игрокам!");
                return;
            }
        }

        Restriction state = evaluateState(player, now);

        // 3. Block re-enabling /god while in 5.0s post-god cooldown
        if (state == Restriction.POST_GOD_COOLDOWN && GOD_TOGGLE_COMMANDS.contains(cmd)
                && !"ungod".equals(cmd) && !"eungod".equals(cmd)) {
            event.setCancelled(true);
            sendPvpNotice(player, PvpState.POST_GOD_COOLDOWN, now);
            return;
        }

        // 4. Enderchest command (/ec) requires own WG region while in /god or /fly
        if (ENDERCHEST_COMMANDS.contains(cmd) && isPickupOrChestRestricted(player, now)) {
            if (!isOwnWorldGuardRegion(player, player.getLocation())) {
                event.setCancelled(true);
                sendContainerNotice(player, now);
                return;
            }
        }

        // 5. Block harmful/abuse commands while in active /god
        if (state == Restriction.ACTIVE_GOD && BLOCKED_IN_GOD_ABUSE_COMMANDS.contains(cmd)) {
            event.setCancelled(true);
            sendThrottled(player, now, PREFIX + "Эта команда недоступна в режиме " + ACCENT + "/god\u00a7f!");
        }
    }

    // =========================================================================
    // COMBAT: Allow hitting MOBS; block hitting PLAYERS in /god, /fly & 5.0s CD
    // =========================================================================

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onDamageByEntity(EntityDamageByEntityEvent event) {
        handleDamage(event, true);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onDamageByEntityHighest(EntityDamageByEntityEvent event) {
        handleDamage(event, false);
    }

    private void handleDamage(EntityDamageByEntityEvent event, boolean notify) {
        Entity victim = event.getEntity();
        Player attacker = resolvePlayerDamager(event.getDamager());
        long now = System.currentTimeMillis();

        if (victim instanceof EnderCrystal) {
            if (attacker != null) {
                crystalDetonator.put(victim.getUniqueId(), attacker.getUniqueId());
            }
            return;
        }

        if (victim instanceof Player) {
            Player victimPlayer = (Player) victim;
            if (attacker != null && !attacker.getUniqueId().equals(victimPlayer.getUniqueId())) {
                PvpState pvp = getPvpRestriction(attacker, now);
                if (pvp != PvpState.NONE) {
                    event.setCancelled(true);
                    if (notify) {
                        sendPvpNotice(attacker, pvp, now);
                    }
                    return;
                }
            }
            // Victim in active /god is invulnerable (victim in /fly is NEVER invulnerable!)
            if (evaluateState(victimPlayer, now) == Restriction.ACTIVE_GOD) {
                event.setCancelled(true);
            }
            return;
        }

        // Non-player entity: allow hitting all LivingEntity mobs (excluding ArmorStand/Hanging outside own WG in /god)
        if (attacker != null && evaluateState(attacker, now) == Restriction.ACTIVE_GOD) {
            if ((victim instanceof ArmorStand || victim instanceof Hanging)
                    && !isOwnWorldGuardRegion(attacker, victim.getLocation())) {
                event.setCancelled(true);
                if (notify) {
                    sendContainerNotice(attacker, now);
                }
            }
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onPotionSplash(PotionSplashEvent event) {
        ThrownPotion potion = event.getPotion();
        if (potion == null || !(potion.getShooter() instanceof Player)) {
            return;
        }
        Player thrower = (Player) potion.getShooter();
        long now = System.currentTimeMillis();
        PvpState pvp = getPvpRestriction(thrower, now);
        if (pvp == PvpState.NONE) {
            return;
        }
        boolean strippedAnyPlayer = false;
        for (LivingEntity affected : event.getAffectedEntities()) {
            if (affected instanceof Player && !affected.getUniqueId().equals(thrower.getUniqueId())) {
                event.setIntensity(affected, 0.0D);
                strippedAnyPlayer = true;
            }
        }
        if (strippedAnyPlayer) {
            sendPvpNotice(thrower, pvp, now);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onAreaEffectApply(AreaEffectCloudApplyEvent event) {
        ProjectileSource src = event.getEntity().getSource();
        if (!(src instanceof Player)) {
            return;
        }
        Player owner = (Player) src;
        long now = System.currentTimeMillis();
        PvpState pvp = getPvpRestriction(owner, now);
        if (pvp == PvpState.NONE) {
            return;
        }
        Iterator<LivingEntity> it = event.getAffectedEntities().iterator();
        while (it.hasNext()) {
            LivingEntity target = it.next();
            if (target instanceof Player && !target.getUniqueId().equals(owner.getUniqueId())) {
                it.remove();
            }
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onFish(PlayerFishEvent event) {
        Entity caught = event.getCaught();
        if (caught instanceof Player && !caught.getUniqueId().equals(event.getPlayer().getUniqueId())) {
            long now = System.currentTimeMillis();
            PvpState pvp = getPvpRestriction(event.getPlayer(), now);
            if (pvp != PvpState.NONE) {
                event.setCancelled(true);
                sendPvpNotice(event.getPlayer(), pvp, now);
            }
        }
    }

    // =========================================================================
    // CHESTS & WORLD CONTAINERS: Only allowed inside player's own WG region
    // =========================================================================

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = false)
    public void onInteract(PlayerInteractEvent event) {
        handleInteract(event, true);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = false)
    public void onInteractHighest(PlayerInteractEvent event) {
        handleInteract(event, false);
    }

    private void handleInteract(PlayerInteractEvent event, boolean notify) {
        Player player = event.getPlayer();
        long now = System.currentTimeMillis();
        Restriction godState = evaluateState(player, now);
        UUID uuid = player.getUniqueId();
        boolean inGod = godState == Restriction.ACTIVE_GOD;
        boolean inFly = Boolean.TRUE.equals(lastFlyState.get(uuid));

        if (!inGod && !inFly) {
            return;
        }

        Action action = event.getAction();
        Block clicked = event.getClickedBlock();

        // Right-clicking a world container block (chest, barrel, shulker, hopper, furnace, shelf, ender chest, etc.)
        if (action == Action.RIGHT_CLICK_BLOCK && clicked != null && isContainerBlock(clicked)) {
            if (isOwnWorldGuardRegion(player, clicked.getLocation())) {
                return;
            }
            if (!inGod && player.isSneaking()) {
                ItemStack hand = event.getItem();
                if (hand != null && hand.getType() != Material.AIR) {
                    // Sneak + block/item in /fly does not open the chest unless useInteractedBlock is forced
                    event.setUseInteractedBlock(Event.Result.DENY);
                    return;
                }
            }
            event.setCancelled(true);
            event.setUseInteractedBlock(Event.Result.DENY);
            if (inGod) {
                event.setUseItemInHand(Event.Result.DENY);
            }
            if (notify) {
                sendContainerNotice(player, now);
            }
            return;
        }

        // In /fly (without /god), normal survival interactions (building, eating, bows, doors, etc.) are allowed
        if (!inGod) {
            return;
        }

        // In /god: allow left-click/physical (mob melee combat, walking) and combat/consumable items (bow, trident, food)
        if (action == Action.LEFT_CLICK_AIR || action == Action.LEFT_CLICK_BLOCK || action == Action.PHYSICAL) {
            return;
        }
        ItemStack handItem = event.getItem();
        if (action == Action.RIGHT_CLICK_AIR && handItem != null && isCombatOrConsumableMaterial(handItem.getType())) {
            return;
        }
        if (action == Action.RIGHT_CLICK_BLOCK && clicked != null) {
            if (isOwnWorldGuardRegion(player, clicked.getLocation())) {
                return;
            }
            if (handItem != null && isCombatOrConsumableMaterial(handItem.getType())) {
                event.setUseInteractedBlock(Event.Result.DENY);
                return;
            }
            event.setCancelled(true);
            event.setUseInteractedBlock(Event.Result.DENY);
            event.setUseItemInHand(Event.Result.DENY);
            if (notify) {
                sendContainerNotice(player, now);
            }
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onInteractEntity(PlayerInteractEntityEvent event) {
        handleEntityContainerInteract(event.getPlayer(), event.getRightClicked(), event);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onInteractAtEntity(PlayerInteractAtEntityEvent event) {
        handleEntityContainerInteract(event.getPlayer(), event.getRightClicked(), event);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onArmorStand(PlayerArmorStandManipulateEvent event) {
        handleEntityContainerInteract(event.getPlayer(), event.getRightClicked(), event);
    }

    private void handleEntityContainerInteract(Player player, Entity target, Cancellable event) {
        if (target == null) {
            return;
        }
        boolean isStorageEntity = (target instanceof InventoryHolder && !(target instanceof HumanEntity))
                || target instanceof ArmorStand
                || target instanceof Hanging;
        if (!isStorageEntity) {
            return;
        }
        long now = System.currentTimeMillis();
        if (isPickupOrChestRestricted(player, now) && !isOwnWorldGuardRegion(player, target.getLocation())) {
            event.setCancelled(true);
            sendContainerNotice(player, now);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onInventoryOpen(InventoryOpenEvent event) {
        handleInventoryOpen(event, true);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onInventoryOpenHighest(InventoryOpenEvent event) {
        handleInventoryOpen(event, false);
    }

    private void handleInventoryOpen(InventoryOpenEvent event, boolean notify) {
        HumanEntity human = event.getPlayer();
        if (!(human instanceof Player)) {
            return;
        }
        Player player = (Player) human;
        long now = System.currentTimeMillis();
        if (!isPickupOrChestRestricted(player, now)) {
            return;
        }
        Inventory inv = event.getInventory();
        if (isWorldContainerInventory(inv) && !isAuthorizedOwnRegionInventory(player, inv)) {
            event.setCancelled(true);
            if (notify) {
                sendContainerNotice(player, now);
            }
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onInventoryClick(InventoryClickEvent event) {
        handleOpenContainerGuard(event.getWhoClicked(), event.getView() != null ? event.getView().getTopInventory() : event.getInventory(), event, true);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onInventoryClickHighest(InventoryClickEvent event) {
        handleOpenContainerGuard(event.getWhoClicked(), event.getView() != null ? event.getView().getTopInventory() : event.getInventory(), event, false);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onInventoryDrag(InventoryDragEvent event) {
        handleOpenContainerGuard(event.getWhoClicked(), event.getView() != null ? event.getView().getTopInventory() : event.getInventory(), event, true);
    }

    private void handleOpenContainerGuard(HumanEntity human, Inventory top, Cancellable event, boolean notify) {
        if (!(human instanceof Player)) {
            return;
        }
        Player player = (Player) human;
        long now = System.currentTimeMillis();
        if (!isPickupOrChestRestricted(player, now)) {
            return;
        }
        if (isWorldContainerInventory(top) && !isAuthorizedOwnRegionInventory(player, top)) {
            event.setCancelled(true);
            player.closeInventory();
            if (notify) {
                sendContainerNotice(player, now);
            }
        }
    }

    // =========================================================================
    // ITEM & ARROW PICKUPS: Blocked in BOTH /god and /fly (LOWEST + HIGHEST)
    // =========================================================================

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onAttemptPickup(PlayerAttemptPickupItemEvent event) {
        if (isPickupOrChestRestricted(event.getPlayer(), System.currentTimeMillis())) {
            event.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onAttemptPickupHighest(PlayerAttemptPickupItemEvent event) {
        if (isPickupOrChestRestricted(event.getPlayer(), System.currentTimeMillis())) {
            event.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onEntityPickup(EntityPickupItemEvent event) {
        if (event.getEntity() instanceof Player
                && isPickupOrChestRestricted((Player) event.getEntity(), System.currentTimeMillis())) {
            event.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onEntityPickupHighest(EntityPickupItemEvent event) {
        if (event.getEntity() instanceof Player
                && isPickupOrChestRestricted((Player) event.getEntity(), System.currentTimeMillis())) {
            event.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onArrowPickup(PlayerPickupArrowEvent event) {
        if (isPickupOrChestRestricted(event.getPlayer(), System.currentTimeMillis())) {
            event.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onArrowPickupHighest(PlayerPickupArrowEvent event) {
        if (isPickupOrChestRestricted(event.getPlayer(), System.currentTimeMillis())) {
            event.setCancelled(true);
        }
    }

    // =========================================================================
    // WORLD PROTECTION IN /god OUTSIDE OWN WORLDGUARD REGION
    // =========================================================================

    private void blockInGodOutsideOwnRegion(Player player, Location loc, Cancellable event, boolean notify) {
        long now = System.currentTimeMillis();
        if (evaluateState(player, now) != Restriction.ACTIVE_GOD) {
            return;
        }
        if (isOwnWorldGuardRegion(player, loc)) {
            return;
        }
        event.setCancelled(true);
        if (notify) {
            sendThrottled(player, now,
                    PREFIX + "В режиме " + ACCENT + "/god \u00a7fвзаимодействовать с блоками можно только в своём регионе!");
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onBlockBreak(BlockBreakEvent event) {
        blockInGodOutsideOwnRegion(event.getPlayer(), event.getBlock() != null ? event.getBlock().getLocation() : null, event, true);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onBlockBreakHighest(BlockBreakEvent event) {
        blockInGodOutsideOwnRegion(event.getPlayer(), event.getBlock() != null ? event.getBlock().getLocation() : null, event, false);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onBlockPlace(BlockPlaceEvent event) {
        blockInGodOutsideOwnRegion(event.getPlayer(), event.getBlock() != null ? event.getBlock().getLocation() : null, event, true);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onBlockPlaceHighest(BlockPlaceEvent event) {
        blockInGodOutsideOwnRegion(event.getPlayer(), event.getBlock() != null ? event.getBlock().getLocation() : null, event, false);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onBlockMultiPlace(BlockMultiPlaceEvent event) {
        blockInGodOutsideOwnRegion(event.getPlayer(), event.getBlock() != null ? event.getBlock().getLocation() : null, event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onSignChange(SignChangeEvent event) {
        blockInGodOutsideOwnRegion(event.getPlayer(), event.getBlock() != null ? event.getBlock().getLocation() : null, event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onBlockIgnite(BlockIgniteEvent event) {
        Location loc = event.getBlock() != null ? event.getBlock().getLocation() : null;
        if (event.getPlayer() != null) {
            blockInGodOutsideOwnRegion(event.getPlayer(), loc, event, true);
        } else if (event.getIgnitingEntity() != null) {
            Player source = resolvePlayerDamager(event.getIgnitingEntity());
            if (source != null) {
                blockInGodOutsideOwnRegion(source, loc, event, true);
            }
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onBucketEmpty(PlayerBucketEmptyEvent event) {
        blockInGodOutsideOwnRegion(event.getPlayer(), event.getBlock() != null ? event.getBlock().getLocation() : null, event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onBucketFill(PlayerBucketFillEvent event) {
        blockInGodOutsideOwnRegion(event.getPlayer(), event.getBlock() != null ? event.getBlock().getLocation() : null, event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onBucketEntity(PlayerBucketEntityEvent event) {
        blockInGodOutsideOwnRegion(event.getPlayer(), event.getEntity() != null ? event.getEntity().getLocation() : null, event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onHangingBreak(HangingBreakByEntityEvent event) {
        Player remover = resolvePlayerDamager(event.getRemover());
        if (remover != null) {
            blockInGodOutsideOwnRegion(remover, event.getEntity() != null ? event.getEntity().getLocation() : null, event, true);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onHangingPlace(HangingPlaceEvent event) {
        if (event.getPlayer() != null) {
            blockInGodOutsideOwnRegion(event.getPlayer(), event.getEntity() != null ? event.getEntity().getLocation() : null, event, true);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onShear(PlayerShearEntityEvent event) {
        blockInGodOutsideOwnRegion(event.getPlayer(), event.getEntity() != null ? event.getEntity().getLocation() : null, event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onLeash(PlayerLeashEntityEvent event) {
        blockInGodOutsideOwnRegion(event.getPlayer(), event.getEntity() != null ? event.getEntity().getLocation() : null, event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onUnleash(PlayerUnleashEntityEvent event) {
        blockInGodOutsideOwnRegion(event.getPlayer(), event.getEntity() != null ? event.getEntity().getLocation() : null, event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onEntityChangeBlock(EntityChangeBlockEvent event) {
        Player actor = resolvePlayerDamager(event.getEntity());
        if (actor != null) {
            blockInGodOutsideOwnRegion(actor, event.getBlock() != null ? event.getBlock().getLocation() : null, event, false);
        }
    }
}
