package pw.elytrix.eventguard;

import java.io.File;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Level;

import org.bukkit.Bukkit;
import org.bukkit.ChatMessageType;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.EnderCrystal;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityExplodeEvent;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.event.player.PlayerCommandPreprocessEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.plugin.Plugin;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitTask;
import net.md_5.bungee.api.chat.TextComponent;

/**
 * ElytrixEventGuard v1.1.0.
 *
 * <p>Four small, very targeted rules the owner asked for, each one independently
 * switchable in {@code plugins/ElytrixEventGuard/config.yml}:</p>
 *
 * <ol>
 *   <li><b>/fly on the Talisman and the Airdrop.</b> LuckPerms groups {@code moder}
 *       and above (by group weight) and {@code *} keep their fly: while such a
 *       player stands inside an active event zone the plugin re-asserts
 *       {@code setAllowFlight(true)} every tick, so a guard that strips fly
 *       (ElytrixGodPickup, the NMascot talisman guard, ElytrixAir) simply cannot
 *       win. A player who was not flying is never touched.</li>
 *   <li><b>The auction refuses god/fly.</b> Every auction command is cancelled for
 *       a player who is currently in {@code /god} or {@code /fly}; the reason is
 *       written ONLY into the action bar (the "auction bar"), drawn in the tiny
 *       resource-pack font {@code reallyworld:small}, never into the chat.</li>
 *   <li><b>Picking things up in god/fly is refused loudly.</b> ElytrixGodPickup
 *       silently cancelled {@code EntityPickupItemEvent}; now the player is told,
 *       in the same small action bar, that /god or /fly must be switched off first.</li>
 *   <li><b>Staff are above the rules.</b> Whoever keeps /fly on events (LuckPerms
 *       moder and above, and {@code *}) is also exempt from the auction and the
 *       pickup prohibition - the point of the rule is to stop donors from abusing
 *       god/fly, not to get in the way of the staff.</li>
 *   <li><b>End crystals stop eating blocks.</b> {@code EntityExplodeEvent} from an
 *       {@code EnderCrystal} keeps its entity damage but loses its block list.</li>
 * </ol>
 *
 * <p>On top of that the plugin makes sure the two donation groups the site sells
 * actually exist in LuckPerms: on startup it runs a short list of {@code lp}
 * console commands (see {@code luckperms.setup}), all of them idempotent.</p>
 *
 * <p>Every cross-plugin call (LuckPerms, NMascot, Essentials) is reflective and
 * cached, so the plugin loads and keeps working when one of them is missing or is
 * hot-reloaded by PlugManX.</p>
 */
public final class EventGuard extends JavaPlugin implements Listener {

    public static final String VERSION = "1.2.0";
    public static final String BYPASS_PERMISSION = "elytrix.eventguard.bypass";

    private static final String PREFIX = "\u00a7x\u00a7F\u00a78\u00a7B\u00a7E\u00a7F\u00a7BElytrix \u00a78\u00bb \u00a7f";

    /** How often the action bar may be refreshed, in milliseconds. */
    private static final long BAR_COOLDOWN_MS = 1200L;
    /** How often the same notice may reach the chat, in milliseconds. */
    private static final long CHAT_COOLDOWN_MS = 5000L;

    private final Set<String> exemptGroups = new LinkedHashSet<String>();
    private final Set<String> auctionCommands = new LinkedHashSet<String>();
    private final Map<UUID, boolean[]> seen = new ConcurrentHashMap<UUID, boolean[]>();
    private final Map<UUID, Long> reseedAt = new ConcurrentHashMap<UUID, Long>();
    private final Map<UUID, Long> lastBar = new ConcurrentHashMap<UUID, Long>();
    private final Map<UUID, Long> lastChat = new ConcurrentHashMap<UUID, Long>();
    private final List<String> luckPermsSetup = new ArrayList<String>();

    private volatile boolean flyGuard = true;
    private volatile String referenceGroup = "moder";
    private volatile int referenceWeight = -1;
    private volatile boolean talisman = true;
    private volatile boolean airdrop = true;
    private volatile int airdropRadius = 60;
    private volatile double airdropX = 1850.0;
    private volatile double airdropZ = 1850.0;
    private volatile String airdropWorld = "world";
    private volatile int interval = 1;

