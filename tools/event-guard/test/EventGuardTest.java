import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.UUID;

import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.EnderCrystal;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.entity.EntityExplodeEvent;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.event.player.PlayerCommandPreprocessEvent;
import org.bukkit.plugin.Plugin;
import org.bukkit.plugin.PluginManager;
import org.bukkit.scheduler.BukkitTask;

import pw.elytrix.eventguard.EventGuard;

/** Mock harness: every rule of ElytrixEventGuard is exercised with no server. */
public class EventGuardTest {

    // ------------------------------------------------------------------ mocks

    static class NopPlugin implements Plugin {
        final String name;
        final boolean enabled;
        NopPlugin(String name, boolean enabled) { this.name = name; this.enabled = enabled; }
        public boolean isEnabled() { return enabled; }
        public String getName() { return name; }
    }

    static Runnable pending;
    static Runnable pendingLater;

    static class Sched implements org.bukkit.scheduler.BukkitScheduler {
        public BukkitTask runTaskTimer(Plugin p, Runnable task, long delay, long period) {
            if (task == null) throw new AssertionError("null task");
            if (period <= 0) throw new AssertionError("non-positive period");
            pending = task;
            return new BukkitTask() { public void cancel() { pending = null; } };
        }
        public BukkitTask runTaskLater(Plugin p, Runnable task, long delay) {
            if (task == null) throw new AssertionError("null task");
            if (delay <= 0) throw new AssertionError("non-positive delay");
            pendingLater = task;
            return new BukkitTask() { public void cancel() { pendingLater = null; } };
        }
    }

    static class Mgr implements PluginManager {
        int registered;
        public Plugin getPlugin(String name) { return name.equals("NMascot") ? new NopPlugin(name, false) : null; }
        public void registerEvents(org.bukkit.event.Listener l, Plugin p) { registered++; }
    }

    static class FakeWorld implements World {
        final String name;
        FakeWorld(String name) { this.name = name; }
        public String getName() { return name; }
    }

    static class FakePlayer implements Player {
        final String name = "Travka";
        final UUID id = UUID.randomUUID();
        boolean bypass, allowFlight, flying;
        GameMode mode = GameMode.SURVIVAL;
        double x, z;
        final StringBuilder sent = new StringBuilder();
        final StringBuilder bar = new StringBuilder();
        public String getName() { return name; }
        public UUID getUniqueId() { return id; }
        public boolean hasPermission(String perm) { return bypass && perm.equals(EventGuard.BYPASS_PERMISSION); }
        public boolean getAllowFlight() { return allowFlight; }
        public void setAllowFlight(boolean v) { allowFlight = v; if (!v) flying = false; }
        public boolean isFlying() { return flying; }
        public void setFlying(boolean v) { flying = v && allowFlight; }
        public void sendMessage(String m) { sent.append(m).append('\n'); }
        public GameMode getGameMode() { return mode; }
        public Location getLocation() { return new Location(new FakeWorld("world"), x, 64.0, z); }
        public Spigot spigot() { return new Spigot() {
            public void sendMessage(org.bukkit.ChatMessageType type,
                                    net.md_5.bungee.api.chat.BaseComponent... parts) {
                if (type != org.bukkit.ChatMessageType.ACTION_BAR) throw new AssertionError("wrong bar type");
                bar.append(((net.md_5.bungee.api.chat.TextComponent) parts[0]).text).append('\n');
            }
        }; }
    }

    static class FakeCrystal implements EnderCrystal {}
    static class FakeCreeper implements Entity {}

    // ------------------------------------------------------------------ helpers

    static void check(boolean ok, String what) {
        if (!ok) throw new AssertionError("FAILED: " + what);
        System.out.println("  ok  - " + what);
    }

