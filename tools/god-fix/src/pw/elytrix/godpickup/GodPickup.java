package pw.elytrix.godpickup;

import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Predicate;
import net.ess3.api.IEssentials;
import net.ess3.api.IUser;
import net.ess3.api.events.GodStatusChangeEvent;
import org.bukkit.Bukkit;
import org.bukkit.entity.AreaEffectCloud;
import org.bukkit.entity.Entity;
import org.bukkit.entity.HumanEntity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.entity.TNTPrimed;
import org.bukkit.entity.Tameable;
import org.bukkit.event.Cancellable;
import org.bukkit.event.Event;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockDamageEvent;
import org.bukkit.event.block.BlockIgniteEvent;
import org.bukkit.event.block.BlockMultiPlaceEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.block.SignChangeEvent;
import org.bukkit.event.entity.EntityChangeBlockEvent;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.event.entity.EntityShootBowEvent;
import org.bukkit.event.entity.ProjectileLaunchEvent;
import org.bukkit.event.hanging.HangingBreakByEntityEvent;
import org.bukkit.event.hanging.HangingPlaceEvent;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.player.PlayerArmorStandManipulateEvent;
import org.bukkit.event.player.PlayerAttemptPickupItemEvent;
import org.bukkit.event.player.PlayerBedEnterEvent;
import org.bukkit.event.player.PlayerBucketEmptyEvent;
import org.bukkit.event.player.PlayerBucketEntityEvent;
import org.bukkit.event.player.PlayerBucketFillEvent;
import org.bukkit.event.player.PlayerCommandPreprocessEvent;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.bukkit.event.player.PlayerFishEvent;
import org.bukkit.event.player.PlayerInteractAtEntityEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerItemConsumeEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerLeashEntityEvent;
import org.bukkit.event.player.PlayerPickupArrowEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerShearEntityEvent;
import org.bukkit.event.player.PlayerSwapHandItemsEvent;
import org.bukkit.event.player.PlayerUnleashEntityEvent;
import org.bukkit.event.vehicle.VehicleDamageEvent;
import org.bukkit.event.vehicle.VehicleDestroyEvent;
import org.bukkit.event.vehicle.VehicleEnterEvent;
import org.bukkit.plugin.Plugin;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.projectiles.ProjectileSource;

/**
 * Complete Essentials /god (/egod, /godmode, /tgm, /ungod, API) action lockdown
 * + strict 5,000 ms post-god cooldown with zero relog/API/command bypasses.
 */
public final class GodPickup extends JavaPlugin implements Listener {

    public static final long POST_GOD_COOLDOWN_MS = 5000L;
    private static final long NOTIFY_THROTTLE_MS = 1000L;

    private static final String PREFIX = "\u00a7x\u00a7F\u00a78\u00a7B\u00a7E\u00a7F\u00a7BElytrix \u00a78\u00bb \u00a7f";
    private static final String ACCENT = "\u00a7x\u00a7F\u00a78\u00a7B\u00a7E\u00a7F\u00a7B";

    private static final Set<String> GOD_TOGGLE_COMMANDS = Collections.unmodifiableSet(new HashSet<>(Arrays.asList(
            "god", "egod", "godmode", "egodmode", "tgm", "etgm", "ungod", "eungod"
    )));

    private static final Set<String> AUTH_COMMANDS = Collections.unmodifiableSet(new HashSet<>(Arrays.asList(
            "l", "login", "reg", "register"
    )));