    private volatile boolean auctionGuard = true;
    private volatile String auctionMessage = "";

    private volatile boolean pickupGuard = true;
    private volatile String pickupMessage = "";

    private volatile boolean chatNotice = false;
    private volatile String barFont = "";

    private volatile boolean crystalsBreakBlocks = false;
    private volatile boolean crystalsLog = false;

    private volatile boolean lpSetup = true;
    private volatile int lpSetupDelay = 60;

    private volatile BukkitTask task;

    // ---------------------------------------------------------------- lifecycle

    @Override
    public void onEnable() {
        saveDefaultConfig();
        reload();
        Bukkit.getPluginManager().registerEvents(this, this);
        startTask();
        setupLuckPerms();
        getLogger().info("ElytrixEventGuard v" + VERSION + " enabled (fly guard on Talisman/Airdrop"
                + ", auction + pickup refuse god/fly in the action bar"
                + ", end crystals keep the blocks).");
    }

    @Override
    public void onDisable() {
        BukkitTask t = task;
        task = null;
        if (t != null) {
            t.cancel();
        }
        seen.clear();
        reseedAt.clear();
        lastBar.clear();
        lastChat.clear();
    }

    /** Re-reads the config and re-arms the watcher. */
    public void reload() {
        FileConfiguration cfg = getConfig();
        flyGuard = cfg.getBoolean("fly-guard.enabled", true);
        referenceGroup = cfg.getString("fly-guard.reference-group", "moder");
        exemptGroups.clear();
        List<String> groups = cfg.getStringList("fly-guard.groups");
        if (groups != null) {
            for (String g : groups) {
                if (g != null && g.length() > 0) {
                    exemptGroups.add(g.toLowerCase(Locale.ROOT));
                }
            }
        }
        talisman = cfg.getBoolean("fly-guard.talisman.enabled", true);
        airdrop = cfg.getBoolean("fly-guard.airdrop.enabled", true);
        airdropRadius = Math.max(1, cfg.getInt("fly-guard.airdrop.radius", 60));
        interval = Math.max(1, cfg.getInt("fly-guard.check-interval-ticks", 1));

        auctionGuard = cfg.getBoolean("auction.enabled", true);
        auctionCommands.clear();
        List<String> cmds = cfg.getStringList("auction.commands");
        if (cmds != null) {
            for (String c : cmds) {
                if (c != null && c.length() > 1) {
                    auctionCommands.add(c.substring(c.charAt(0) == '/' ? 1 : 0).toLowerCase(Locale.ROOT));
                }
            }
        }
        if (auctionCommands.isEmpty()) {
            auctionCommands.add("auction");
            auctionCommands.add("ah");
        }
        auctionMessage = colour(cfg.getString("auction.message",
                PREFIX + "Нельзя пользоваться аукционом в /god или /fly!"));

        pickupGuard = cfg.getBoolean("pickup.enabled", true);
        pickupMessage = colour(cfg.getString("pickup.message",
                PREFIX + "Нельзя поднимать предметы в /god или /fly!"));
        chatNotice = cfg.getBoolean("notice.chat", false);
        barFont = cfg.getString("notice.font", "");
        if (barFont != null) {
            barFont = barFont.trim();
        }

        crystalsBreakBlocks = cfg.getBoolean("crystals.break-blocks", false);
        crystalsLog = cfg.getBoolean("crystals.log", false);

        lpSetup = cfg.getBoolean("luckperms.enabled", true);
        lpSetupDelay = Math.max(1, cfg.getInt("luckperms.delay-ticks", 60));
        luckPermsSetup.clear();
        List<String> setup = cfg.getStringList("luckperms.setup");
        if (setup != null) {
            for (String line : setup) {
                if (line != null && line.trim().length() > 0) {
                    luckPermsSetup.add(line.trim());
                }
            }
        }

        try {
            File air = new File(getDataFolder().getParentFile(), "ElytrixAir/config.yml");
            if (air.isFile()) {
                YamlConfiguration yml = YamlConfiguration.loadConfiguration(air);
                airdropX = yml.getDouble("xCords", airdropX);
                airdropZ = yml.getDouble("zCords", airdropZ);
                airdropWorld = yml.getString("worldName", airdropWorld);
            }
        } catch (Throwable ignored) {
            // ElytrixAir missing or unreadable -> keep the configured defaults
        }
        referenceWeight = -1;   // resolved lazily, LuckPerms may load after us
        seen.clear();
        reseedAt.clear();
    }