    static EventGuard boot() {
        Bukkit.manager = new Mgr();
        Bukkit.scheduler = new Sched();
        Bukkit.online = Collections.emptyList();
        Bukkit.dispatched.clear();
        pending = null;
        pendingLater = null;
        EventGuard guard = new EventGuard();
        // the shipped defaults, exactly as they sit in config.yml
        guard.getConfig().set("fly-guard.enabled", Boolean.TRUE);
        guard.getConfig().set("fly-guard.reference-group", "moder");
        guard.getConfig().set("fly-guard.groups", Arrays.asList("*", "owner", "admin", "dadmin",
                "fulladmin", "mladmin", "glmoder", "stmoder", "moderplus", "moder", "dmoder"));
        guard.getConfig().set("fly-guard.talisman.enabled", Boolean.TRUE);
        guard.getConfig().set("fly-guard.airdrop.enabled", Boolean.TRUE);
        guard.getConfig().set("fly-guard.airdrop.radius", Integer.valueOf(60));
        guard.getConfig().set("fly-guard.check-interval-ticks", Integer.valueOf(1));
        guard.getConfig().set("auction.enabled", Boolean.TRUE);
        guard.getConfig().set("auction.commands", Arrays.asList("auction", "ah", "auc", "cloudauction"));
        guard.getConfig().set("auction.message", "&cАукцион закрыт в /god или /fly!");
        guard.getConfig().set("pickup.enabled", Boolean.TRUE);
        guard.getConfig().set("pickup.message", "&cНе поднимай предметы в /god или /fly!");
        guard.getConfig().set("crystals.break-blocks", Boolean.FALSE);
        guard.getConfig().set("luckperms.enabled", Boolean.TRUE);
        guard.getConfig().set("luckperms.delay-ticks", Integer.valueOf(60));
        guard.getConfig().set("luckperms.setup", Arrays.asList(
                "lp creategroup fame", "lp creategroup dmoder",
                "lp group fame parent add pegas",
                "lp group fame permission set nKits.kits.fame true",
                "lp group dmoder parent add moder",
                "lp group dmoder parent add dhelper",
                "lp group moder permission set elytrix.eventguard.bypass true",
                "lp group tiger parent add fame"));
        guard.onEnable();
        return guard;
    }

    // ---------------------------------------------------------------- the tests

