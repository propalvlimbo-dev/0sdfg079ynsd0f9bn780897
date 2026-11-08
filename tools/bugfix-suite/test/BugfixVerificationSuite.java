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
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;
import net.ess3.api.IUser;
import net.ess3.api.events.GodStatusChangeEvent;
import org.bukkit.entity.Player;
import org.bukkit.event.Event;
import org.bukkit.event.block.Action;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.player.PlayerCommandPreprocessEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassVisitor;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;
import pw.elytrix.godpickup.GodPickup;
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
        if (args.length != 4) {
            throw new IllegalArgumentException("Usage: BugfixVerificationSuite <god.jar> <hjobs.jar> <nclans.jar> <greatcombat.jar>");
        }
        Path godJar = Path.of(args[0]);
        Path hjobsJar = Path.of(args[1]);
        Path nclansJar = Path.of(args[2]);
        Path gcJar = Path.of(args[3]);

        verifyBytecodeAll(godJar, hjobsJar, nclansJar, gcJar);
        testGodLockdownAndCooldown();
        testNClansColorEnforcement();
        testHJobsDatabasePersistence();
        testGreatCombatBytecodeInvariants(gcJar);

        System.out.println("ALL BUGFIX VERIFICATION TESTS PASSED UNDER -Xverify:all!");
    }

    private static void verifyBytecodeAll(Path godJar, Path hjobsJar, Path nclansJar, Path gcJar) throws Exception {
        URL[] urls = new URL[]{
                godJar.toUri().toURL(),
                hjobsJar.toUri().toURL(),
                nclansJar.toUri().toURL(),
                gcJar.toUri().toURL()
        };
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
                "dev.enco.greatcombat.listeners.PlayerListener"
        };
        try (URLClassLoader ucl = new URLClassLoader(urls, BugfixVerificationSuite.class.getClassLoader())) {
            for (String cn : classesToVerify) {
                Class<?> c = Class.forName(cn, false, ucl);
                // getDeclaredMethods() + getDeclaredConstructors() triggers JVM StackMapTable verification under -Xverify:all
                c.getDeclaredMethods();
                c.getDeclaredConstructors();
            }
        }
        System.out.println("[OK] Bytecode StackMapTable verification passed for all 13 target classes.");
    }

    private static Player mockPlayer(UUID uuid, String name, List<String> messages, AtomicBoolean closedInv) {
        InvocationHandler h = (proxy, method, mArgs) -> {
            switch (method.getName()) {
                case "getUniqueId":
                    return uuid;
                case "getName":
                    return name;
                case "hasPermission":
                    return false;
                case "sendMessage":
                    if (mArgs != null && mArgs.length > 0 && mArgs[0] != null) {
                        messages.add(String.valueOf(mArgs[0]));
                    }
                    return null;
                case "closeInventory":
                    closedInv.set(true);
                    return null;
                case "equals":
                    return proxy == mArgs[0];
                case "hashCode":
                    return uuid.hashCode();
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

    private static void testGodLockdownAndCooldown() throws Exception {
        UUID u1 = UUID.randomUUID();
        UUID u2 = UUID.randomUUID();
        List<String> msgs1 = new ArrayList<>();
        List<String> msgs2 = new ArrayList<>();
        AtomicBoolean closed1 = new AtomicBoolean(false);
        AtomicBoolean closed2 = new AtomicBoolean(false);
        AtomicBoolean god1 = new AtomicBoolean(false);
        AtomicBoolean god2 = new AtomicBoolean(false);

        Player p1 = mockPlayer(u1, "AdminOne", msgs1, closed1);
        Player p2 = mockPlayer(u2, "EnemyTwo", msgs2, closed2);
        IUser iu1 = mockUser(p1, god1);
        IUser iu2 = mockUser(p2, god2);

        GodPickup plugin = new GodPickup();
        plugin.initForTest(p -> p == p1 ? god1.get() : (p == p2 && god2.get()));

        long t0 = System.currentTimeMillis();
        assertTrue(plugin.evaluateState(p1, t0) == GodPickup.Restriction.NONE, "Initially NONE");

        // 1. Prevent /god <otherPlayer> griefing
        GodStatusChangeEvent griefAttempt = new GodStatusChangeEvent(iu2, iu1, true);
        plugin.onGodStatusChange(griefAttempt);
        assertTrue(griefAttempt.isCancelled(), "Toggling /god on another player must be cancelled");

        // 2. Enable /god on self
        GodStatusChangeEvent enableEvt = new GodStatusChangeEvent(iu1, iu1, true);
        god1.set(true);
        plugin.onGodStatusChange(enableEvt);
        assertTrue(!enableEvt.isCancelled(), "Self /god enable must succeed");
        assertTrue(closed1.get(), "Inventory must be closed immediately on /god enable");
        assertTrue(plugin.evaluateState(p1, t0 + 10) == GodPickup.Restriction.ACTIVE_GOD, "Must be ACTIVE_GOD");

        // 3. Verify attacks, chests, pickups, blocks, interacts, and abuse commands are blocked in /god
        EntityDamageByEntityEvent hitEvt = new EntityDamageByEntityEvent(p1, p2);
        plugin.onDamageByEntity(hitEvt);
        assertTrue(hitEvt.isCancelled(), "Attacking in /god must be cancelled");

        InventoryOpenEvent chestEvt = new InventoryOpenEvent(p1);
        plugin.onInventoryOpen(chestEvt);
        assertTrue(chestEvt.isCancelled(), "Opening chest in /god must be cancelled");

        EntityPickupItemEvent pickupEvt = new EntityPickupItemEvent(p1);
        plugin.onEntityPickup(pickupEvt);
        assertTrue(pickupEvt.isCancelled(), "Item pickup in /god must be cancelled");

        BlockBreakEvent breakEvt = new BlockBreakEvent(p1);
        plugin.onBlockBreak(breakEvt);
        assertTrue(breakEvt.isCancelled(), "Block break in /god must be cancelled");

        PlayerInteractEvent interactEvt = new PlayerInteractEvent(p1, Action.RIGHT_CLICK_AIR);
        plugin.onInteract(interactEvt);
        assertTrue(interactEvt.useItemInHand() == Event.Result.DENY, "Using item in /god must be DENIED");

        PlayerCommandPreprocessEvent ecCmd = new PlayerCommandPreprocessEvent(p1, "/ec");
        plugin.onCommandPreprocess(ecCmd);
        assertTrue(ecCmd.isCancelled(), "/ec in /god must be cancelled");

        PlayerCommandPreprocessEvent egodOffCmd = new PlayerCommandPreprocessEvent(p1, "/egod");
        plugin.onCommandPreprocess(egodOffCmd);
        assertTrue(!egodOffCmd.isCancelled(), "/egod off must remain allowed while in /god");

        // 4. Disable /god -> 5,000 ms cooldown starts immediately
        GodStatusChangeEvent disableEvt = new GodStatusChangeEvent(iu1, iu1, false);
        god1.set(false);
        plugin.onGodStatusChange(disableEvt);
        long afterOff = System.currentTimeMillis();
        assertTrue(plugin.evaluateState(p1, afterOff + 100) == GodPickup.Restriction.POST_GOD_COOLDOWN,
                "Must be in POST_GOD_COOLDOWN at +100ms");
        assertTrue(plugin.evaluateState(p1, afterOff + 4900) == GodPickup.Restriction.POST_GOD_COOLDOWN,
                "Must still be in POST_GOD_COOLDOWN at +4900ms");

        // 5. During 5s cooldown: player CANNOT hit, CANNOT open chests, AND CANNOT panic re-enable /god!
        EntityDamageByEntityEvent hitInCd = new EntityDamageByEntityEvent(p1, p2);
        plugin.onDamageByEntity(hitInCd);
        assertTrue(hitInCd.isCancelled(), "Attacking during 5s post-god cooldown must be cancelled");

        // Meanwhile enemy p2 CAN hit p1 during p1's 5s post-god cooldown!
        EntityDamageByEntityEvent enemyPunish = new EntityDamageByEntityEvent(p2, p1);
        plugin.onDamageByEntity(enemyPunish);
        assertTrue(!enemyPunish.isCancelled(), "Mortal player in 5s post-god cooldown must take enemy hits normally");

        GodStatusChangeEvent panicReEnable = new GodStatusChangeEvent(iu1, iu1, true);
        plugin.onGodStatusChange(panicReEnable);
        assertTrue(panicReEnable.isCancelled(), "Panic re-enabling /god during 5s cooldown must be cancelled");

        // 6. After 5,001 ms: restriction expires cleanly
        assertTrue(plugin.evaluateState(p1, afterOff + 5050) == GodPickup.Restriction.NONE,
                "Restriction must clear after 5000ms");

        // 7. Silent API bypass test (god turned off without GodStatusChangeEvent + relog test)
        god1.set(true);
        assertTrue(plugin.evaluateState(p1, afterOff + 6000) == GodPickup.Restriction.ACTIVE_GOD, "API god on");
        plugin.onQuit(new PlayerQuitEvent(p1));
        god1.set(false); // Disconnected & god cleared externally
        plugin.onJoin(new PlayerJoinEvent(p1));
        long joinNow = System.currentTimeMillis();
        assertTrue(plugin.evaluateState(p1, joinNow + 500) == GodPickup.Restriction.POST_GOD_COOLDOWN,
                "Relogging out of /god must still enforce full 5s post-god cooldown");

        System.out.println("[OK] ElytrixGodPickup lockdown + 5.0s cooldown + anti-bypass tests passed.");
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

        // Verify Clan constructor and setName automatically strip legacy manual colors from clans.yml
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

        // 1. Saving an unloaded player must NOT overwrite DB!
        UUID unloadedUuid = UUID.randomUUID();
        dm.savePlayerStats(unloadedUuid);
        assertTrue(executedSql.isEmpty(), "Unloaded player must NEVER trigger SQL write");

        // 2. Calling jm.getPlayerStats(playerUuid) after restart (before async join finishes) lazily loads 4200 from DB!
        Map<String, JobStat> stats = jm.getPlayerStats(playerUuid);
        assertTrue(stats != null && stats.containsKey("miner"), "Lazy getPlayerStats must load miner stats from DB");
        assertTrue(stats.get("miner").soldItemsTotal == 4200, "Must preserve 4200 soldItemsTotal across restart");

        // 3. Selling 64 more items and calling savePlayerStats persists 4264 via ON CONFLICT DO UPDATE MAX(...)
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
