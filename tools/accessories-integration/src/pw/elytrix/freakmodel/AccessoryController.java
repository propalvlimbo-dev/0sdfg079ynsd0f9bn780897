package pw.elytrix.freakmodel;

import com.ticxo.modelengine.api.ModelEngineAPI;
import com.ticxo.modelengine.api.animation.BlueprintAnimation;
import com.ticxo.modelengine.api.animation.ModelState;
import com.ticxo.modelengine.api.animation.handler.AnimationHandler;
import com.ticxo.modelengine.api.animation.property.IAnimationProperty;
import com.ticxo.modelengine.api.entity.BaseEntity;
import com.ticxo.modelengine.api.entity.CullType;
import com.ticxo.modelengine.api.entity.Dummy;
import com.ticxo.modelengine.api.entity.data.BukkitEntityData;
import com.ticxo.modelengine.api.entity.data.IEntityData;
import com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint;
import com.ticxo.modelengine.api.lod.AnimationLODHandler;
import com.ticxo.modelengine.api.model.ActiveModel;
import com.ticxo.modelengine.api.model.ModeledEntity;
import com.ticxo.modelengine.api.model.PivotOverride;
import com.ticxo.modelengine.api.model.PivotOverrideRegistry;
import com.ticxo.modelengine.api.model.render.DisplayRenderer;
import com.ticxo.modelengine.api.model.render.ModelRenderer;
import com.ticxo.modelengine.api.nms.entity.wrapper.BodyRotationController;
import com.ticxo.modelengine.api.nms.entity.wrapper.TrackedEntity;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.World;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.PluginCommand;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.player.PlayerAnimationEvent;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerMoveEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerRespawnEvent;
import org.bukkit.event.player.PlayerTeleportEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;

/**
 * Server-side accessories menu & unified controller (v3.11.0):
 * Angel Wings, Divine Halo, Kaneki Ken's Rinkaku Kagune (elytrix_kaneki_tentacles),
 * and the Full-Body Crawling Tokyo Ghoul Scolopendra (elytrix_centipede).
 *
 * <p>Key guarantees:
 * <ul>
 *   <li>Both {@code elytrix_centipede} and {@code elytrix_kaneki_tentacles} run on
 *       isolated {@link Dummy} base entities so neither collides with
 *       {@code WornAngelRig}'s {@code PlayerAuraAttachment(player)} nor triggers
 *       angel feather particles.</li>
 *   <li>Teleport, cross-world, respawn, and &gt;24-block NMS jumps cleanly destroy
 *       stale virtual {@link DisplayRenderer} entities and respawn fresh ones at the
 *       destination after 2 ticks, eliminating 4-chunk view-distance despawns.</li>
 *   <li>Every tick verifies {@link PivotOverrideRegistry#getOrCreate} and passenger
 *       containment (with a 40-tick warmup + 20-tick periodic {@code markDirty()}),
 *       recovering seamlessly even if {@code WornAngelRig.destroyAll()} removes the
 *       player's {@link PivotOverride}.</li>
 * </ul>
 */
public final class AccessoryController implements CommandExecutor, Listener {
    static final NamespacedKey BACK = new NamespacedKey("elytrixaccessories", "back");
    static final NamespacedKey HALO = new NamespacedKey("elytrixaccessories", "halo");
    static final NamespacedKey HEAD = new NamespacedKey("elytrixaccessories", "head");
    static final NamespacedKey PET = new NamespacedKey("elytrixaccessories", "pet");
    static final String PET_CHOICE = "centipede";
    static final String CENTIPEDE_BLUEPRINT = "elytrix_centipede";
    static final String KANEKI_BLUEPRINT = "elytrix_kaneki_tentacles";
    static final String IDLE_ANIM = "idle";
    static final String MEDIA_GROUP = "media";
    static final String USE_PERMISSION = "elytrixaccessories.use";
    static final int VIEW_RANGE = 96;
    static final long RE_PAIR_TICKS = 40L;
    static final int WARMUP_SYNC_TICKS = 40;
    static final double TELEPORT_JUMP_DIST_SQ = 24.0D * 24.0D;

    private static boolean mediaGranted;
    private static ElytrixFreakModelPlugin host;
    private static final java.util.Map<java.util.UUID, GhoulRig> PETS = new java.util.HashMap<>();
    private static final java.util.Map<java.util.UUID, GhoulRig> KAGUNES = new java.util.HashMap<>();
    private static final java.util.Map<java.util.UUID, PlayerBodyTracker> TRACKERS = new java.util.HashMap<>();
    private static final java.util.Map<java.util.UUID, Long> TELEPORT_RESPAWN_AT = new java.util.HashMap<>();
    private static final java.util.Set<String> REPORTED = new java.util.HashSet<>();
    static long petTicks;
    private static boolean modelsLogged;

    private AccessoryController() {}

    /** Isolated Dummy-backed ModelEngine rig (Scolopendra or Kaneki Rinkaku Kagune). */
    private static final class GhoulRig {
        final String blueprintId;
        final Dummy<Player> dummy;
        final ModeledEntity entity;
        final ActiveModel model;
        PivotOverride pivot;
        IAnimationProperty animProperty;
        boolean statesCleared;
        boolean attached;
        int attachedPivotId = -1;
        int warmupTicks = WARMUP_SYNC_TICKS;
        boolean ownerSees;
        long pairedAt;
        World lastWorld;
        double lastX;
        double lastY;
        double lastZ;
        boolean hasLastPos;
        boolean loggedReady;