    private static final Set<String> BLOCKED_IN_GOD_COMMANDS = Collections.unmodifiableSet(new HashSet<>(Arrays.asList(
            "ec", "eec", "enderchest", "eenderchest", "endersee", "eendersee",
            "invsee", "einvsee", "wb", "ewb", "workbench", "eworkbench", "craft", "ecraft",
            "anvil", "eanvil", "grindstone", "egrindstone", "smithingtable", "esmithingtable",
            "stonecutter", "estonecutter", "loom", "eloom", "cartographytable", "ecartographytable",
            "kit", "ekit", "kits", "ekits", "createkit", "free", "shop",
            "ah", "auc", "auction", "sell", "esell", "sellall", "sellhand",
            "sellmine", "sellfarm", "sellfish", "sellwood", "hjobs",
            "repair", "erepair", "fix", "efix", "repairexp",
            "thor", "ethor", "lightning", "elightning", "shock", "eshock", "smite", "esmite",
            "fireball", "efireball", "nuke", "enuke", "antioch", "eantioch",
            "break", "ebreak", "burn", "eburn", "suicide", "esuicide", "kill",
            "tpahere", "etpahere", "tphere", "etphere", "sethome", "esethome", "createhome",
            "potion", "potions", "crafts", "dealer", "oskolki", "contract", "contracts", "cases", "duel"
    )));

    public enum Restriction {
        NONE,
        ACTIVE_GOD,
        POST_GOD_COOLDOWN
    }

    private IEssentials essentials;
    private Predicate<Player> godReader;
    private final Map<UUID, Boolean> lastGodState = new ConcurrentHashMap<>();
    private final Map<UUID, Long> cooldownUntil = new ConcurrentHashMap<>();
    private final Set<UUID> wasGodOnQuit = ConcurrentHashMap.newKeySet();
    private final Map<UUID, Long> lastNotifyAt = new ConcurrentHashMap<>();

    /** Test hook for unit tests without live Bukkit server. */
    public void initForTest(Predicate<Player> customGodReader) {
        this.godReader = customGodReader;
    }

    @Override
    public void onEnable() {
        Plugin raw = Bukkit.getPluginManager().getPlugin("Essentials");
        if (!(raw instanceof IEssentials) || !raw.isEnabled()) {
            getLogger().severe("Essentials unavailable; disabling ElytrixGodPickup.");
            Bukkit.getPluginManager().disablePlugin(this);
            return;
        }
        this.essentials = (IEssentials) raw;
        this.godReader = p -> {
            IUser user = this.essentials.getUser(p);
            return user != null && user.isGodModeEnabled();
        };
        for (Player online : Bukkit.getOnlinePlayers()) {
            lastGodState.put(online.getUniqueId(), queryEssentialsGod(online));
        }
        Bukkit.getPluginManager().registerEvents(this, this);
        Bukkit.getScheduler().runTaskTimer(this, this::pollOnlinePlayers, 2L, 2L);
    }

    @Override
    public void onDisable() {
        lastGodState.clear();
        lastNotifyAt.clear();
    }

    private void pollOnlinePlayers() {
        long now = System.currentTimeMillis();
        for (Player player : Bukkit.getOnlinePlayers()) {
            evaluateState(player, now);
        }
    }

    private boolean queryEssentialsGod(Player player) {
        if (godReader == null || player == null) {
            return false;
        }
        try {
            return godReader.test(player);
        } catch (RuntimeException | LinkageError ex) {
            getLogger().warning("Cannot read Essentials god mode for " + player.getName() + ": " + ex);
            return true;
        }
    }

    public Restriction evaluateState(Player player, long now) {
        if (player == null) {
            return Restriction.NONE;
        }
        UUID uuid = player.getUniqueId();
        boolean currentlyGod = queryEssentialsGod(player);
        Boolean previous = lastGodState.put(uuid, currentlyGod);

        if (currentlyGod) {
            return Restriction.ACTIVE_GOD;
        }
        if (Boolean.TRUE.equals(previous)) {
            long target = now + POST_GOD_COOLDOWN_MS;
            cooldownUntil.merge(uuid, target, Math::max);
        }
        Long until = cooldownUntil.get(uuid);
        if (until != null) {
            if (now < until) {
                return Restriction.POST_GOD_COOLDOWN;
            }
            cooldownUntil.remove(uuid, until);
        }
        return Restriction.NONE;
    }

    public long getRemainingCooldownMs(UUID uuid, long now) {
        Long until = cooldownUntil.get(uuid);
        if (until == null) {
            return 0L;
        }
        long rem = until - now;
        return Math.max(0L, rem);
    }