    public static void main(String[] args) {
        System.out.println("ElytrixEventGuard v" + EventGuard.VERSION + " mock tests");

        EventGuard guard = boot();

        check(((Mgr) Bukkit.manager).registered == 1, "registers its listener");
        check(pending != null, "arms the fly watcher");

        // --- rule 1: an exempt player keeps /fly inside the airdrop zone -------
        FakePlayer staff = new FakePlayer();
        staff.bypass = true;
        staff.x = 1850.0;
        staff.z = 1850.0;
        staff.allowFlight = true;
        staff.flying = true;
        Bukkit.online = Collections.singletonList(staff);

        check(guard.insideAirdrop(staff), "the airdrop pad is recognised");
        check(guard.isExempt(staff), "an exempt player is exempt");

        guard.runTickForTest();         // the watcher learns he is airborne
        check(staff.allowFlight && staff.flying, "the watcher does not touch a flying player");

        staff.allowFlight = false;      // a guard strips fly
        staff.flying = false;
        guard.runTickForTest();
        check(staff.allowFlight, "fly is given back inside the event zone");
        check(staff.flying, "and the player is put back in the air");

        staff.x = 20.0;                 // walks out of the zone
        staff.allowFlight = false;
        guard.runTickForTest();
        check(!staff.allowFlight, "outside the zone the guard stops interfering");
        staff.x = 1850.0;

        FakePlayer guest = new FakePlayer();
        guest.bypass = false;
        guest.x = 1850.0;
        guest.z = 1850.0;
        guest.allowFlight = false;
        Bukkit.online = Arrays.asList(staff, guest);
        guard.runTickForTest();
        check(!guest.allowFlight, "a non-exempt player gets no fly");

        FakePlayer walker = new FakePlayer();
        walker.bypass = true;
        walker.x = 1850.0;
        walker.z = 1850.0;
        walker.allowFlight = false;     // was not flying to begin with
        Bukkit.online = Collections.singletonList(walker);
        guard.runTickForTest();
        walker.allowFlight = false;
        guard.runTickForTest();
        check(!walker.allowFlight, "an exempt player who was not flying stays on the ground");

        // --- rule 2: the auction refuses god/fly ------------------------------
        FakePlayer buyer = new FakePlayer();
        buyer.allowFlight = true;
        PlayerCommandPreprocessEvent cmd = new PlayerCommandPreprocessEvent(buyer, "/ah");
        guard.onCommand(cmd);
        check(cmd.isCancelled(), "/ah is cancelled for a player in /fly");
        check(buyer.sent.toString().contains("Аукцион"), "and he is told why in the chat");
        check(buyer.bar.toString().contains("Аукцион"),
                "and the reason goes into the action bar (auction bar): " + buyer.bar.toString().trim());

        FakePlayer grounded = new FakePlayer();
        grounded.allowFlight = false;
        PlayerCommandPreprocessEvent ok = new PlayerCommandPreprocessEvent(grounded, "/ah");
        guard.onCommand(ok);
        check(!ok.isCancelled(), "/ah still works for a player on the ground");
        check(grounded.bar.length() == 0 && grounded.sent.length() == 0, "and he is told nothing");

        PlayerCommandPreprocessEvent other = new PlayerCommandPreprocessEvent(buyer, "/warp pvp");
        guard.onCommand(other);
        check(!other.isCancelled(), "unrelated commands are untouched");

        PlayerCommandPreprocessEvent pluginNs = new PlayerCommandPreprocessEvent(buyer, "/cloudauction:ah sell 10");
        guard.onCommand(pluginNs);
        check(pluginNs.isCancelled(), "namespaced /cloudauction:ah is cancelled too");

        // --- rule 3: picking items up in god/fly is refused loudly -------------
        FakePlayer picker = new FakePlayer();
        picker.allowFlight = true;
        EntityPickupItemEvent pickup = new EntityPickupItemEvent(picker);
        guard.onPickup(pickup);
        check(pickup.isCancelled(), "picking an item up in /fly is cancelled");
        check(picker.bar.toString().contains("поднимать") || picker.bar.toString().contains("Не поднимай"),
                "and the action bar says why: " + picker.bar.toString().trim());
        check(picker.sent.toString().contains("Не поднимай"), "and the chat says why too");

        FakePlayer walkerPickup = new FakePlayer();
        EntityPickupItemEvent pickup2 = new EntityPickupItemEvent(walkerPickup);
        guard.onPickup(pickup2);
        check(!pickup2.isCancelled(), "a player on the ground picks items up normally");
        check(walkerPickup.bar.length() == 0, "and sees no bar message");

        // the bar is not spammed: a second notice inside the cooldown is silent
        String before = picker.bar.toString();
        EntityPickupItemEvent pickup3 = new EntityPickupItemEvent(picker);
        guard.onPickup(pickup3);
        check(pickup3.isCancelled(), "the pickup is still cancelled");
        check(picker.bar.toString().equals(before), "the action bar is not spammed");
        check(picker.sent.toString().indexOf('\n') == picker.sent.toString().lastIndexOf('\n'),
                "and neither is the chat");

        EntityPickupItemEvent notPlayer = new EntityPickupItemEvent(new FakeCreeper());
        guard.onPickup(notPlayer);
        check(!notPlayer.isCancelled(), "mobs are unaffected");

        // --- rule 4: end crystals stop eating blocks --------------------------
        EntityExplodeEvent crystal = new EntityExplodeEvent(new FakeCrystal(), 37);
        guard.onExplode(crystal);
        check(crystal.blockList().isEmpty(), "a crystal explosion loses every block");

        EntityExplodeEvent creeper = new EntityExplodeEvent(new FakeCreeper(), 12);
        guard.onExplode(creeper);
        check(creeper.blockList().size() == 12, "any other explosion still breaks blocks");

        // --- rule 5: the LuckPerms groups are created on startup ---------------
        check(pendingLater != null, "the LuckPerms setup is scheduled");
        pendingLater.run();
        String all = String.join("\n", Bukkit.dispatched);
        check(all.contains("lp creategroup fame"), "fame is created");
        check(all.contains("lp creategroup dmoder"), "dmoder is created");
        check(all.contains("lp group fame parent add pegas"), "fame inherits pegas");
        check(all.contains("lp group dmoder parent add moder"), "dmoder inherits moder");
        check(all.contains("lp group dmoder parent add dhelper"), "dmoder inherits dhelper");
        check(all.contains("lp group fame permission set nKits.kits.fame true"), "fame gets its kit");
        check(all.contains("lp group tiger parent add fame"), "old TIGER owners are migrated to FAME");
        check(guard.luckPermsSetupForTest().size() == 8, "all setup commands are loaded");

        // --- config surface ---------------------------------------------------
        check(guard.auctionCommandsForTest().containsAll(Arrays.asList("auction", "ah", "auc", "cloudauction")),
                "all four auction aliases are guarded");
        check(guard.exemptGroupsForTest().contains("moder") && guard.exemptGroupsForTest().contains("*"),
                "moder and * are on the exempt list");
        check(guard.pickupMessageForTest().contains("нельзя") == false
                && guard.pickupMessageForTest().length() > 10, "the pickup message is loaded");

        // --- a reload keeps everything working --------------------------------
        guard.reload();
        Bukkit.online = Collections.singletonList(staff);
        staff.allowFlight = true;
        staff.flying = true;
        guard.runTickForTest();
        staff.allowFlight = false;
        guard.runTickForTest();
        check(staff.allowFlight, "the watcher survives a config reload");

        guard.onDisable();
        check(pending == null, "onDisable cancels the watcher");

        System.out.println("EventGuard mock tests passed");
    }
}