        GhoulRig(String blueprintId, Dummy<Player> dummy, ModeledEntity entity,
                 ActiveModel model, PivotOverride pivot, Location spawnLoc) {
            this.blueprintId = blueprintId;
            this.dummy = dummy;
            this.entity = entity;
            this.model = model;
            this.pivot = pivot;
            recordLocation(spawnLoc);
        }

        void recordLocation(Location loc) {
            if (loc == null) return;
            this.lastWorld = loc.getWorld();
            this.lastX = loc.getX();
            this.lastY = loc.getY();
            this.lastZ = loc.getZ();
            this.hasLastPos = true;
        }
    }

    public static void install(ElytrixFreakModelPlugin plugin) {
        try {
            AccessoryController controller = new AccessoryController();
            host = plugin;
            PluginCommand command = plugin.getCommand("accessories");
            if (command == null) {
                plugin.getLogger().warning("[Аксессуары] команда accessories не найдена в plugin.yml — меню не подключено");
            } else {
                command.setExecutor(controller);
            }
            Bukkit.getPluginManager().registerEvents(controller, plugin);
            Bukkit.getScheduler().runTaskTimer(plugin, AccessoryController::tickAll, 20L, 5L);
            Bukkit.getScheduler().runTaskTimer(plugin, AccessoryController::animatePets, 2L, 1L);
            grantDonationAccess();
        } catch (Throwable failure) {
            plugin.getLogger().warning("[Аксессуары] меню не подключилось: " + failure);
        }
    }

    private static void grantDonationAccess() {
        if (mediaGranted) return;
        try {
            if (!Bukkit.getPluginManager().isPluginEnabled("LuckPerms")) return;
            if (!Bukkit.dispatchCommand(Bukkit.getConsoleSender(),
                "lp group " + MEDIA_GROUP + " permission set " + USE_PERMISSION + " true")) return;
            mediaGranted = true;
        } catch (Throwable ignored) {
        }
    }

    static boolean allowed(Player player) {
        return player != null
            && (player.hasPermission("elytrixaccessories.admin") || player.hasPermission(USE_PERMISSION));
    }

    static void reportOnce(String what, Throwable failure) {
        if (!REPORTED.add(what)) return;
        try {
            if (host != null) {
                host.getLogger().warning("[Аксессуары] " + what + " не работает: " + failure);
            }
        } catch (Throwable ignored) {
        }
    }

    private static String get(Player p, NamespacedKey k) {
        String v = p.getPersistentDataContainer().get(k, PersistentDataType.STRING);
        return v == null ? "" : v;
    }

    private static void set(Player p, NamespacedKey k, String v) {
        PersistentDataContainer data = p.getPersistentDataContainer();
        if (v.isEmpty()) data.remove(k); else data.set(k, PersistentDataType.STRING, v);
    }

    static String headChoice(Player player) {
        String choice = get(player, HEAD);
        if (choice.isEmpty()) choice = get(player, HALO);
        return choice.equals("halo") ? choice : "";
    }

    public static FreakModelSpec halo(ElytrixFreakModelPlugin plugin, Player player) {
        if (!allowed(player)) return null;
        return headChoice(player).equals("halo") ? plugin.findModel("angel_halo") : null;
    }

    /**
     * WornAngelRig resolver for the back slot: ONLY Angel Wings use WornAngelRig.
     * Kaneki Ken's Rinkaku Kagune runs on our own isolated Dummy GhoulRig so it never
     * emits celestial angel dust, never conflicts with Halo removal, and survives all teleports.
     */
    public static FreakModelSpec back(ElytrixFreakModelPlugin plugin, Player player) {
        if (!allowed(player)) return null;
        String selection = get(player, BACK);
        if (selection.equals("wings")) return plugin.findModel("angel_wings");
        return null;
    }

    public static boolean kanekiSelected(Player player) {
        return player != null
            && player.isOnline()
            && !player.isDead()
            && player.getGameMode() != GameMode.SPECTATOR
            && allowed(player)
            && get(player, BACK).equals("kaneki");
    }

    public static boolean centipedeSelected(Player player) {
        return player != null
            && player.isOnline()
            && !player.isDead()
            && player.getGameMode() != GameMode.SPECTATOR
            && allowed(player)
            && get(player, PET).equals(PET_CHOICE);
    }

    static boolean wearingKaneki(Player player) {
        GhoulRig rig = KAGUNES.get(player.getUniqueId());
        return rig != null && !rig.model.isDestroyed() && !rig.entity.isDestroyed();
    }

    static boolean wearingCentipede(Player player) {
        GhoulRig rig = PETS.get(player.getUniqueId());
        return rig != null && !rig.model.isDestroyed() && !rig.entity.isDestroyed();
    }

    static boolean centipedeAttached(Player player) {
        GhoulRig rig = PETS.get(player.getUniqueId());
        return rig != null && rig.attached;
    }

    static boolean kanekiAttached(Player player) {
        GhoulRig rig = KAGUNES.get(player.getUniqueId());
        return rig != null && rig.attached;
    }

