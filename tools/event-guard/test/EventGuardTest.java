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

    static class Sched implements org.bukkit.scheduler.BukkitScheduler {
        public BukkitTask runTaskTimer(Plugin p, Runnable task, long delay, long period) {
            if (task == null) throw new AssertionError("null task");
            if (period <= 0) throw new AssertionError("non-positive period");
            pending = task;
            return new BukkitTask() { public void cancel() { pending = null; } };
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
        pending = null;
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
        guard.getConfig().set("crystals.break-blocks", Boolean.FALSE);
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
        PlayerCommandPreprocessEvent cmd =
                new PlayerCommandPreprocessEvent(buyer, "/ah");
        guard.onCommand(cmd);
        check(cmd.isCancelled(), "/ah is cancelled for a player in /fly");
        check(buyer.sent.toString().contains("Аукцион"), "and he is told why: " + buyer.sent.toString().trim());

        FakePlayer grounded = new FakePlayer();
        grounded.allowFlight = false;
        PlayerCommandPreprocessEvent ok = new PlayerCommandPreprocessEvent(grounded, "/ah");
        guard.onCommand(ok);
        check(!ok.isCancelled(), "/ah still works for a player on the ground");

        PlayerCommandPreprocessEvent other = new PlayerCommandPreprocessEvent(buyer, "/warp pvp");
        guard.onCommand(other);
        check(!other.isCancelled(), "unrelated commands are untouched");

        PlayerCommandPreprocessEvent pluginNs = new PlayerCommandPreprocessEvent(buyer, "/cloudauction:ah sell 10");
        guard.onCommand(pluginNs);
        check(pluginNs.isCancelled(), "namespaced /cloudauction:ah is cancelled too");

        // --- rule 3: end crystals stop eating blocks --------------------------
        EntityExplodeEvent crystal = new EntityExplodeEvent(new FakeCrystal(), 37);
        guard.onExplode(crystal);
        check(crystal.blockList().isEmpty(), "a crystal explosion loses every block");

        EntityExplodeEvent creeper = new EntityExplodeEvent(new FakeCreeper(), 12);
        guard.onExplode(creeper);
        check(creeper.blockList().size() == 12, "any other explosion still breaks blocks");

        // --- config surface ---------------------------------------------------
        check(guard.auctionCommandsForTest().containsAll(Arrays.asList("auction", "ah", "auc", "cloudauction")),
                "all four auction aliases are guarded");
        check(guard.exemptGroupsForTest().contains("moder") && guard.exemptGroupsForTest().contains("*"),
                "moder and * are on the exempt list");

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