    private void startTask() {
        BukkitTask t = task;
        if (t != null) {
            t.cancel();
        }
        task = Bukkit.getScheduler().runTaskTimer(this, new Runnable() {
            public void run() {
                try {
                    tick();
                } catch (Throwable failure) {
                    getLogger().log(Level.WARNING, "ElytrixEventGuard tick failed", failure);
                }
            }
        }, 20L, Math.max(1L, interval));
    }

    // ------------------------------------------------------------------ fly guard

    private void tick() {
        if (!flyGuard) {
            return;
        }
        Collection<? extends Player> players = Bukkit.getOnlinePlayers();
        if (players == null) {
            return;
        }
        for (Player player : players) {
            UUID id = player.getUniqueId();
            boolean inside = (talisman && insideTalisman(player)) || (airdrop && insideAirdrop(player));
            if (!isExempt(player) || !inside) {
                seen.remove(id);
                reseedAt.remove(id);
                continue;
            }
            boolean allow = player.getAllowFlight();
            boolean flying = player.isFlying();

            Long until = reseedAt.get(id);
            if (until != null) {
                if (System.currentTimeMillis() < until.longValue()) {
                    seen.put(id, new boolean[] {allow, flying});
                    continue;
                }
                reseedAt.remove(id);
            }

            boolean[] previous = seen.get(id);
            seen.put(id, new boolean[] {allow, flying});
            if (previous == null || !previous[0] || allow) {
                continue;
            }
            // He was allowed to fly a moment ago inside an event zone and now he is
            // not: some guard took it, so hand it straight back.
            player.setAllowFlight(true);
            if (previous[1] && !flying && !isFreeFlight(player)) {
                player.setFlying(true);
            }
            seen.put(id, new boolean[] {player.getAllowFlight(), player.isFlying()});
        }
    }

    private static boolean isFreeFlight(Player player) {
        GameMode gm = player.getGameMode();
        return gm == GameMode.CREATIVE || gm == GameMode.SPECTATOR;
    }

    /** True for LuckPerms groups moder and above, for {@code *}, and for the explicit bypass. */
    public boolean isExempt(Player player) {
        if (player == null) {
            return false;
        }
        try {
            if (player.hasPermission(BYPASS_PERMISSION)) {
                return true;
            }
        } catch (Throwable ignored) {
            // a broken permission backend must never make us strip fly
        }
        String group = primaryGroup(player);
        if (group == null) {
            return false;
        }
        String lower = group.toLowerCase(Locale.ROOT);
        if (exemptGroups.contains(lower)) {
            return true;
        }
        int weight = groupWeight(player, group);
        int ref = referenceWeight(player);
        return ref > 0 && weight >= ref;
    }

    /** The single exemption rule, exposed so ElytrixGodPickup and the NMascot
     *  talisman guard can ask us before they strip anybody's fly. */
    public boolean isFlyExempt(Player player) {
        return flyGuard && isExempt(player);
    }

    // ------------------------------------------------------- LuckPerms (reflection)

    private static Object luckPerms() {
        try {
            return Class.forName("net.luckperms.api.LuckPermsProvider")
                    .getMethod("get").invoke(null);
        } catch (Throwable ignored) {
            return null;
        }
    }

    public String primaryGroup(Player player) {
        Object api = luckPerms();
        if (api == null || player == null) {
            return null;
        }
        try {
            Object users = api.getClass().getMethod("getUserManager").invoke(api);
            Object user = users.getClass().getMethod("getUser", UUID.class)
                    .invoke(users, player.getUniqueId());
            if (user == null) {
                return null;
            }
            Object value = user.getClass().getMethod("getPrimaryGroup").invoke(user);
            return value == null ? null : String.valueOf(value);
        } catch (Throwable ignored) {
            return null;
        }
    }