    static boolean centipedeAnimating(Player player) {
        GhoulRig rig = PETS.get(player.getUniqueId());
        if (rig == null || rig.model.isDestroyed()) return false;
        AnimationHandler handler = rig.model.getAnimationHandler();
        return handler != null && handler.isPlayingAnimation(IDLE_ANIM);
    }

    static boolean kanekiAnimating(Player player) {
        GhoulRig rig = KAGUNES.get(player.getUniqueId());
        if (rig == null || rig.model.isDestroyed()) return false;
        AnimationHandler handler = rig.model.getAnimationHandler();
        return handler != null && handler.isPlayingAnimation(IDLE_ANIM);
    }

    private static PlayerBodyTracker trackerFor(Player player) {
        return TRACKERS.computeIfAbsent(player.getUniqueId(), uuid -> {
            PlayerBodyTracker t = new PlayerBodyTracker();
            t.resetToPlayer(player);
            return t;
        });
    }

    static boolean ensureOwnerSees(Player player, GhoulRig rig) {
        if (player == null || rig == null || rig.model == null || rig.model.isDestroyed()) return false;
        ModeledEntity entity = rig.entity;
        if (entity == null || entity.isDestroyed()) return false;
        try {
            if (rig.dummy != null) {
                rig.dummy.setDetectingPlayers(true);
                rig.dummy.setRenderRadius(VIEW_RANGE);
                rig.dummy.setForceViewing(player, true);
            }
            AnimationLODHandler lod = entity.getAnimationLodHandler();
            if (lod != null) lod.setEnabled(Boolean.FALSE);
            BaseEntity base = entity.getBase();
            if (base == null) return false;
            IEntityData data = base.getData();
            if (data != null) {
                data.setVerticalCull(false);
                data.setBackCull(false);
                data.setBlockedCull(false);
                data.setCullInterval(1);
                data.setVerticalCullType(CullType.NO_CULL);
                data.setBackCullType(CullType.NO_CULL);
                data.setBlockedCullType(CullType.NO_CULL);
                if (data instanceof BukkitEntityData) {
                    TrackedEntity tracked = ((BukkitEntityData) data).getTracked();
                    if (tracked != null) {
                        tracked.addForcedPairing(player.getUniqueId());
                        if (tracked.getBaseRange() < VIEW_RANGE) tracked.setBaseRange(VIEW_RANGE);
                    }
                }
            }
            return true;
        } catch (Throwable failure) {
            reportOnce("видимость", failure);
            return false;
        }
    }

    static int resolvePivotEntityId(ActiveModel model) {
        if (model == null || model.isDestroyed()) return -1;
        ModelRenderer renderer;
        try {
            renderer = model.getModelRenderer();
        } catch (Throwable failure) {
            reportOnce("рендерер аксессуара", failure);
            return -1;
        }
        if (!(renderer instanceof DisplayRenderer)) return -1;
        DisplayRenderer display = (DisplayRenderer) renderer;
        if (!display.isInitialized()) return -1;
        DisplayRenderer.Pivot pivotEntity = display.getPivot();
        return pivotEntity == null ? -1 : pivotEntity.getId();
    }

    /**
     * Ensures the model's DisplayRenderer pivot is bound to the player's CURRENT
     * PivotOverride (recovering if WornAngelRig.destroyAll() removed an older one)
     * and keeps passengers synced across warmup & periodic intervals.
     */
    static boolean ensurePivotMounted(Player player, GhoulRig rig) {
        if (player == null || rig == null || rig.model == null || rig.model.isDestroyed()) return false;
        PivotOverrideRegistry registry = ModelEngineAPI.getPivotOverrideRegistry();
        PivotOverride latest = registry == null ? null : registry.getOrCreate(player);
        if (latest != null && latest != rig.pivot) {
            detachPivotFromPlayer(rig);
            rig.pivot = latest;
            rig.model.setPivotOverride(latest);
            rig.attached = false;
            rig.warmupTicks = WARMUP_SYNC_TICKS;
        }
        if (rig.pivot == null) return false;
        int id = resolvePivotEntityId(rig.model);
        if (id < 0) return false;
        boolean idChanged = (rig.attachedPivotId != id);
        if (idChanged && rig.attachedPivotId >= 0) {
            try {
                rig.pivot.removePassenger(rig.attachedPivotId);
            } catch (Throwable ignored) {
            }
        }
        rig.attachedPivotId = id;
        boolean alreadyContained = rig.pivot.getPassengers() != null && rig.pivot.getPassengers().contains(id);
        if (!alreadyContained) {
            rig.pivot.addPassenger(id);
        }
        boolean shouldMarkDirty = !rig.attached || !alreadyContained || idChanged
            || rig.warmupTicks > 0 || (petTicks % 20L == 0L);
        if (shouldMarkDirty && rig.pivot.getPassengers() != null) {
            rig.pivot.getPassengers().markDirty();
        }
        if (rig.warmupTicks > 0) rig.warmupTicks--;
        rig.attached = true;
        return true;
    }

