import com.hokokrtet.hjobs.HJobs;
import com.hokokrtet.hjobs.data.JobStat;
import com.hokokrtet.hjobs.manager.DatabaseManager;
import com.hokokrtet.hjobs.manager.JobManager;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Proxy;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import me.realized.duels.DuelsPlugin;
import me.realized.duels.arena.ArenaManagerImpl;
import me.realized.duels.util.ElytrixDuelTeleportFix;
import net.ess3.api.IUser;
import net.ess3.api.events.GodStatusChangeEvent;
import org.bukkit.Chunk;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.BlockState;
import org.bukkit.block.ShulkerBox;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.enchantments.Enchantment;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.inventory.InventoryType;
import org.bukkit.event.player.PlayerCommandPreprocessEvent;
import org.bukkit.event.player.PlayerToggleFlightEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;
import org.bukkit.inventory.meta.BlockStateMeta;
import org.bukkit.inventory.meta.ItemMeta;
import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassVisitor;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;
import pw.elytrix.godpickup.GodPickup;
import ru.Travka.util.ElytrixMascotGuard;
import ru.penatov.itemkeep.data.ElytrixItemKeepFix;
import sun.misc.Unsafe;
import wtf.n1zamu.clans.Clan;
import wtf.n1zamu.utils.ValidatorUtil;

public final class BugfixVerificationSuite {

    private static Unsafe getUnsafe() throws Exception {
        Field f = Unsafe.class.getDeclaredField("theUnsafe");
        f.setAccessible(true);
        return (Unsafe) f.get(null);
    }

    private static void assertTrue(boolean cond, String msg) {
        if (!cond) {
            throw new AssertionError("ASSERTION FAILED: " + msg);
        }
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 8) {
            throw new IllegalArgumentException(
                    "Usage: BugfixVerificationSuite <god> <hjobs> <nclans> <gc> <duels> <eitems> <nmascot> <itemkeep>");
        }
        Path godJar = Path.of(args[0]);
        Path hjobsJar = Path.of(args[1]);
        Path nclansJar = Path.of(args[2]);
        Path gcJar = Path.of(args[3]);
        Path duelsJar = Path.of(args[4]);
        Path eitemsJar = Path.of(args[5]);
        Path nmascotJar = Path.of(args[6]);
        Path itemkeepJar = Path.of(args[7]);

        verifyBytecodeAll(godJar, hjobsJar, nclansJar, gcJar, duelsJar, eitemsJar, nmascotJar, itemkeepJar);
        testGodAndFlyGameplayRules();
        testDuelsTeleportRaceFix(duelsJar);
        testElytrixItemsAirDropTrapGuard(eitemsJar);
        testNMascotFlyAndGodStrip(nmascotJar);
        testItemKeepEnchantsCloneAndOverflow(itemkeepJar);
        testNClansColorEnforcement();
        testHJobsDatabasePersistence();
        testGreatCombatBytecodeInvariants(gcJar);