    private boolean blockIfRestricted(Player player, Cancellable event, boolean notify) {
        long now = System.currentTimeMillis();
        Restriction state = evaluateState(player, now);
        if (state == Restriction.NONE) {
            return false;
        }
        if (event != null) {
            event.setCancelled(true);
        }
        if (notify) {
            sendRestrictionNotice(player, state, now);
        }
        return true;
    }

    private void sendRestrictionNotice(Player player, Restriction state, long now) {
        UUID uuid = player.getUniqueId();
        Long prev = lastNotifyAt.get(uuid);
        if (prev != null && (now - prev) < NOTIFY_THROTTLE_MS) {
            return;
        }
        lastNotifyAt.put(uuid, now);
        if (state == Restriction.ACTIVE_GOD) {
            player.sendMessage(PREFIX + "В режиме " + ACCENT + "/god \u00a7fнельзя взаимодействовать с миром и игроками!");
        } else if (state == Restriction.POST_GOD_COOLDOWN) {
            long remMs = getRemainingCooldownMs(uuid, now);
            double sec = Math.max(0.1D, Math.ceil(remMs / 100.0D) / 10.0D);
            player.sendMessage(String.format(Locale.US,
                    PREFIX + "Подождите " + ACCENT + "%.1f сек. \u00a7fпосле выключения " + ACCENT + "/god\u00a7f!",
                    sec));
        }
    }