    private static void detachPivotFromPlayer(GhoulRig rig) {
        if (rig == null || rig.pivot == null) return;
        try {
            int id = rig.attachedPivotId >= 0 ? rig.attachedPivotId : resolvePivotEntityId(rig.model);
            if (id >= 0) {
                rig.pivot.removePassenger(id);
                if (rig.pivot.getPassengers() != null) rig.pivot.getPassengers().markDirty();
            }
        } catch (Throwable ignored) {
        }
    }

    private static boolean hasTeleportJumped(Location now, GhoulRig rig) {
        if (now == null || rig == null || !rig.hasLastPos) return false;
        if (now.getWorld() != rig.lastWorld) return true;
        double dx = now.getX() - rig.lastX;
        double dy = now.getY() - rig.lastY;
        double dz = now.getZ() - rig.lastZ;
        return (dx * dx + dy * dy + dz * dz) > TELEPORT_JUMP_DIST_SQ;
    }

    private static void syncRigTransform(Player player, GhoulRig rig, float bodyYaw) {
        if (player == null || rig == null || rig.entity == null || rig.entity.isDestroyed()) return;
        float safeYaw = Float.isFinite(bodyYaw) ? bodyYaw : 0.0F;
        try {
            Location loc = player.getLocation();
            if (rig.dummy != null) {
                if (loc != null) {
                    rig.dummy.syncLocation(loc);
                    rig.recordLocation(loc);
                }
                rig.dummy.setYBodyRot(safeYaw);
                rig.dummy.setYHeadRot(safeYaw);
                rig.dummy.setXHeadRot(0.0F);
                BodyRotationController rot = rig.dummy.getBodyRotationController();
                if (rot != null) {
                    rot.setYBodyRot(safeYaw);
                    rot.setYHeadRot(safeYaw);
                    rot.setXHeadRot(0.0F);
                }
            }
            PlayerAuraAttachment.syncModeledEntityImmediately(rig.entity, safeYaw);
        } catch (Throwable failure) {
            reportOnce("поворот аксессуара", failure);
        }
    }

    private static void ensureLivingAnimation(GhoulRig rig, double horizSpeed) {
        if (rig == null || rig.model == null || rig.model.isDestroyed()) return;
        AnimationHandler handler;
        try {
            handler = rig.model.getAnimationHandler();
        } catch (Throwable failure) {
            reportOnce("анимация аксессуара", failure);
            return;
        }
        if (handler == null) return;
        if (!rig.statesCleared) {
            rig.statesCleared = true;
            for (ModelState state : ModelState.values()) {
                handler.setDefaultProperty(new AnimationHandler.DefaultProperty(state, "", 0.0D, 0.0D, 1.0D));
            }
        }
        double speedBoost = KANEKI_BLUEPRINT.equals(rig.blueprintId) ? 2.5D : 1.8D;
        double targetSpeed = 1.0D + Math.min(0.85D, Math.max(0.0D, horizSpeed) * speedBoost);
        if (!handler.isPlayingAnimation(IDLE_ANIM) || rig.animProperty == null) {
            IAnimationProperty prop = handler.playAnimation(IDLE_ANIM, 0.0D, 0.0D, targetSpeed, true);
            if (prop != null) {
                prop.setForceLoopMode(BlueprintAnimation.LoopMode.LOOP);
                prop.setSpeed(targetSpeed);
            }
            rig.animProperty = prop;
        } else {
            rig.animProperty.setSpeed(targetSpeed);
        }
    }

    private static void syncSingleSlot(Player player, boolean want, String blueprintId,
                                       java.util.Map<java.util.UUID, GhoulRig> store) {
        java.util.UUID uuid = player.getUniqueId();
        GhoulRig rig = store.get(uuid);
        if (!want) {
            if (rig != null) removeRig(uuid, rig, store);
            return;
        }
        Long cooldownUntil = TELEPORT_RESPAWN_AT.get(uuid);
        if (cooldownUntil != null && petTicks < cooldownUntil.longValue()) {
            if (rig != null) removeRig(uuid, rig, store);
            return;
        }
        if (rig != null && hasTeleportJumped(player.getLocation(), rig)) {
            removeRig(uuid, rig, store);
            rig = null;
        }
        if (rig == null || rig.model.isDestroyed() || rig.entity.isDestroyed()) {
            if (rig != null) removeRig(uuid, rig, store);
            rig = spawnRig(player, blueprintId);
            if (rig != null) store.put(uuid, rig);
        }
        if (rig == null) return;
        if (!rig.ownerSees || petTicks - rig.pairedAt >= RE_PAIR_TICKS) {
            rig.ownerSees = ensureOwnerSees(player, rig);
            rig.pairedAt = petTicks;
        }
        ensurePivotMounted(player, rig);
        PlayerBodyTracker tracker = trackerFor(player);
        syncRigTransform(player, rig, tracker.getBodyYaw());
        ensureLivingAnimation(rig, tracker.getHorizSpeedBlocksPerTick());
        logRigReady(rig);
    }

    static void syncPet(Player player) {
        syncPlayerRigs(player);
    }

    static void syncPlayerRigs(Player player) {
        if (player == null || !player.isOnline()) return;
        syncSingleSlot(player, centipedeSelected(player), CENTIPEDE_BLUEPRINT, PETS);
        syncSingleSlot(player, kanekiSelected(player), KANEKI_BLUEPRINT, KAGUNES);
    }