        System.out.println("ALL BUGFIX VERIFICATION TESTS PASSED UNDER -Xverify:all!");
    }

    private static void verifyBytecodeAll(Path... jars) throws Exception {
        URL[] urls = new URL[jars.length];
        for (int i = 0; i < jars.length; i++) {
            urls[i] = jars[i].toUri().toURL();
        }
        String[] classesToVerify = new String[]{
                "pw.elytrix.godpickup.GodPickup",
                "com.hokokrtet.hjobs.manager.DatabaseManager",
                "com.hokokrtet.hjobs.manager.JobManager",
                "com.hokokrtet.hjobs.listener.PlayerListener",
                "com.hokokrtet.hjobs.listener.GuiListener",
                "wtf.n1zamu.utils.ValidatorUtil",
                "wtf.n1zamu.clans.Clan",
                "wtf.n1zamu.placeholder.ClanPlaceholder",
                "wtf.n1zamu.function.impl.info.InfoFunction",
                "wtf.n1zamu.level.config.LevelConfiguration",
                "dev.enco.greatcombat.utils.ItemUtils",
                "dev.enco.greatcombat.restrictions.cooldowns.CooldownManager",
                "dev.enco.greatcombat.listeners.PlayerListener",
                "me.realized.duels.util.ElytrixDuelTeleportFix",
                "me.realized.duels.util.ElytrixDuelPerf",
                "me.realized.duels.duel.DuelManager$DuelListener",
                "topka.simbay.rwitems.utils.ElytrixAirTrapGuard",
                "topka.simbay.rwitems.items.ItemEffects$TrapItem",
                "ru.Travka.util.ElytrixMascotGuard",
                "ru.Travka.listener.PlayerMoveListener",
                "ru.penatov.itemkeep.data.ElytrixItemKeepFix",
                "ru.penatov.itemkeep.data.DataManager"
        };
        try (URLClassLoader ucl = new URLClassLoader(urls, BugfixVerificationSuite.class.getClassLoader())) {
            for (String cn : classesToVerify) {
                Class<?> c = Class.forName(cn, false, ucl);
                c.getDeclaredMethods();
                c.getDeclaredConstructors();
            }
        }
        System.out.println("[OK] Bytecode StackMapTable verification passed for all " + classesToVerify.length + " target classes.");
    }

    private static World mockWorld(String name, AtomicInteger droppedCount) {
        return (World) Proxy.newProxyInstance(
                BugfixVerificationSuite.class.getClassLoader(),
                new Class<?>[]{World.class},
                (proxy, method, mArgs) -> {
                    switch (method.getName()) {
                        case "getName":
                            return name;
                        case "dropItemNaturally":
                            if (droppedCount != null) droppedCount.incrementAndGet();
                            return null;
                        case "isChunkLoaded":
                            return true;
                        case "getChunkAt":
                            return Proxy.newProxyInstance(
                                    BugfixVerificationSuite.class.getClassLoader(),
                                    new Class<?>[]{Chunk.class},
                                    (cp, cm, ca) -> true
                            );
                        case "equals":
                            return proxy == mArgs[0];
                        case "hashCode":
                            return name.hashCode();
                        default:
                            Class<?> rt = method.getReturnType();
                            if (rt == boolean.class) return false;
                            return null;
                    }
                }
        );
    }

    private static final class PlayerMockState {
        final UUID uuid;
        final String name;
        final World world;
        final List<String> messages = new ArrayList<>();
        final AtomicBoolean closedInv = new AtomicBoolean(false);
        final AtomicBoolean canPickup = new AtomicBoolean(true);
        final AtomicBoolean god = new AtomicBoolean(false);
        final AtomicBoolean flying = new AtomicBoolean(false);
        final AtomicBoolean allowFlight = new AtomicBoolean(false);
        final AtomicBoolean inVehicle = new AtomicBoolean(false);
        final AtomicBoolean gliding = new AtomicBoolean(false);
        final AtomicBoolean sleeping = new AtomicBoolean(false);
        final Map<String, Object> metadata = new HashMap<>();
        GameMode gameMode = GameMode.SURVIVAL;
        Location location;

        PlayerMockState(UUID uuid, String name, World world) {
            this.uuid = uuid;
            this.name = name;
            this.world = world;
            this.location = new Location(world, 100.0, 65.0, 100.0);
        }
    }

    private static Player mockPlayer(PlayerMockState st, PlayerInventory inv) {
        InvocationHandler h = (proxy, method, mArgs) -> {
            switch (method.getName()) {
                case "getUniqueId":
                    return st.uuid;
                case "getName":
                    return st.name;
                case "isOnline":
                    return true;
                case "isDead":
                    return false;
                case "getWorld":
                    return st.world;
                case "getLocation":
                    return st.location;
                case "getGameMode":
                    return st.gameMode;
                case "hasPermission":
                    return false;
                case "setCanPickupItems":
                    st.canPickup.set((Boolean) mArgs[0]);
                    return null;
                case "getCanPickupItems":
                    return st.canPickup.get();
                case "isFlying":
                    return st.flying.get();
                case "setFlying":
                    st.flying.set((Boolean) mArgs[0]);
                    return null;
                case "getAllowFlight":
                    return st.allowFlight.get();
                case "setAllowFlight":
                    st.allowFlight.set((Boolean) mArgs[0]);
                    return null;
                case "isInsideVehicle":
                    return st.inVehicle.get();
                case "leaveVehicle":
                    st.inVehicle.set(false);
                    return true;
                case "eject":
                    return true;
                case "isGliding":
                    return st.gliding.get();
                case "setGliding":
                    st.gliding.set((Boolean) mArgs[0]);
                    return null;
                case "isSleeping":
                    return st.sleeping.get();
                case "wakeup":
                    st.sleeping.set(false);
                    return null;
                case "teleport":
                    st.location = ((Location) mArgs[0]).clone();
                    return true;
                case "hasMetadata":
                    return st.metadata.containsKey((String) mArgs[0]);
                case "setMetadata":
                    st.metadata.put((String) mArgs[0], mArgs[1]);
                    return null;
                case "removeMetadata":
                    st.metadata.remove((String) mArgs[0]);
                    return null;
                case "getInventory":
                    return inv;
                case "sendMessage":
                    if (mArgs != null && mArgs.length > 0 && mArgs[0] != null) {
                        st.messages.add(String.valueOf(mArgs[0]));
                    }
                    return null;
                case "closeInventory":
                    st.closedInv.set(true);
                    return null;
                case "equals":
                    return proxy == mArgs[0];
                case "hashCode":
                    return st.uuid.hashCode();
                default:
                    Class<?> rt = method.getReturnType();
                    if (rt == boolean.class) return false;
                    if (rt == int.class) return 0;
                    if (rt == long.class) return 0L;
                    if (rt == double.class) return 0.0D;
                    return null;
            }
        };
        return (Player) Proxy.newProxyInstance(
                BugfixVerificationSuite.class.getClassLoader(),
                new Class<?>[]{Player.class},
                h
        );
    }

    private static IUser mockUser(Player base, AtomicBoolean godFlag) {
        return (IUser) Proxy.newProxyInstance(
                BugfixVerificationSuite.class.getClassLoader(),
                new Class<?>[]{IUser.class},
                (proxy, method, args) -> {
                    switch (method.getName()) {
                        case "getBase":
                            return base;
                        case "isGodModeEnabled":
                            return godFlag.get();
                        default:
                            Class<?> rt = method.getReturnType();
                            if (rt == boolean.class) return false;
                            return null;
                    }
                }
        );
    }

    private static Inventory mockContainerInventory(Location blockLoc, InventoryType type) {
        BlockState chestHolder = blockLoc == null ? null : (BlockState) Proxy.newProxyInstance(
                BugfixVerificationSuite.class.getClassLoader(),
                new Class<?>[]{BlockState.class, InventoryHolder.class},
                (p, m, a) -> "getLocation".equals(m.getName()) ? blockLoc : null
        );
        return (Inventory) Proxy.newProxyInstance(
                BugfixVerificationSuite.class.getClassLoader(),
                new Class<?>[]{Inventory.class},
                (p, m, a) -> {
                    if ("getHolder".equals(m.getName())) return chestHolder;
                    if ("getType".equals(m.getName())) return type;
                    if ("getSize".equals(m.getName())) return 27;
                    return null;
                }
        );
    }

    private static void testGodAndFlyGameplayRules() throws Exception {
        World world = mockWorld("world", null);
        PlayerMockState s1 = new PlayerMockState(UUID.randomUUID(), "AdminOne", world);
        PlayerMockState s2 = new PlayerMockState(UUID.randomUUID(), "EnemyTwo", world);
        Player p1 = mockPlayer(s1, null);
        Player p2 = mockPlayer(s2, null);
        Mob zombie = (Mob) Proxy.newProxyInstance(
                BugfixVerificationSuite.class.getClassLoader(),
                new Class<?>[]{Mob.class},
                (proxy, method, args) -> {
                    if ("getUniqueId".equals(method.getName())) return UUID.randomUUID();
                    if (method.getReturnType() == boolean.class) return false;
                    return null;
                }
        );

        IUser iu1 = mockUser(p1, s1.god);
        IUser iu2 = mockUser(p2, s2.god);

        Location ownRegionChestLoc = new Location(world, 10.0, 64.0, 10.0);
        Location foreignChestLoc = new Location(world, 500.0, 64.0, 500.0);
        AtomicBoolean inTalisman = new AtomicBoolean(false);

        GodPickup plugin = new GodPickup();
        plugin.initForTestFull(
                p -> p == p1 ? s1.god.get() : (p == p2 && s2.god.get()),
                p -> p == p1 ? (s1.flying.get() || s1.allowFlight.get()) : (p == p2 && (s2.flying.get() || s2.allowFlight.get())),
                (p, loc) -> p == p1 && loc != null && loc.distanceSquared(ownRegionChestLoc) < 1.0,
                p -> p == p1 && inTalisman.get(),
                p -> {
                    if (p == p1) s1.god.set(false);
                    if (p == p2) s2.god.set(false);
                },
                p -> {
                    if (p == p1) {
                        s1.flying.set(false);
                        s1.allowFlight.set(false);
                    }
                }
        );

        // 1. Prevent /god <otherPlayer> griefing
        GodStatusChangeEvent griefAttempt = new GodStatusChangeEvent(iu2, iu1, true);
        plugin.handleGodToggleAttempt(p1, p2, true, griefAttempt);
        assertTrue(griefAttempt.isCancelled(), "Toggling /god on another player must be cancelled");

        // 2. Enable /god on self
        GodStatusChangeEvent enableGod = new GodStatusChangeEvent(iu1, iu1, true);
        s1.god.set(true);
        plugin.handleGodToggleAttempt(p1, p1, true, enableGod);
        assertTrue(!enableGod.isCancelled(), "Self /god enable must succeed");
        assertTrue(!s1.canPickup.get(), "NMS canPickupItems must be false in /god");

        // 3. In /god: hitting MOBS is ALLOWED, hitting PLAYERS is BLOCKED!
        EntityDamageByEntityEvent hitMobInGod = new EntityDamageByEntityEvent(p1, zombie);
        plugin.onDamageByEntity(hitMobInGod);
        assertTrue(!hitMobInGod.isCancelled(), "Hitting mobs in /god MUST BE ALLOWED");

        EntityDamageByEntityEvent hitPlayerInGod = new EntityDamageByEntityEvent(p1, p2);
        plugin.onDamageByEntity(hitPlayerInGod);
        assertTrue(hitPlayerInGod.isCancelled(), "Hitting players in /god MUST BE CANCELLED");

        // 4. In /god: opening chest in OWN WorldGuard region is ALLOWED, foreign/unclaimed chest is BLOCKED, virtual GUI menu is ALLOWED!
        InventoryOpenEvent ownChestInGod = new InventoryOpenEvent(p1, mockContainerInventory(ownRegionChestLoc, InventoryType.CHEST));
        plugin.onInventoryOpen(ownChestInGod);
        assertTrue(!ownChestInGod.isCancelled(), "Opening chest in own WorldGuard region in /god MUST BE ALLOWED");

        InventoryOpenEvent foreignChestInGod = new InventoryOpenEvent(p1, mockContainerInventory(foreignChestLoc, InventoryType.CHEST));
        plugin.onInventoryOpen(foreignChestInGod);
        assertTrue(foreignChestInGod.isCancelled(), "Opening chest outside own WG region in /god MUST BE BLOCKED");

        InventoryOpenEvent menuInGod = new InventoryOpenEvent(p1, mockContainerInventory(null, InventoryType.CHEST));
        plugin.onInventoryOpen(menuInGod);
        assertTrue(!menuInGod.isCancelled(), "Opening virtual GUI menu in /god MUST BE ALLOWED");

        // 5. Item pickup in /god is BLOCKED
        EntityPickupItemEvent pickupInGod = new EntityPickupItemEvent(p1);
        plugin.onEntityPickup(pickupInGod);
        assertTrue(pickupInGod.isCancelled(), "Item pickup in /god MUST BE BLOCKED");

        // 6. Disable /god -> 5.0s PvP cooldown starts; mob hits & item pickup work immediately after /god off, PvP blocked for 5.0s!
        GodStatusChangeEvent disableGod = new GodStatusChangeEvent(iu1, iu1, false);
        s1.god.set(false);
        plugin.handleGodToggleAttempt(p1, p1, false, disableGod);
        assertTrue(s1.canPickup.get(), "canPickupItems restored when neither /god nor /fly is active");

        EntityDamageByEntityEvent hitPlayerInGodCd = new EntityDamageByEntityEvent(p1, p2);
        plugin.onDamageByEntity(hitPlayerInGodCd);
        assertTrue(hitPlayerInGodCd.isCancelled(), "PvP during 5s post-god cooldown MUST BE BLOCKED");

        EntityDamageByEntityEvent hitMobInGodCd = new EntityDamageByEntityEvent(p1, zombie);
        plugin.onDamageByEntity(hitMobInGodCd);
        assertTrue(!hitMobInGodCd.isCancelled(), "Mob combat during 5s post-god cooldown MUST BE ALLOWED");

        GodStatusChangeEvent panicGod = new GodStatusChangeEvent(iu1, iu1, true);
        plugin.handleGodToggleAttempt(p1, p1, true, panicGod);
        assertTrue(panicGod.isCancelled(), "Panic re-enabling /god during 5s cooldown MUST BE CANCELLED");

        // Clear cooldowns via evaluateState at +6000ms
        long futureTs = System.currentTimeMillis() + 6000L;
        assertTrue(plugin.evaluateState(p1, futureTs) == GodPickup.Restriction.NONE,
                "5s post-god cooldown must clear after 5000ms");

        // 7. Test /fly rules: item pickup BLOCKED, non-own WG chest BLOCKED, own WG chest ALLOWED, mob combat ALLOWED, PvP BLOCKED + 5.0s post-fly PvP cooldown!
        s1.allowFlight.set(true);
        s1.flying.set(true);
        plugin.onToggleFlight(new PlayerToggleFlightEvent(p1, true));
        assertTrue(!s1.canPickup.get(), "NMS canPickupItems must be false in /fly");

        EntityPickupItemEvent pickupInFly = new EntityPickupItemEvent(p1);
        plugin.onEntityPickup(pickupInFly);
        assertTrue(pickupInFly.isCancelled(), "Item pickup in /fly MUST BE BLOCKED");

        InventoryOpenEvent ownChestInFly = new InventoryOpenEvent(p1, mockContainerInventory(ownRegionChestLoc, InventoryType.CHEST));
        plugin.onInventoryOpen(ownChestInFly);
        assertTrue(!ownChestInFly.isCancelled(), "Opening chest in own WG region in /fly MUST BE ALLOWED");

        InventoryOpenEvent foreignChestInFly = new InventoryOpenEvent(p1, mockContainerInventory(foreignChestLoc, InventoryType.CHEST));
        plugin.onInventoryOpen(foreignChestInFly);
        assertTrue(foreignChestInFly.isCancelled(), "Opening chest outside own WG region in /fly MUST BE BLOCKED");

        EntityDamageByEntityEvent hitMobInFly = new EntityDamageByEntityEvent(p1, zombie);
        plugin.onDamageByEntity(hitMobInFly);
        assertTrue(!hitMobInFly.isCancelled(), "Hitting mobs in /fly MUST BE ALLOWED");

        EntityDamageByEntityEvent hitPlayerInFly = new EntityDamageByEntityEvent(p1, p2);
        plugin.onDamageByEntity(hitPlayerInFly);
        assertTrue(hitPlayerInFly.isCancelled(), "Hitting players in /fly MUST BE BLOCKED");

        // Turn /fly completely off -> 5.0s post-fly PvP cooldown!
        s1.flying.set(false);
        s1.allowFlight.set(false);
        plugin.evaluateState(p1, System.currentTimeMillis());
        assertTrue(s1.canPickup.get(), "canPickupItems restored immediately when /fly disabled");

        EntityDamageByEntityEvent hitPlayerInFlyCd = new EntityDamageByEntityEvent(p1, p2);
        plugin.onDamageByEntity(hitPlayerInFlyCd);
        assertTrue(hitPlayerInFlyCd.isCancelled(), "PvP during 5.0s post-fly cooldown MUST BE BLOCKED");

        PlayerToggleFlightEvent panicFly = new PlayerToggleFlightEvent(p1, true);
        plugin.onToggleFlight(panicFly);
        assertTrue(panicFly.isCancelled(), "Panic re-enabling flight during 5s post-fly cooldown MUST BE BLOCKED");

        // 8. Test Talisman region enforcement: blocks /fly & /god commands and auto-strips active /fly & /god!
        plugin.evaluateState(p1, System.currentTimeMillis() + 6000L);
        s1.god.set(true);
        s1.allowFlight.set(true);
        s1.flying.set(true);
        inTalisman.set(true);
        plugin.enforceTalismanAt(p1, p1.getLocation(), System.currentTimeMillis());
        assertTrue(!s1.god.get(), "Active /god must be force-disabled in Talisman region");
        assertTrue(!s1.flying.get() && !s1.allowFlight.get(), "Active /fly must be force-disabled in Talisman region");

        PlayerCommandPreprocessEvent flyInTalisman = new PlayerCommandPreprocessEvent(p1, "/fly");
        plugin.onCommandPreprocess(flyInTalisman);
        assertTrue(flyInTalisman.isCancelled(), "/fly command inside Talisman region MUST BE CANCELLED");

        PlayerCommandPreprocessEvent godInTalisman = new PlayerCommandPreprocessEvent(p1, "/god");
        plugin.onCommandPreprocess(godInTalisman);
        assertTrue(godInTalisman.isCancelled(), "/god command inside Talisman region MUST BE CANCELLED");

        System.out.println("[OK] ElytrixGodPickup v2.1.0 (/god + /fly + WG own-region chests + mob combat + 5s PvP cooldown + Talisman) passed.");
    }

    private static void testDuelsTeleportRaceFix(Path duelsJar) throws Exception {
        Unsafe unsafe = getUnsafe();
        DuelsPlugin fakeDuels = (DuelsPlugin) unsafe.allocateInstance(DuelsPlugin.class);
        World arenaWorld = mockWorld("duels_world", null);
        PlayerMockState st = new PlayerMockState(UUID.randomUUID(), "Duelist", arenaWorld);
        st.inVehicle.set(true);
        st.gliding.set(true);
        st.sleeping.set(true);
        Player duelist = mockPlayer(st, null);

        // Verify performSyncTeleport clears vehicle/gliding/sleeping, teleports player, and cleans up Duels-Teleport metadata
        Location target = new Location(arenaWorld, 250.5, 70.0, -120.5);
        boolean ok = ElytrixDuelTeleportFix.performSyncTeleport(fakeDuels, null, duelist, target);
        assertTrue(ok, "performSyncTeleport must succeed");
        assertTrue(!st.inVehicle.get(), "Vehicle must be exited before duel teleport");
        assertTrue(!st.gliding.get(), "Gliding must be stopped before duel teleport");
        assertTrue(!st.sleeping.get(), "Sleeping must be stopped before duel teleport");
        assertTrue(st.location.distanceSquared(target) < 0.01, "Duelist location must match arena spawn");
        assertTrue(!duelist.hasMetadata("Duels-Teleport"), "Duels-Teleport metadata must be cleaned up in finally");

        // Verify shouldBlockTeleportInMatch returns false whenever Duels-Teleport metadata is present
        ArenaManagerImpl dummyAm = (ArenaManagerImpl) unsafe.allocateInstance(ArenaManagerImpl.class);
        st.metadata.put("Duels-Teleport", Boolean.TRUE);
        assertTrue(!ElytrixDuelTeleportFix.shouldBlockTeleportInMatch(dummyAm, duelist),
                "DuelListener must NEVER cancel a teleport carrying Duels-Teleport metadata");

        // Verify DuelListener bytecode calls shouldBlockTeleportInMatch
        try (java.util.zip.ZipFile zf = new java.util.zip.ZipFile(duelsJar.toFile())) {
            byte[] b = zf.getInputStream(zf.getEntry("me/realized/duels/duel/DuelManager$DuelListener.class")).readAllBytes();
            final boolean[] hooked = {false};
            new ClassReader(b).accept(new ClassVisitor(Opcodes.ASM9) {
                @Override
                public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                    return new MethodVisitor(Opcodes.ASM9) {
                        @Override
                        public void visitMethodInsn(int op, String owner, String mName, String mDesc, boolean itf) {
                            if ("me/realized/duels/util/ElytrixDuelTeleportFix".equals(owner)
                                    && "shouldBlockTeleportInMatch".equals(mName)) {
                                hooked[0] = true;
                            }
                        }
                    };
                }
            }, 0);
            assertTrue(hooked[0], "DuelListener.on(PlayerTeleportEvent) must call ElytrixDuelTeleportFix.shouldBlockTeleportInMatch");
        }
        System.out.println("[OK] Duels teleport race fix, vehicle/glide cleanup, and metadata guard passed.");
    }

    private static void testElytrixItemsAirDropTrapGuard(Path eitemsJar) throws Exception {
        try (java.util.zip.ZipFile zf = new java.util.zip.ZipFile(eitemsJar.toFile())) {
            byte[] b = zf.getInputStream(zf.getEntry("topka/simbay/rwitems/items/ItemEffects$TrapItem.class")).readAllBytes();
            final boolean[] hooked = {false};
            new ClassReader(b).accept(new ClassVisitor(Opcodes.ASM9) {
                @Override
                public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                    if ("execute".equals(name)) {
                        return new MethodVisitor(Opcodes.ASM9) {
                            @Override
                            public void visitMethodInsn(int op, String owner, String mName, String mDesc, boolean itf) {
                                if ("topka/simbay/rwitems/utils/ElytrixAirTrapGuard".equals(owner)
                                        && "validateTrapUse".equals(mName)) {
                                    hooked[0] = true;
                                }
                            }
                        };
                    }
                    return null;
                }
            }, 0);
            assertTrue(hooked[0], "ItemEffects$TrapItem.execute must call ElytrixAirTrapGuard.validateTrapUse");
            String pluginYml = new String(zf.getInputStream(zf.getEntry("plugin.yml")).readAllBytes());
            assertTrue(pluginYml.contains("ElytrixAir"), "ElytrixItems plugin.yml must softdepend on ElytrixAir");
        }
        System.out.println("[OK] ElytrixItems AirDrop trap guard bytecode hook & plugin.yml verified.");
    }

    private static void testNMascotFlyAndGodStrip(Path nmascotJar) throws Exception {
        World w = mockWorld("world", null);
        PlayerMockState st = new PlayerMockState(UUID.randomUUID(), "MascotRunner", w);
        st.flying.set(true);
        st.allowFlight.set(true);
        Player p = mockPlayer(st, null);

        ElytrixMascotGuard.stripFlyAndGod(p);
        assertTrue(!st.flying.get() && !st.allowFlight.get(), "ElytrixMascotGuard must strip /fly in SURVIVAL");

        // Creative mode flight must NOT be stripped by raw flag check
        st.gameMode = GameMode.CREATIVE;
        st.flying.set(true);
        st.allowFlight.set(true);
        ElytrixMascotGuard.stripFlyAndGod(p);
        assertTrue(st.flying.get(), "Creative flight preserved");

        try (java.util.zip.ZipFile zf = new java.util.zip.ZipFile(nmascotJar.toFile())) {
            byte[] b = zf.getInputStream(zf.getEntry("ru/Travka/listener/PlayerMoveListener.class")).readAllBytes();
            final boolean[] hooked = {false};
            final boolean[] hasDeadCmi = {false};
            new ClassReader(b).accept(new ClassVisitor(Opcodes.ASM9) {
                @Override
                public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                    return new MethodVisitor(Opcodes.ASM9) {
                        @Override
                        public void visitMethodInsn(int op, String owner, String mName, String mDesc, boolean itf) {
                            if ("ru/Travka/util/ElytrixMascotGuard".equals(owner) && "onPlayerMove".equals(mName)) {
                                hooked[0] = true;
                            }
                            if (owner.contains("CMI")) {
                                hasDeadCmi[0] = true;
                            }
                        }
                    };
                }
            }, 0);
            assertTrue(hooked[0], "NMascot PlayerMoveListener.onMove must delegate to ElytrixMascotGuard.onPlayerMove");
            assertTrue(!hasDeadCmi[0], "Dead CMI references must be removed from PlayerMoveListener.onMove");
        }
        System.out.println("[OK] NMascot Talisman /fly & /god guard verified.");
    }

    private static ItemMeta mockTrackableMeta(Map<Enchantment, Integer> enchants, AtomicBoolean unbreakable) {
        return (ItemMeta) Proxy.newProxyInstance(
                BugfixVerificationSuite.class.getClassLoader(),
                new Class<?>[]{ItemMeta.class},
                (p, m, a) -> {
                    switch (m.getName()) {
                        case "hasEnchants":
                            return !enchants.isEmpty();
                        case "addEnchant":
                            enchants.put((Enchantment) a[0], (Integer) a[1]);
                            return true;
                        case "setUnbreakable":
                            unbreakable.set((Boolean) a[0]);
                            return null;
                        case "hasDisplayName":
                            return true;
                        default:
                            if (m.getReturnType() == boolean.class) return false;
                            return null;
                    }
                }
        );
    }

    private static void testItemKeepEnchantsCloneAndOverflow(Path itemkeepJar) throws Exception {
        // 1. Verify цыганский_щит runtime enchantment guarantee
        Map<Enchantment, Integer> shieldEnchants = new HashMap<>();
        AtomicBoolean shieldUnbreakable = new AtomicBoolean(false);
        ItemStack gypsyShield = new ItemStack(Material.SHIELD);
        gypsyShield.setItemMeta(mockTrackableMeta(shieldEnchants, shieldUnbreakable));
        ElytrixItemKeepFix.ensureExpectedEnchantments("цыганский_щит", gypsyShield);
        assertTrue(shieldEnchants.getOrDefault(Enchantment.THORNS, 0) == 10, "Gypsy shield must have Thorns 10");
        assertTrue(shieldEnchants.getOrDefault(Enchantment.VANISHING_CURSE, 0) == 1, "Gypsy shield must have Curse of Vanishing 1");
        assertTrue(shieldUnbreakable.get(), "Gypsy shield must be Unbreakable");

        // 2. Verify quest shulker (джамшут_2) inner tool runtime enchantment guarantee
        Map<Enchantment, Integer> pickEnchants = new HashMap<>();
        ItemStack innerPick = new ItemStack(Material.NETHERITE_PICKAXE);
        innerPick.setItemMeta(mockTrackableMeta(pickEnchants, new AtomicBoolean(false)));

        ItemStack[] shulkerSlots = new ItemStack[27];
        shulkerSlots[11] = innerPick;
        Inventory shulkerInv = (Inventory) Proxy.newProxyInstance(
                BugfixVerificationSuite.class.getClassLoader(),
                new Class<?>[]{Inventory.class},
                (p, m, a) -> {
                    switch (m.getName()) {
                        case "getSize":
                            return shulkerSlots.length;
                        case "getItem":
                            return shulkerSlots[(Integer) a[0]];
                        case "setItem":
                            shulkerSlots[(Integer) a[0]] = (ItemStack) a[1];
                            return null;
                        default:
                            return null;
                    }
                }
        );
        ShulkerBox shulkerState = (ShulkerBox) Proxy.newProxyInstance(
                BugfixVerificationSuite.class.getClassLoader(),
                new Class<?>[]{ShulkerBox.class},
                (p, m, a) -> "getInventory".equals(m.getName()) ? shulkerInv : null
        );
        BlockStateMeta shulkerMeta = (BlockStateMeta) Proxy.newProxyInstance(
                BugfixVerificationSuite.class.getClassLoader(),
                new Class<?>[]{BlockStateMeta.class},
                (p, m, a) -> "getBlockState".equals(m.getName()) ? shulkerState : null
        );
        ItemStack questShulker = new ItemStack(Material.SHULKER_BOX);
        questShulker.setItemMeta(shulkerMeta);
        ElytrixItemKeepFix.ensureExpectedEnchantments("джамшут_2", questShulker);
        assertTrue(pickEnchants.getOrDefault(Enchantment.EFFICIENCY, 0) == 5, "Quest pickaxe must have Efficiency 5");
        assertTrue(pickEnchants.getOrDefault(Enchantment.FORTUNE, 0) == 3, "Quest pickaxe must have Fortune 3");
        assertTrue(pickEnchants.getOrDefault(Enchantment.UNBREAKING, 0) == 3, "Quest pickaxe must have Unbreaking 3");
        assertTrue(pickEnchants.getOrDefault(Enchantment.MENDING, 0) == 1, "Quest pickaxe must have Mending 1");

        // 3. Verify cloning & full-inventory overflow drop
        AtomicInteger dropped = new AtomicInteger(0);
        World w = mockWorld("world", dropped);
        PlayerMockState st = new PlayerMockState(UUID.randomUUID(), "Buyer", w);
        List<ItemStack> receivedStacks = new ArrayList<>();
        PlayerInventory fullInv = (PlayerInventory) Proxy.newProxyInstance(
                BugfixVerificationSuite.class.getClassLoader(),
                new Class<?>[]{PlayerInventory.class},
                (p, m, a) -> {
                    if ("addItem".equals(m.getName())) {
                        ItemStack[] arr = (ItemStack[]) a[0];
                        receivedStacks.add(arr[0]);
                        HashMap<Integer, ItemStack> left = new HashMap<>();
                        left.put(0, arr[0]);
                        return left;
                    }
                    return null;
                }
        );
        Player buyer = mockPlayer(st, fullInv);
        ItemStack cachedOriginal = new ItemStack(Material.SHIELD);
        cachedOriginal.setItemMeta(mockTrackableMeta(new HashMap<>(), new AtomicBoolean(false)));
        FileConfiguration cfg = new FileConfiguration() {
            @Override
            public List<?> getList(String path) {
                return "цыганский_щит.items".equals(path) ? Collections.singletonList(cachedOriginal) : Collections.emptyList();
            }
        };
        ElytrixItemKeepFix.giveItem(cfg, buyer, "цыганский_щит");
        assertTrue(receivedStacks.size() == 1 && receivedStacks.get(0) != cachedOriginal,
                "ItemKeep must clone cached ItemStack before giving to player");
        assertTrue(dropped.get() == 1, "Overflow item must be dropped naturally when inventory is full");

        System.out.println("[OK] ItemKeep enchantments (цыганский_щит & quest shulkers), clone safety, and overflow drop passed.");
    }

    private static void testNClansColorEnforcement() throws Exception {
        String[] illegalColoredNames = new String[]{
                "&cMyClan",
                "&#FF0000MyClan",
                "<#00FF00>MyClan",
                "#123456MyClan",
                "&x&f&f&0&0&0&0MyClan",
                "\u00a7cMyClan",
                "&lBoldClan",
                "&kMagicClan",
                "Clan&#F8BEFB"
        };
        for (String bad : illegalColoredNames) {
            assertTrue(ValidatorUtil.getValidClanName(bad) == null, "Must reject colored clan name: " + bad);
        }
        assertTrue("ElytrixSquad".equals(ValidatorUtil.getValidClanName("ElytrixSquad")), "Plain ASCII clan name allowed");
        assertTrue("Легион_1".equals(ValidatorUtil.getValidClanName("Легион_1")), "Plain Cyrillic clan name allowed");

        Clan legacyClan = new Clan(0, null, "Leader", new ArrayList<>(), 0, false, false, "&#FF0000&lLegacyClan");
        assertTrue("LegacyClan".equals(legacyClan.getName()),
                "Clan.<init> must strip legacy colors, got: " + legacyClan.getName());
        legacyClan.setName("&a&lAnother&#123456Name");
        assertTrue("AnotherName".equals(legacyClan.getName()),
                "Clan.setName must strip manual colors, got: " + legacyClan.getName());

        System.out.println("[OK] NClans manual color rejection & legacy clans.yml sanitization passed.");
    }

    private static void testHJobsDatabasePersistence() throws Exception {
        Unsafe unsafe = getUnsafe();
        HJobs fakePlugin = (HJobs) unsafe.allocateInstance(HJobs.class);
        JobManager jm = new JobManager(fakePlugin);
        DatabaseManager dm = new DatabaseManager(fakePlugin);

        Field jmField = HJobs.class.getDeclaredField("jobManager");
        jmField.setAccessible(true);
        jmField.set(fakePlugin, jm);

        Field dmField = HJobs.class.getDeclaredField("databaseManager");
        dmField.setAccessible(true);
        dmField.set(fakePlugin, dm);

        UUID playerUuid = UUID.randomUUID();
        Map<String, int[]> mockDbTable = new HashMap<>();
        mockDbTable.put("miner", new int[]{4200, 150});
        List<String> executedSql = new ArrayList<>();
        AtomicBoolean autoCommitState = new AtomicBoolean(true);

        Connection mockConn = (Connection) Proxy.newProxyInstance(
                BugfixVerificationSuite.class.getClassLoader(),
                new Class<?>[]{Connection.class},
                (proxy, method, args) -> {
                    switch (method.getName()) {
                        case "isClosed":
                            return false;
                        case "setAutoCommit":
                            autoCommitState.set((Boolean) args[0]);
                            return null;
                        case "commit":
                        case "rollback":
                        case "close":
                            return null;
                        case "createStatement":
                            return Proxy.newProxyInstance(
                                    BugfixVerificationSuite.class.getClassLoader(),
                                    new Class<?>[]{Statement.class},
                                    (sp, sm, sa) -> false
                            );
                        case "prepareStatement": {
                            String sql = (String) args[0];
                            executedSql.add(sql);
                            if (sql.startsWith("SELECT")) {
                                final int[] idx = {-1};
                                List<Map.Entry<String, int[]>> rows = new ArrayList<>(mockDbTable.entrySet());
                                ResultSet rs = (ResultSet) Proxy.newProxyInstance(
                                        BugfixVerificationSuite.class.getClassLoader(),
                                        new Class<?>[]{ResultSet.class},
                                        (rp, rm, ra) -> {
                                            switch (rm.getName()) {
                                                case "next":
                                                    idx[0]++;
                                                    return idx[0] < rows.size();
                                                case "getString":
                                                    return rows.get(idx[0]).getKey();
                                                case "getInt":
                                                    return "sold_total".equals(ra[0])
                                                            ? rows.get(idx[0]).getValue()[0]
                                                            : rows.get(idx[0]).getValue()[1];
                                                case "getLong":
                                                    return 1700000000000L;
                                                case "close":
                                                    return null;
                                                default:
                                                    return null;
                                            }
                                        }
                                );
                                return Proxy.newProxyInstance(
                                        BugfixVerificationSuite.class.getClassLoader(),
                                        new Class<?>[]{PreparedStatement.class},
                                        (pp, pm, pa) -> "executeQuery".equals(pm.getName()) ? rs : null
                                );
                            } else {
                                final String[] curJob = {null};
                                final int[] curTotal = {0};
                                final int[] curDaily = {0};
                                return Proxy.newProxyInstance(
                                        BugfixVerificationSuite.class.getClassLoader(),
                                        new Class<?>[]{PreparedStatement.class},
                                        (pp, pm, pa) -> {
                                            switch (pm.getName()) {
                                                case "setString":
                                                    if ((Integer) pa[0] == 2) curJob[0] = (String) pa[1];
                                                    return null;
                                                case "setInt":
                                                    if ((Integer) pa[0] == 3) curTotal[0] = (Integer) pa[1];
                                                    if ((Integer) pa[0] == 4) curDaily[0] = (Integer) pa[1];
                                                    return null;
                                                case "addBatch":
                                                    int prev = mockDbTable.containsKey(curJob[0]) ? mockDbTable.get(curJob[0])[0] : 0;
                                                    mockDbTable.put(curJob[0], new int[]{Math.max(prev, curTotal[0]), curDaily[0]});
                                                    return null;
                                                case "executeBatch":
                                                    return new int[]{1};
                                                default:
                                                    return null;
                                            }
                                        }
                                );
                            }
                        }
                        default:
                            return null;
                    }
                }
        );

        Field connField = DatabaseManager.class.getDeclaredField("connection");
        connField.setAccessible(true);
        connField.set(dm, mockConn);

        UUID unloadedUuid = UUID.randomUUID();
        dm.savePlayerStats(unloadedUuid);
        assertTrue(executedSql.isEmpty(), "Unloaded player must NEVER trigger SQL write");

        Map<String, JobStat> stats = jm.getPlayerStats(playerUuid);
        assertTrue(stats != null && stats.containsKey("miner"), "Lazy getPlayerStats must load miner stats from DB");
        assertTrue(stats.get("miner").soldItemsTotal == 4200, "Must preserve 4200 soldItemsTotal across restart");

        stats.get("miner").soldItemsTotal += 64;
        stats.get("miner").dailySold += 64;
        dm.savePlayerStats(playerUuid);
        assertTrue(mockDbTable.get("miner")[0] == 4264, "Saved sold_total must be 4264");
        assertTrue(autoCommitState.get(), "Connection autoCommit must be restored to true in finally");
        assertTrue(executedSql.stream().anyMatch(s -> s.contains("MAX(job_stats.sold_total, excluded.sold_total)")),
                "Must use monotonic MAX(sold_total) UPSERT");

        System.out.println("[OK] hJobs restart persistence, lazy load, and monotonic SQLite UPSERT passed.");
    }

    private static void testGreatCombatBytecodeInvariants(Path gcJar) throws Exception {
        try (java.util.zip.ZipFile zf = new java.util.zip.ZipFile(gcJar.toFile())) {
            byte[] itemUtilsBytes = zf.getInputStream(zf.getEntry("dev/enco/greatcombat/utils/ItemUtils.class")).readAllBytes();
            final boolean[] hasDisableCall = {false};
            final boolean[] hasDecodeFallback = {false};
            new ClassReader(itemUtilsBytes).accept(new ClassVisitor(Opcodes.ASM9) {
                @Override
                public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                    if ("decodeWithFallback".equals(name)) {
                        hasDecodeFallback[0] = true;
                    }
                    return new MethodVisitor(Opcodes.ASM9) {
                        @Override
                        public void visitMethodInsn(int op, String owner, String mName, String mDesc, boolean itf) {
                            if ("disablePlugin".equals(mName)) {
                                hasDisableCall[0] = true;
                            }
                        }
                    };
                }
            }, 0);
            assertTrue(!hasDisableCall[0], "ItemUtils.decode must never call disablePlugin(GreatCombat)");
            assertTrue(hasDecodeFallback[0], "ItemUtils.decodeWithFallback must exist");

            byte[] plBytes = zf.getInputStream(zf.getEntry("dev/enco/greatcombat/listeners/PlayerListener.class")).readAllBytes();
            final boolean[] hasBypassCheck = {false};
            new ClassReader(plBytes).accept(new ClassVisitor(Opcodes.ASM9) {
                @Override
                public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                    if ("handleCooldown".equals(name)) {
                        return new MethodVisitor(Opcodes.ASM9) {
                            @Override
                            public void visitMethodInsn(int op, String owner, String mName, String mDesc, boolean itf) {
                                if ("hasPermission".equals(mName)) {
                                    hasBypassCheck[0] = true;
                                }
                            }
                        };
                    }
                    return null;
                }
            }, 0);
            assertTrue(!hasBypassCheck[0], "PlayerListener.handleCooldown must not bypass cooldowns for OP/*");
        }
        System.out.println("[OK] GreatCombat non-disabling ItemUtils + OP-proof cooldown invariants passed.");
    }
}