    private static Player resolvePlayerDamager(Entity damager) {
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
        return null;
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onGodStatusChange(GodStatusChangeEvent event) {
        IUser affected = event.getAffected();
        if (affected == null || affected.getBase() == null) {
            return;
        }
        Player target = affected.getBase();
        UUID targetId = target.getUniqueId();
        long now = System.currentTimeMillis();

        IUser controller = event.getController();
        if (controller != null && controller.getBase() != null) {
            Player actor = controller.getBase();
            if (!actor.getUniqueId().equals(targetId) && !actor.hasPermission("elytrix.god.others")) {
                event.setCancelled(true);
                actor.sendMessage(PREFIX + "Вы не можете переключать " + ACCENT + "/god \u00a7fдругим игрокам!");
                return;
            }
        }

        boolean enabling = event.getValue();
        if (enabling) {
            long remMs = getRemainingCooldownMs(targetId, now);
            if (remMs > 0L) {
                event.setCancelled(true);
                sendRestrictionNotice(target, Restriction.POST_GOD_COOLDOWN, now);
                return;
            }
            lastGodState.put(targetId, Boolean.TRUE);
            target.closeInventory();
            if (isEnabled()) {
                Bukkit.getScheduler().runTask(this, target::closeInventory);
            }
        } else {
            lastGodState.put(targetId, Boolean.FALSE);
            cooldownUntil.put(targetId, now + POST_GOD_COOLDOWN_MS);
            target.closeInventory();
            target.sendMessage(PREFIX + "Режим " + ACCENT + "/god \u00a7fвыключен. Подождите " + ACCENT + "5.0 сек. \u00a7fперед действиями!");
        }
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onJoin(PlayerJoinEvent event) {
        Player player = event.getPlayer();
        UUID uuid = player.getUniqueId();
        long now = System.currentTimeMillis();
        boolean currentlyGod = queryEssentialsGod(player);
        lastGodState.put(uuid, currentlyGod);
        if (wasGodOnQuit.remove(uuid) && !currentlyGod) {
            cooldownUntil.merge(uuid, now + POST_GOD_COOLDOWN_MS, Math::max);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onQuit(PlayerQuitEvent event) {
        Player player = event.getPlayer();
        UUID uuid = player.getUniqueId();
        long now = System.currentTimeMillis();
        if (queryEssentialsGod(player) || Boolean.TRUE.equals(lastGodState.remove(uuid))) {
            wasGodOnQuit.add(uuid);
            cooldownUntil.merge(uuid, now + POST_GOD_COOLDOWN_MS, Math::max);
        }
        lastNotifyAt.remove(uuid);
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
        Restriction state = evaluateState(player, now);
        if (state == Restriction.NONE) {
            if (GOD_TOGGLE_COMMANDS.contains(cmd) && parts.length > 1 && !player.hasPermission("elytrix.god.others")) {
                String arg = parts[1];
                if (!arg.equalsIgnoreCase("on") && !arg.equalsIgnoreCase("off")
                        && !arg.equalsIgnoreCase("enable") && !arg.equalsIgnoreCase("disable")
                        && !arg.equalsIgnoreCase(player.getName())) {
                    event.setCancelled(true);
                    player.sendMessage(PREFIX + "Вы не можете переключать " + ACCENT + "/god \u00a7fдругим игрокам!");
                }
            }
            return;
        }

        if (state == Restriction.POST_GOD_COOLDOWN) {
            event.setCancelled(true);
            sendRestrictionNotice(player, state, now);
            return;
        }

        // state == ACTIVE_GOD
        if (GOD_TOGGLE_COMMANDS.contains(cmd)) {
            if (parts.length > 1 && !player.hasPermission("elytrix.god.others")) {
                String arg = parts[1];
                if (!arg.equalsIgnoreCase("on") && !arg.equalsIgnoreCase("off")
                        && !arg.equalsIgnoreCase("enable") && !arg.equalsIgnoreCase("disable")
                        && !arg.equalsIgnoreCase(player.getName())) {
                    event.setCancelled(true);
                    player.sendMessage(PREFIX + "Вы не можете переключать " + ACCENT + "/god \u00a7fдругим игрокам!");
                }
            }
            return;
        }

        if (BLOCKED_IN_GOD_COMMANDS.contains(cmd)) {
            event.setCancelled(true);
            sendRestrictionNotice(player, state, now);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onDamageByEntity(EntityDamageByEntityEvent event) {
        Player attacker = resolvePlayerDamager(event.getDamager());
        if (attacker != null && blockIfRestricted(attacker, event, true)) {
            return;
        }
        if (event.getEntity() instanceof Player) {
            Player victim = (Player) event.getEntity();
            if (evaluateState(victim, System.currentTimeMillis()) == Restriction.ACTIVE_GOD) {
                event.setCancelled(true);
            }
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onProjectileLaunch(ProjectileLaunchEvent event) {
        ProjectileSource shooter = event.getEntity().getShooter();
        if (shooter instanceof Player) {
            blockIfRestricted((Player) shooter, event, true);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onShootBow(EntityShootBowEvent event) {
        if (event.getEntity() instanceof Player) {
            blockIfRestricted((Player) event.getEntity(), event, true);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onFish(PlayerFishEvent event) {
        blockIfRestricted(event.getPlayer(), event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = false)
    public void onInteract(PlayerInteractEvent event) {
        Player player = event.getPlayer();
        long now = System.currentTimeMillis();
        Restriction state = evaluateState(player, now);
        if (state == Restriction.NONE) {
            return;
        }
        event.setCancelled(true);
        event.setUseInteractedBlock(Event.Result.DENY);
        event.setUseItemInHand(Event.Result.DENY);
        if (event.getAction() != Action.PHYSICAL) {
            sendRestrictionNotice(player, state, now);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onInteractEntity(PlayerInteractEntityEvent event) {
        blockIfRestricted(event.getPlayer(), event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onInteractAtEntity(PlayerInteractAtEntityEvent event) {
        blockIfRestricted(event.getPlayer(), event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onArmorStand(PlayerArmorStandManipulateEvent event) {
        blockIfRestricted(event.getPlayer(), event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onInventoryOpen(InventoryOpenEvent event) {
        HumanEntity human = event.getPlayer();
        if (human instanceof Player) {
            blockIfRestricted((Player) human, event, true);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onInventoryClick(InventoryClickEvent event) {
        HumanEntity human = event.getWhoClicked();
        if (human instanceof Player) {
            blockIfRestricted((Player) human, event, true);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onInventoryDrag(InventoryDragEvent event) {
        HumanEntity human = event.getWhoClicked();
        if (human instanceof Player) {
            blockIfRestricted((Player) human, event, true);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onAttemptPickup(PlayerAttemptPickupItemEvent event) {
        if (blockIfRestricted(event.getPlayer(), event, false)) {
            event.setFlyAtPlayer(false);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onEntityPickup(EntityPickupItemEvent event) {
        if (event.getEntity() instanceof Player) {
            blockIfRestricted((Player) event.getEntity(), event, false);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onArrowPickup(PlayerPickupArrowEvent event) {
        blockIfRestricted(event.getPlayer(), event, false);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onDrop(PlayerDropItemEvent event) {
        blockIfRestricted(event.getPlayer(), event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onSwapHand(PlayerSwapHandItemsEvent event) {
        blockIfRestricted(event.getPlayer(), event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onConsume(PlayerItemConsumeEvent event) {
        blockIfRestricted(event.getPlayer(), event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onBlockBreak(BlockBreakEvent event) {
        blockIfRestricted(event.getPlayer(), event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onBlockPlace(BlockPlaceEvent event) {
        blockIfRestricted(event.getPlayer(), event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onBlockMultiPlace(BlockMultiPlaceEvent event) {
        blockIfRestricted(event.getPlayer(), event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onBlockDamage(BlockDamageEvent event) {
        blockIfRestricted(event.getPlayer(), event, false);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onSignChange(SignChangeEvent event) {
        blockIfRestricted(event.getPlayer(), event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onBlockIgnite(BlockIgniteEvent event) {
        if (event.getPlayer() != null) {
            blockIfRestricted(event.getPlayer(), event, true);
        } else if (event.getIgnitingEntity() != null) {
            Player source = resolvePlayerDamager(event.getIgnitingEntity());
            if (source != null) {
                blockIfRestricted(source, event, true);
            }
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onBucketEmpty(PlayerBucketEmptyEvent event) {
        blockIfRestricted(event.getPlayer(), event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onBucketFill(PlayerBucketFillEvent event) {
        blockIfRestricted(event.getPlayer(), event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onBucketEntity(PlayerBucketEntityEvent event) {
        blockIfRestricted(event.getPlayer(), event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onHangingBreak(HangingBreakByEntityEvent event) {
        Player remover = resolvePlayerDamager(event.getRemover());
        if (remover != null) {
            blockIfRestricted(remover, event, true);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onHangingPlace(HangingPlaceEvent event) {
        if (event.getPlayer() != null) {
            blockIfRestricted(event.getPlayer(), event, true);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onVehicleEnter(VehicleEnterEvent event) {
        if (event.getEntered() instanceof Player) {
            blockIfRestricted((Player) event.getEntered(), event, true);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onVehicleDamage(VehicleDamageEvent event) {
        Player attacker = resolvePlayerDamager(event.getAttacker());
        if (attacker != null) {
            blockIfRestricted(attacker, event, true);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onVehicleDestroy(VehicleDestroyEvent event) {
        Player attacker = resolvePlayerDamager(event.getAttacker());
        if (attacker != null) {
            blockIfRestricted(attacker, event, true);
        }
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onShear(PlayerShearEntityEvent event) {
        blockIfRestricted(event.getPlayer(), event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onLeash(PlayerLeashEntityEvent event) {
        blockIfRestricted(event.getPlayer(), event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onUnleash(PlayerUnleashEntityEvent event) {
        blockIfRestricted(event.getPlayer(), event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onBedEnter(PlayerBedEnterEvent event) {
        blockIfRestricted(event.getPlayer(), event, true);
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onEntityChangeBlock(EntityChangeBlockEvent event) {
        Player actor = resolvePlayerDamager(event.getEntity());
        if (actor != null) {
            blockIfRestricted(actor, event, false);
        }
    }
}