    static void animatePets() {
        petTicks++;
        if (!TELEPORT_RESPAWN_AT.isEmpty()) {
            for (java.util.Map.Entry<java.util.UUID, Long> e : new java.util.ArrayList<>(TELEPORT_RESPAWN_AT.entrySet())) {
                if (petTicks < e.getValue().longValue()) continue;
                TELEPORT_RESPAWN_AT.remove(e.getKey());
                Player p = Bukkit.getPlayer(e.getKey());
                if (p != null && p.isOnline()) {
                    try {
                        syncPlayerRigs(p);
                    } catch (Throwable failure) {
                        reportOnce("респавн аксессуаров после телепорта", failure);
                    }
                }
            }
        }
        if (PETS.isEmpty() && KAGUNES.isEmpty()) return;

        java.util.Set<java.util.UUID> activePlayers = new java.util.LinkedHashSet<>();
        activePlayers.addAll(PETS.keySet());
        activePlayers.addAll(KAGUNES.keySet());

        for (java.util.UUID uuid : activePlayers) {
            Player wearer = Bukkit.getPlayer(uuid);
            if (wearer == null || !wearer.isOnline() || wearer.isDead()
                    || wearer.getGameMode() == GameMode.SPECTATOR) {
                releaseByUuid(uuid);
                continue;
            }
            PlayerBodyTracker tracker = trackerFor(wearer);
            tracker.stepServerTick(wearer);
            tickActiveRig(uuid, wearer, tracker, PETS, centipedeSelected(wearer));
            tickActiveRig(uuid, wearer, tracker, KAGUNES, kanekiSelected(wearer));
        }
    }

    private static void tickActiveRig(java.util.UUID uuid, Player wearer, PlayerBodyTracker tracker,
                                      java.util.Map<java.util.UUID, GhoulRig> store, boolean stillWanted) {
        GhoulRig rig = store.get(uuid);
        if (rig == null) return;
        try {
            if (!stillWanted || rig.model.isDestroyed() || rig.entity.isDestroyed()) {
                removeRig(uuid, rig, store);
                return;
            }
            if (hasTeleportJumped(wearer.getLocation(), rig)) {
                schedulePostTeleportRespawn(wearer, 1L);
                return;
            }
            if (!rig.ownerSees || petTicks - rig.pairedAt >= RE_PAIR_TICKS) {
                rig.ownerSees = ensureOwnerSees(wearer, rig);
                rig.pairedAt = petTicks;
            }
            ensurePivotMounted(wearer, rig);
            syncRigTransform(wearer, rig, tracker.getBodyYaw());
            ensureLivingAnimation(rig, tracker.getHorizSpeedBlocksPerTick());
            logRigReady(rig);
        } catch (Throwable failure) {
            reportOnce("тик аксессуара", failure);
        }
    }

    private static void logRigReady(GhoulRig rig) {
        if (rig.loggedReady || !rig.attached) return;
        rig.loggedReady = true;
        if (host == null) return;
        String label = KANEKI_BLUEPRINT.equals(rig.blueprintId)
            ? "кагуне Канэки Кена"
            : "сколопендра (по всему телу)";
        host.getLogger().info("[Аксессуары] " + label + ": живая анимация '" + IDLE_ANIM
            + "', привязка к PivotOverride активна");
    }

    private static GhoulRig spawnRig(Player player, String blueprintId) {
        ModelBlueprint blueprint = ModelEngineAPI.getBlueprint(blueprintId);
        if (blueprint == null) return null;

        Dummy<Player> dummy = new Dummy<>(player);
        Location loc = player.getLocation();
        if (loc != null) dummy.syncLocation(loc);
        dummy.setDetectingPlayers(true);
        dummy.setRenderRadius(VIEW_RANGE);
        dummy.setForceViewing(player, true);

        PlayerBodyTracker tracker = trackerFor(player);
        float bodyYaw = tracker.getBodyYaw();
        dummy.setYBodyRot(bodyYaw);
        dummy.setYHeadRot(bodyYaw);
        dummy.setXHeadRot(0.0F);
        BodyRotationController rot = dummy.getBodyRotationController();
        if (rot != null) {
            rot.setYBodyRot(bodyYaw);
            rot.setYHeadRot(bodyYaw);
            rot.setXHeadRot(0.0F);
        }

        ModeledEntity entity = ModelEngineAPI.createModeledEntity(dummy);
        if (entity == null) {
            entity = ModelEngineAPI.getOrCreateModeledEntity(player);
        }
        if (entity == null || entity.isDestroyed()) return null;
        entity.setBaseEntityVisible(false);
        entity.setModelRotationLocked(false);
        AnimationLODHandler lod = entity.getAnimationLodHandler();
        if (lod != null) lod.setEnabled(Boolean.FALSE);

        ActiveModel model = ModelEngineAPI.createActiveModel(blueprint);
        if (model == null) return null;
        model.setBlockLight(15);
        model.setSkyLight(15);
        model.setScale(1.0D);
        model.setCanHurt(false);
        model.setShadowVisible(false);
        model.setHitboxVisible(false);
        model.setLockPitch(true);
        model.setLockYaw(true);
        model.setViewRange(2.5F);

        PivotOverrideRegistry registry = ModelEngineAPI.getPivotOverrideRegistry();
        PivotOverride pivot = registry == null ? null : registry.getOrCreate(player);
        if (pivot != null) model.setPivotOverride(pivot);

        entity.addModel(model, false);
        model.setModelRotationLocked(Boolean.FALSE);
        PlayerAuraAttachment.syncModeledEntityImmediately(entity, bodyYaw);

        GhoulRig rig = new GhoulRig(blueprintId, dummy, entity, model, pivot, loc);
        rig.ownerSees = ensureOwnerSees(player, rig);
        rig.pairedAt = petTicks;
        ensurePivotMounted(player, rig);
        ensureLivingAnimation(rig, tracker.getHorizSpeedBlocksPerTick());
        return rig;
    }