    private int groupWeight(Player player, String group) {
        Object api = luckPerms();
        if (api == null || group == null) {
            return 0;
        }
        try {
            Object groups = api.getClass().getMethod("getGroupManager").invoke(api);
            Object node = groups.getClass().getMethod("getGroup", String.class).invoke(groups, group);
            if (node == null) {
                return 0;
            }
            Object weight = node.getClass().getMethod("getWeight").invoke(node);
            if (weight instanceof java.util.OptionalInt) {
                java.util.OptionalInt opt = (java.util.OptionalInt) weight;
                return opt.isPresent() ? opt.getAsInt() : 0;
            }
        } catch (Throwable ignored) {
            // fall through
        }
        return 0;
    }

    private int referenceWeight(Player player) {
        int cached = referenceWeight;
        if (cached >= 0) {
            return cached;
        }
        int resolved = groupWeight(player, referenceGroup);
        referenceWeight = resolved;
        return resolved;
    }

    /** Makes sure the donation groups the site sells really exist. Every command in
     *  the list is idempotent, so running it on every start is safe. */
    private void setupLuckPerms() {
        if (!lpSetup || luckPermsSetup.isEmpty()) {
            return;
        }
        final int delay = lpSetupDelay;
        Bukkit.getScheduler().runTaskLater(this, new Runnable() {
            public void run() {
                runLuckPermsSetup();
            }
        }, delay);
    }

    /** Dispatches every command from {@code luckperms.setup}. Safe to re-run at any
     *  time (and bound to {@code /eventguard setup}), which is how the groups get
     *  created on a server that never restarts. */
    public int runLuckPermsSetup() {
        int applied = 0;
        for (String line : luckPermsSetup) {
            try {
                Bukkit.dispatchCommand(Bukkit.getConsoleSender(), line);
                applied++;
            } catch (Throwable ignored) {
                // a refused command must never break the startup
            }
        }
        getLogger().info("LuckPerms setup: " + applied + " command(s) applied");
        return applied;
    }