    private static void removeRig(java.util.UUID playerUuid, GhoulRig rig,
                                  java.util.Map<java.util.UUID, GhoulRig> store) {
        store.remove(playerUuid);
        if (rig == null) return;
        detachPivotFromPlayer(rig);
        try {
            if (!rig.entity.isDestroyed()) rig.entity.removeModel(rig.blueprintId);
        } catch (Throwable ignored) {
        }
        try {
            if (!rig.model.isDestroyed()) rig.model.destroy();
        } catch (Throwable ignored) {
        }
        try {
            if (rig.dummy != null) {
                rig.dummy.setRemoved(true);
                ModelEngineAPI.removeModeledEntity(rig.dummy.getUUID());
            }
            if (!rig.entity.isDestroyed() && rig.dummy != null
                    && rig.entity.getBase() == rig.dummy) {
                rig.entity.destroy();
            }
        } catch (Throwable ignored) {
        }
    }

    private static void releaseByUuid(java.util.UUID uuid) {
        GhoulRig pet = PETS.get(uuid);
        if (pet != null) removeRig(uuid, pet, PETS);
        GhoulRig kagune = KAGUNES.get(uuid);
        if (kagune != null) removeRig(uuid, kagune, KAGUNES);
    }

    static void releasePet(Player player) {
        if (player == null) return;
        releaseByUuid(player.getUniqueId());
    }

    private static void schedulePostTeleportRespawn(Player player, long delayTicks) {
        if (player == null) return;
        java.util.UUID uuid = player.getUniqueId();
        releaseByUuid(uuid);
        if (centipedeSelected(player) || kanekiSelected(player)) {
            TELEPORT_RESPAWN_AT.put(uuid, Long.valueOf(petTicks + Math.max(1L, delayTicks)));
        }
    }

    static void logLoadedModels() {
        if (modelsLogged || host == null) return;
        modelsLogged = true;
        StringBuilder missing = new StringBuilder();
        for (String id : new String[] {"elytrix_angel_wings", "elytrix_angel_halo",
                                       KANEKI_BLUEPRINT, CENTIPEDE_BLUEPRINT}) {
            if (ModelEngineAPI.getBlueprint(id) == null) {
                if (missing.length() > 0) missing.append(", ");
                missing.append(id);
            }
        }
        try {
            if (missing.length() == 0) {
                host.getLogger().info("[Аксессуары] ModelEngine загрузил все модели: крылья, нимб, кагуне Канэки, сколопендра");
            } else {
                host.getLogger().warning("[Аксессуары] ModelEngine не загрузил: " + missing
                    + " — проверь plugins/ModelEngine/blueprints и лог ModelEngine");
            }
        } catch (Throwable ignored) {
        }
    }

    static void tickAll() {
        try {
            logLoadedModels();
            for (Player player : Bukkit.getOnlinePlayers()) {
                try {
                    syncPlayerRigs(player);
                } catch (Throwable failure) {
                    reportOnce("синхронизация аксессуаров", failure);
                }
            }
        } catch (Throwable ignored) {
        }
    }

    // ------------------------------------------------------------------ player lifecycle events

    @EventHandler public void onMove(PlayerMoveEvent event) {
        if (event.isCancelled()) return;
        Player player = event.getPlayer();
        if (player == null) return;
        java.util.UUID uuid = player.getUniqueId();
        GhoulRig pet = PETS.get(uuid);
        GhoulRig kagune = KAGUNES.get(uuid);
        if ((pet == null || pet.model.isDestroyed()) && (kagune == null || kagune.model.isDestroyed())) {
            return;
        }
        Location to = event.getTo();
        if (to == null) return;
        if ((pet != null && hasTeleportJumped(to, pet)) || (kagune != null && hasTeleportJumped(to, kagune))) {
            PlayerBodyTracker tracker = trackerFor(player);
            tracker.resetToYaw(to.getYaw());
            schedulePostTeleportRespawn(player, 2L);
            return;
        }
        PlayerBodyTracker tracker = trackerFor(player);
        tracker.stepFromPacket(player, to);
        float yaw = tracker.getBodyYaw();
        if (pet != null) syncRigTransform(player, pet, yaw);
        if (kagune != null) syncRigTransform(player, kagune, yaw);
    }

    @EventHandler public void onTeleport(PlayerTeleportEvent event) {
        if (event.isCancelled()) return;
        Player player = event.getPlayer();
        if (player == null) return;
        Location to = event.getTo();
        if (to != null) {
            PlayerBodyTracker tracker = trackerFor(player);
            tracker.resetToYaw(to.getYaw());
        }
        schedulePostTeleportRespawn(player, 2L);
    }