    // ----------------------------------------------------------------- commands

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (args == null || args.length == 0) {
            sender.sendMessage(PREFIX + "ElytrixEventGuard v" + VERSION);
            sender.sendMessage("  /" + label + " status  - что включено и что видит плагин");
            sender.sendMessage("  /" + label + " setup   - создать группы LuckPerms fame и dmoder");
            sender.sendMessage("  /" + label + " reload  - перечитать config.yml");
            return true;
        }
        String sub = args[0].toLowerCase(Locale.ROOT);
        if (sub.equals("reload")) {
            reload();
            setupLuckPerms();
            sender.sendMessage(PREFIX + "config.yml перечитан, настройка LuckPerms запланирована.");
            return true;
        }
        if (sub.equals("setup")) {
            int applied = runLuckPermsSetup();
            sender.sendMessage(PREFIX + "Выполнено " + applied + " lp-команд из luckperms.setup.");
            return true;
        }
        if (sub.equals("status")) {
            sender.sendMessage(PREFIX + "v" + VERSION);
            sender.sendMessage("  /fly на ивентах: " + onOff(flyGuard)
                    + " (талисман " + onOff(talisman) + ", аирдроп " + onOff(airdrop) + ")");
            sender.sendMessage("  аукцион в /god и /fly: " + onOff(auctionGuard));
            sender.sendMessage("  подбор предметов в /god и /fly: " + onOff(pickupGuard));
            sender.sendMessage("  сообщение в чате: " + onOff(chatNotice)
                    + " (основной канал - экшен-бар, шрифт "
                    + (barFont.isEmpty() ? "обычный" : barFont) + ")");
            sender.sendMessage("  кристаллы ломают блоки: " + onOff(crystalsBreakBlocks));
            sender.sendMessage("  настройка LuckPerms: " + onOff(lpSetup)
                    + " (" + luckPermsSetup.size() + " команд)");
            return true;
        }
        sender.sendMessage(PREFIX + "Неизвестная команда. Доступно: status, setup, reload.");
        return true;
    }

    private static String onOff(boolean value) {
        return value ? "§aвкл§f" : "§cвыкл§f";
    }

    // --------------------------------------------------------------- zone detection

    public boolean insideTalisman(Player player) {
        try {
            Plugin plugin = Bukkit.getPluginManager().getPlugin("NMascot");
            if (plugin == null || !plugin.isEnabled()) {
                return false;
            }
            Object api = plugin.getClass().getMethod("getInstance").invoke(plugin);
            Object manager = api.getClass().getMethod("getMascotManager").invoke(api);
            if (manager == null) {
                return false;
            }
            Object mascot = manager.getClass().getMethod("getMascot").invoke(manager);
            Object state = manager.getClass().getMethod("getState").invoke(manager);
            if (mascot == null || state == null || !"STARTED".equalsIgnoreCase(String.valueOf(state))) {
                return false;
            }
            String region = (String) manager.getClass().getMethod("getRegionName").invoke(manager);
            if (region == null || region.isEmpty()) {
                return false;
            }
            Class<?> util = Class.forName("ru.Travka.util.RegionUtil");
            Object hit = util.getMethod("isPlayerInRegion", Player.class, String.class)
                    .invoke(null, player, region);
            return Boolean.TRUE.equals(hit);
        } catch (Throwable ignored) {
            return false;
        }
    }

    public boolean insideAirdrop(Player player) {
        Location loc = player.getLocation();
        if (loc == null) {
            return false;
        }
        World world = loc.getWorld();
        if (world == null || airdropWorld == null || !airdropWorld.equals(world.getName())) {
            return false;
        }
        return Math.abs(loc.getX() - airdropX) <= airdropRadius
                && Math.abs(loc.getZ() - airdropZ) <= airdropRadius;
    }

    // ------------------------------------------------------------------ auction

    @EventHandler(priority = EventPriority.LOWEST)
    public void onCommand(PlayerCommandPreprocessEvent event) {
        if (!auctionGuard) {
            return;
        }
        String message = event.getMessage();
        if (message == null || message.length() < 2 || message.charAt(0) != '/') {
            return;
        }
        String head = message.substring(1);
        int cut = head.indexOf(' ');
        if (cut > 0) {
            head = head.substring(0, cut);
        }
        int colon = head.indexOf(':');
        if (colon >= 0) {
            head = head.substring(colon + 1);
        }
        if (!auctionCommands.contains(head.toLowerCase(Locale.ROOT))) {
            return;
        }
        Player player = event.getPlayer();
        if (!inGod(player) && !inFly(player)) {
            return;
        }
        if (isExempt(player)) {
            return;                 // moder and above, and *, are above the rule
        }
        event.setCancelled(true);
        notify(player, auctionMessage);
    }

    // --------------------------------------------------------------- item pickup

    /** ElytrixGodPickup cancels pickups in /god and /fly without a word; this is the word. */
    @EventHandler(priority = EventPriority.LOW)
    public void onPickup(EntityPickupItemEvent event) {
        if (!pickupGuard || event == null) {
            return;
        }
        Entity entity = event.getEntity();
        if (!(entity instanceof Player)) {
            return;
        }
        Player player = (Player) entity;
        if (!inGod(player) && !inFly(player)) {
            return;
        }
        if (isExempt(player)) {
            return;                 // moder and above, and *, are above the rule
        }
        event.setCancelled(true);
        notify(player, pickupMessage);
    }

    /** Remembers the fly state the player asked for right after a /fly command. */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onAnyCommand(PlayerCommandPreprocessEvent event) {
        if (event.getPlayer() == null) {
            return;
        }
        String message = event.getMessage();
        if (message == null || message.length() < 2) {
            return;
        }
        String head = message.substring(1).toLowerCase(Locale.ROOT);
        if (!(head.equals("fly") || head.equals("efly") || head.startsWith("fly ")
                || head.startsWith("efly ") || head.startsWith("essentials:fly"))) {
            return;
        }
        reseedAt.put(event.getPlayer().getUniqueId(), Long.valueOf(System.currentTimeMillis() + 250L));
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent event) {
        if (event.getPlayer() != null) {
            UUID id = event.getPlayer().getUniqueId();
            seen.remove(id);
            reseedAt.remove(id);
            lastBar.remove(id);
            lastChat.remove(id);
        }
    }

    // ----------------------------------------------------------------- crystals

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onExplode(EntityExplodeEvent event) {
        if (crystalsBreakBlocks || event == null) {
            return;
        }
        if (!(event.getEntity() instanceof EnderCrystal)) {
            return;
        }
        List<?> blocks = event.blockList();
        if (blocks == null || blocks.isEmpty()) {
            return;
        }
        int size = blocks.size();
        blocks.clear();
        if (crystalsLog) {
            getLogger().info("crystal explosion: kept " + size + " blocks");
        }
    }

    // -------------------------------------------------------------------- helpers

    /** Writes the refusal into the action bar (the "auction bar") and, much more
     *  rarely, into the chat, so the bar can never be spammed. */
    public void notify(Player player, String message) {
        if (player == null || message == null || message.isEmpty()) {
            return;
        }
        long now = System.currentTimeMillis();
        UUID id = player.getUniqueId();

        Long barUntil = lastBar.get(id);
        if (barUntil == null || now >= barUntil.longValue()) {
            lastBar.put(id, Long.valueOf(now + BAR_COOLDOWN_MS));
            TextComponent bar = new TextComponent(message);
            applyFont(bar, barFont);
            try {
                player.spigot().sendMessage(ChatMessageType.ACTION_BAR, bar);
            } catch (Throwable ignored) {
                // no action bar on this server -> nothing we can do
            }
        }
        if (!chatNotice) {
            return;
        }
        Long chatUntil = lastChat.get(id);
        if (chatUntil == null || now >= chatUntil.longValue()) {
            lastChat.put(id, Long.valueOf(now + CHAT_COOLDOWN_MS));
            player.sendMessage(message);
        }
    }

    /** Puts the tiny resource-pack font on a component. Both the current and the
     *  legacy bungee-chat setter are tried, so a missing font never breaks the
     *  notice - it simply falls back to the normal font. */
    private static void applyFont(TextComponent component, String font) {
        if (component == null || font == null || font.isEmpty()) {
            return;
        }
        try {
            component.getClass().getMethod("setFont", String.class).invoke(component, font);
            return;
        } catch (Throwable ignored) {
            // older bungee-chat only has setFontRaw
        }
        try {
            component.getClass().getMethod("setFontRaw", String.class).invoke(component, font);
        } catch (Throwable ignored) {
            // no font support at all -> plain text
        }
    }

    /** Fly is "on" when the player may fly at all — the same rule the auction uses. */
    public boolean inFly(Player player) {
        return player != null && (player.isFlying() || player.getAllowFlight());
    }

    public boolean inGod(Player player) {
        if (player == null) {
            return false;
        }
        try {
            Plugin ess = Bukkit.getPluginManager().getPlugin("Essentials");
            if (ess == null || !ess.isEnabled()) {
                return false;
            }
            Object user = ess.getClass().getMethod("getUser", Player.class).invoke(ess, player);
            if (user == null) {
                return false;
            }
            Object god = user.getClass().getMethod("isGodModeEnabled").invoke(user);
            return Boolean.TRUE.equals(god);
        } catch (Throwable ignored) {
            return false;
        }
    }

    private static String colour(String text) {
        return text == null ? "" : text.replace('&', '\u00a7');
    }

    // --------------------------------------------------------------- test hooks

    public void runTickForTest() {
        tick();
    }

    public List<String> auctionCommandsForTest() {
        return new ArrayList<String>(auctionCommands);
    }

    public Set<String> exemptGroupsForTest() {
        return new LinkedHashSet<String>(exemptGroups);
    }

    public List<String> luckPermsSetupForTest() {
        return new ArrayList<String>(luckPermsSetup);
    }

    public String pickupMessageForTest() {
        return pickupMessage;
    }

    public String barFontForTest() {
        return barFont;
    }

    public boolean chatNoticeForTest() {
        return chatNotice;
    }
}