    @EventHandler public void onArmSwing(PlayerAnimationEvent event) {
        Player player = event.getPlayer();
        if (player == null) return;
        PlayerBodyTracker tracker = TRACKERS.get(player.getUniqueId());
        if (tracker != null) tracker.notifyArmSwing();
    }

    @EventHandler public void onQuit(PlayerQuitEvent event) {
        Player player = event.getPlayer();
        if (player == null) return;
        java.util.UUID uuid = player.getUniqueId();
        releaseByUuid(uuid);
        TELEPORT_RESPAWN_AT.remove(uuid);
        TRACKERS.remove(uuid);
    }

    @EventHandler public void onDeath(PlayerDeathEvent event) {
        Player player = event.getEntity();
        if (player == null) return;
        releaseByUuid(player.getUniqueId());
        TELEPORT_RESPAWN_AT.remove(player.getUniqueId());
    }

    @EventHandler public void onRespawn(PlayerRespawnEvent event) {
        Player player = event.getPlayer();
        if (player == null) return;
        schedulePostTeleportRespawn(player, 2L);
    }

    @EventHandler public void onWorldChange(PlayerChangedWorldEvent event) {
        Player player = event.getPlayer();
        if (player == null) return;
        schedulePostTeleportRespawn(player, 2L);
    }

    // ------------------------------------------------------------------ menu

    private static final class Holder implements InventoryHolder {
        private Inventory inventory;
        @Override public Inventory getInventory() { return inventory; }
    }

    private static ItemStack item(Material mat, String title, String model, String... lore) {
        ItemStack result = new ItemStack(mat);
        ItemMeta meta = result.getItemMeta();
        if (meta != null) {
            meta.setDisplayName(title);
            meta.setLore(java.util.Arrays.asList(lore));
            if (model != null) meta.setItemModel(new NamespacedKey("reallyworld", model));
            result.setItemMeta(meta);
        }
        return result;
    }

    private static String[] lore(String hint, String... body) {
        String[] out = new String[body.length + 2];
        out[0] = "";
        System.arraycopy(body, 0, out, 1, body.length);
        out[out.length - 1] = hint;
        return out;
    }

    static void openMenu(Player player) {
        Holder holder = new Holder();
        Inventory menu = Bukkit.createInventory(holder, 54, "§fꈁꀀꈂꌀꈂꀁ§fꈃꏠ");
        holder.inventory = menu;
        boolean allowed = allowed(player);
        if (allowed) {
            try {
                syncPlayerRigs(player);
            } catch (Throwable failure) {
                reportOnce("меню синхронизация", failure);
            }
        }
        String hint = allowed ? "§dНажми, чтобы выбрать" : "§cДоступно с доната §dmedia";
        String chosen = allowed ? "§a● Сейчас надето" : "§8● Недоступно";
        String back = get(player, BACK);
        String head = headChoice(player);
        boolean wings = back.equals("wings"), kagune = back.equals("kaneki");
        boolean halo = head.equals("halo"), bug = allowed && get(player, PET).equals(PET_CHOICE);
        menu.setItem(12, item(Material.FEATHER, "§x§F§A§D§8§F§C§lАнгельские крылья", "angel_wings",
            wings ? lore(chosen, "§7Аксессуар для спины", "§7Не занимает слот брони", "§7Нажми ещё раз — снять")
                  : lore(hint, "§7Аксессуар для спины", "§7Не занимает слот брони")));
        menu.setItem(13, item(Material.NETHER_STAR, "§x§F§A§D§8§F§C§lБожественный нимб", "angel_halo",
            halo ? lore(chosen, "§7Нимб на голову", "§7Нажми ещё раз — снять")
                 : lore(hint, "§7Нимб на голову")));
        menu.setItem(14, item(Material.RED_DYE, "§x§F§A§D§8§F§C§lЩупальца Канэки", "kaneki_tentacles_icon",
            kagune ? lore(chosen, "§7Кагуне Ринкаку Канэки Кена (Токийский Гуль)", "§74 живых алых хвоста из какухо на спине", "§7Нажми ещё раз — снять")
                   : lore(hint, "§7Кагуне Ринкаку Канэки Кена (Токийский Гуль)", "§74 живых алых хвоста из какухо на спине")));
        menu.setItem(15, item(Material.SPIDER_EYE, "§x§F§A§D§8§F§C§lСколопендра Гуля", "centipede_icon",
            bug ? lore(chosen, "§7Живая сколопендра ползает по всему телу", "§7Грудь, плечи, шея, спина, руки и бёдра", "§7Нажми ещё раз — снять")
                : lore(hint, "§7Живая сколопендра ползает по всему телу", "§7Грудь, плечи, шея, спина, руки и бёдра")));
        menu.setItem(49, item(Material.BARRIER, "§cСнять всё", null,
            lore("§dНажми, чтобы снять", "§7Убирает все надетые аксессуары")));
        player.openInventory(menu);
    }

    @Override public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) { sender.sendMessage("Только для игроков."); return true; }
        grantDonationAccess();
        try {
            openMenu(player);
        } catch (Throwable failure) {
            reportOnce("меню", failure);
            player.sendMessage("§cМеню аксессуаров не открылось, причина записана в лог.");
        }
        return true;
    }

    private static void setHead(Player player, String choice) {
        set(player, HEAD, choice);
        set(player, HALO, "");
    }

    @EventHandler public void onClick(InventoryClickEvent event) {
        if (!(event.getView().getTopInventory().getHolder() instanceof Holder)) return;
        event.setCancelled(true);
        if (!(event.getWhoClicked() instanceof Player player)) return;
        int slot = event.getRawSlot();
        if (!allowed(player)) {
            player.sendMessage("§cАксессуары доступны с доната §d" + MEDIA_GROUP + "§c.");
            return;
        }
        String blueprint = slot == 12 ? "elytrix_angel_wings" : slot == 13 ? "elytrix_angel_halo"
            : slot == 14 ? KANEKI_BLUEPRINT : slot == 15 ? CENTIPEDE_BLUEPRINT : null;
        if (blueprint != null && ModelEngineAPI.getBlueprint(blueprint) == null) {
            player.sendMessage("§cМодель ещё не загружена. Обратитесь к администрации.");
            return;
        }
        if (slot == 12) { toggleWings(player); }
        else if (slot == 14) { toggleKaneki(player); }
        else if (slot == 13) { toggleHead(player, "halo", "Нимб", "надет", "снят"); }
        else if (slot == 15) { togglePet(player); }
        else if (slot == 49) {
            set(player, BACK, "");
            setHead(player, "");
            set(player, PET, "");
            TELEPORT_RESPAWN_AT.remove(player.getUniqueId());
            releaseByUuid(player.getUniqueId());
            player.sendMessage("§7Все аксессуары сняты.");
        } else return;
        openMenu(player);
    }

    private static void toggleWings(Player player) {
        if (get(player, BACK).equals("wings")) {
            set(player, BACK, "");
            player.sendMessage("§7Крылья сняты.");
            return;
        }
        set(player, BACK, "wings");
        GhoulRig kagune = KAGUNES.get(player.getUniqueId());
        if (kagune != null) removeRig(player.getUniqueId(), kagune, KAGUNES);
        player.sendMessage("§dКрылья надеты.");
    }

    private static void toggleKaneki(Player player) {
        if (get(player, BACK).equals("kaneki")) {
            set(player, BACK, "");
            GhoulRig kagune = KAGUNES.get(player.getUniqueId());
            if (kagune != null) removeRig(player.getUniqueId(), kagune, KAGUNES);
            player.sendMessage("§7Щупальца Канэки сняты.");
            return;
        }
        if (ModelEngineAPI.getBlueprint(KANEKI_BLUEPRINT) == null) {
            player.sendMessage("§cМодель кагуне Канэки ещё не загружена. Обратитесь к администрации.");
            return;
        }
        set(player, BACK, "kaneki");
        TELEPORT_RESPAWN_AT.remove(player.getUniqueId());
        try {
            syncPlayerRigs(player);
        } catch (Throwable failure) {
            reportOnce("кагуне Канэки", failure);
            set(player, BACK, "");
            player.sendMessage("§cЩупальца Канэки не появились: " + failure.getClass().getSimpleName());
            return;
        }
        if (!wearingKaneki(player)) {
            set(player, BACK, "");
            player.sendMessage("§cЩупальца Канэки не появились: модель не загрузилась.");
            return;
        }
        player.sendMessage("§dКагуне Канэки Кена пробуждено.");
    }

    private static void togglePet(Player player) {
        if (get(player, PET).equals(PET_CHOICE)) {
            set(player, PET, "");
            GhoulRig pet = PETS.get(player.getUniqueId());
            if (pet != null) removeRig(player.getUniqueId(), pet, PETS);
            player.sendMessage("§7Сколопендра снята.");
            return;
        }
        if (ModelEngineAPI.getBlueprint(CENTIPEDE_BLUEPRINT) == null) {
            player.sendMessage("§cМодель сколопендры ещё не загружена. Обратитесь к администрации.");
            return;
        }
        set(player, PET, PET_CHOICE);
        TELEPORT_RESPAWN_AT.remove(player.getUniqueId());
        try {
            syncPlayerRigs(player);
        } catch (Throwable failure) {
            reportOnce("сколопендра", failure);
            set(player, PET, "");
            player.sendMessage("§cСколопендра не появилась: " + failure.getClass().getSimpleName());
            return;
        }
        if (!wearingCentipede(player)) {
            set(player, PET, "");
            player.sendMessage("§cСколопендра не появилась: модель не загрузилась.");
            return;
        }
        player.sendMessage("§dСколопендра Гуля выпущена и ползает по всему телу.");
    }

    private static void toggleHead(Player player, String choice, String name, String on, String off) {
        if (headChoice(player).equals(choice)) {
            setHead(player, "");
            player.sendMessage("§7" + name + " " + off + ".");
        } else {
            setHead(player, choice);
            player.sendMessage("§d" + name + " " + on + ".");
        }
    }

    @EventHandler public void onDrag(InventoryDragEvent event) {
        if (event.getView().getTopInventory().getHolder() instanceof Holder) event.setCancelled(true);
    }
}
