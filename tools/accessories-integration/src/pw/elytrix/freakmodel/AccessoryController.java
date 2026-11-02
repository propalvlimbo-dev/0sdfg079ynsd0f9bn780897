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
 * Server-side accessories menu & controller: Angel Wings, Divine Halo, Kaneki Kagune,
 * and the Tokyo Ghoul Scolopendra (elytrix_centipede) coiled around neck & shoulders.
 *
 * <p>Architecture highlights for the Scolopendra:
 * <ul>
 *   <li>Uses an isolated {@link Dummy} base entity so its UUID and entityId never
 *       collide with {@code WornAngelRig}'s {@code PlayerAuraAttachment(player)} —
 *       wings, halo, kagune, and scolopendra can be toggled in any combination.</li>
 *   <li>Rides the player's {@link PivotOverride} via passenger packet mounting for
 *       zero rubberbanding, while {@link PlayerBodyTracker} locks rotation strictly
 *       to the player's torso {@code yBodyRot} (zero camera pitch tilt, zero turn lag).</li>
 *   <li>Plays the blueprint's native multithreaded {@code "idle"} keyframe animation
 *       (14 undulating tergites + 24 metachronal scurrying legs + snapping venomous
 *       fangs + 2-stage whip antennae + scissoring tail cerci), dynamically scaling
 *       animation speed with movement speed.</li>
 * </ul>
 */
public final class AccessoryController implements CommandExecutor, Listener {
    static final NamespacedKey BACK = new NamespacedKey("elytrixaccessories", "back");
    static final NamespacedKey HALO = new NamespacedKey("elytrixaccessories", "halo");
    static final NamespacedKey HEAD = new NamespacedKey("elytrixaccessories", "head");
    static final NamespacedKey PET = new NamespacedKey("elytrixaccessories", "pet");
    static final String PET_CHOICE = "centipede";
    static final String CENTIPEDE_BLUEPRINT = "elytrix_centipede";
    static final String CENTIPEDE_ANIM = "idle";
    static final String MEDIA_GROUP = "media";
    static final String USE_PERMISSION = "elytrixaccessories.use";
    static final int VIEW_RANGE = 96;
    static final long RE_PAIR_TICKS = 100;

    private static boolean mediaGranted;
    private static ElytrixFreakModelPlugin host;
    private static final java.util.Map<java.util.UUID, Pet> PETS = new java.util.HashMap<>();
    private static final java.util.Map<java.util.UUID, PlayerBodyTracker> TRACKERS = new java.util.HashMap<>();
    private static final java.util.Set<String> REPORTED = new java.util.HashSet<>();
    static long petTicks;
    private static FreakModelSpec cachedTentacles;
    private static boolean modelsLogged;

    private AccessoryController() {}

    /** Live neck/shoulder scolopendra bound to one player. */
    private static final class Pet {
        final Dummy<Player> dummy;
        final ModeledEntity entity;
        final ActiveModel model;
        final PivotOverride pivot;
        IAnimationProperty animProperty;
        boolean statesCleared;
        boolean attached;
        int attachedPivotId = -1;
        boolean ownerSees;
        long pairedAt;
        boolean rescued;
        int lostTicks;
        boolean loggedReady;

        Pet(Dummy<Player> dummy, ModeledEntity entity, ActiveModel model, PivotOverride pivot) {
            this.dummy = dummy;
            this.entity = entity;
            this.model = model;
            this.pivot = pivot;
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
        return player.hasPermission("elytrixaccessories.admin") || player.hasPermission(USE_PERMISSION);
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

    public static FreakModelSpec back(ElytrixFreakModelPlugin plugin, Player player) {
        if (!allowed(player)) return null;
        String selection = get(player, BACK);
        if (selection.equals("wings")) return plugin.findModel("angel_wings");
        if (selection.equals("kaneki")) return kaneki(plugin);
        return null;
    }

    static FreakModelSpec kaneki(ElytrixFreakModelPlugin plugin) {
        FreakModelSpec configured = plugin.findModel("elytrix_kaneki_tentacles");
        if (configured != null) return configured;
        FreakModelSpec base = plugin.findModel("angel_wings");
        if (base == null) return null;
        if (cachedTentacles != null) return cachedTentacles;
        cachedTentacles = new FreakModelSpec("elytrix_kaneki_tentacles", base.kind, "elytrix_kaneki_tentacles",
            java.util.List.of(), org.bukkit.Material.RED_DYE, "kaneki_tentacles_icon", 35,
            "Щупальца Канэки", java.util.List.of(), 1.0F, 0.0F, 0.0D, 0.9F, 0.9F, 1, 0,
            0.0D, 0.0D, 0.0D, 0.0D, 0.0D, 0.0D, 0.0D, 0.0D, 0.0F, 0.0D, false, false);
        return cachedTentacles;
    }

    public static boolean kanekiSelected(Player player) {
        return allowed(player) && get(player, BACK).equals("kaneki");
    }

    // ------------------------------------------------------------------ scolopendra

    public static boolean centipedeSelected(Player player) {
        return player != null
            && player.isOnline()
            && !player.isDead()
            && player.getGameMode() != GameMode.SPECTATOR
            && allowed(player)
            && get(player, PET).equals(PET_CHOICE);
    }

    static boolean wearingCentipede(Player player) {
        Pet pet = PETS.get(player.getUniqueId());
        return pet != null && !pet.model.isDestroyed() && !pet.entity.isDestroyed();
    }

    static boolean centipedeAttached(Player player) {
        Pet pet = PETS.get(player.getUniqueId());
        return pet != null && pet.attached;
    }

    static boolean centipedeAnimating(Player player) {
        Pet pet = PETS.get(player.getUniqueId());
        if (pet == null || pet.model.isDestroyed()) return false;
        AnimationHandler handler = pet.model.getAnimationHandler();
        return handler != null && handler.isPlayingAnimation(CENTIPEDE_ANIM);
    }

    private static PlayerBodyTracker trackerFor(Player player) {
        return TRACKERS.computeIfAbsent(player.getUniqueId(), uuid -> {
            PlayerBodyTracker t = new PlayerBodyTracker();
            t.resetToPlayer(player);
            return t;
        });
    }

    static boolean ensureOwnerSees(Player player, Pet pet) {
        if (player == null || pet == null || pet.model == null || pet.model.isDestroyed()) return false;
        ModeledEntity entity = pet.entity;
        if (entity == null || entity.isDestroyed()) return false;
        try {
            if (pet.dummy != null) {
                pet.dummy.setDetectingPlayers(true);
                pet.dummy.setRenderRadius(VIEW_RANGE);
                pet.dummy.setForceViewing(player, true);
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
            reportOnce("питомец", failure);
            return -1;
        }
        if (!(renderer instanceof DisplayRenderer)) return -1;
        DisplayRenderer display = (DisplayRenderer) renderer;
        if (!display.isInitialized()) return -1;
        DisplayRenderer.Pivot pivotEntity = display.getPivot();
        return pivotEntity == null ? -1 : pivotEntity.getId();
    }

    static boolean attachPivotToPlayer(Pet pet) {
        if (pet == null || pet.pivot == null) return false;
        int id = resolvePivotEntityId(pet.model);
        if (id < 0) return false;
        pet.attachedPivotId = id;
        if (!pet.pivot.getPassengers().contains(id)) pet.pivot.addPassenger(id);
        pet.pivot.getPassengers().markDirty();
        return true;
    }

    private static void detachPivotFromPlayer(Pet pet) {
        if (pet == null || pet.pivot == null) return;
        try {
            int id = pet.attachedPivotId >= 0 ? pet.attachedPivotId : resolvePivotEntityId(pet.model);
            if (id >= 0) {
                pet.pivot.removePassenger(id);
                if (pet.pivot.getPassengers() != null) pet.pivot.getPassengers().markDirty();
            }
        } catch (Throwable ignored) {
        }
    }

    private static void syncPetTransform(Player player, Pet pet, float bodyYaw) {
        if (player == null || pet == null || pet.entity == null || pet.entity.isDestroyed()) return;
        float safeYaw = Float.isFinite(bodyYaw) ? bodyYaw : 0.0F;
        try {
            Location loc = player.getLocation();
            if (pet.dummy != null) {
                if (loc != null) pet.dummy.syncLocation(loc);
                pet.dummy.setYBodyRot(safeYaw);
                pet.dummy.setYHeadRot(safeYaw);
                pet.dummy.setXHeadRot(0.0F);
                BodyRotationController rot = pet.dummy.getBodyRotationController();
                if (rot != null) {
                    rot.setYBodyRot(safeYaw);
                    rot.setYHeadRot(safeYaw);
                    rot.setXHeadRot(0.0F);
                }
            }
            PlayerAuraAttachment.syncModeledEntityImmediately(pet.entity, safeYaw);
        } catch (Throwable failure) {
            reportOnce("поворот сколопендры", failure);
        }
    }

    private static void ensureLivingAnimation(Pet pet, double horizSpeed) {
        if (pet == null || pet.model == null || pet.model.isDestroyed()) return;
        AnimationHandler handler;
        try {
            handler = pet.model.getAnimationHandler();
        } catch (Throwable failure) {
            reportOnce("анимация сколопендры", failure);
            return;
        }
        if (handler == null) return;
        if (!pet.statesCleared) {
            pet.statesCleared = true;
            for (ModelState state : ModelState.values()) {
                handler.setDefaultProperty(new AnimationHandler.DefaultProperty(state, "", 0.0D, 0.0D, 1.0D));
            }
        }
        double targetSpeed = 1.0D + Math.min(0.75D, Math.max(0.0D, horizSpeed) * 2.2D);
        if (!handler.isPlayingAnimation(CENTIPEDE_ANIM) || pet.animProperty == null) {
            IAnimationProperty prop = handler.playAnimation(CENTIPEDE_ANIM, 0.0D, 0.0D, targetSpeed, true);
            if (prop != null) {
                prop.setForceLoopMode(BlueprintAnimation.LoopMode.LOOP);
                prop.setSpeed(targetSpeed);
            }
            pet.animProperty = prop;
        } else {
            pet.animProperty.setSpeed(targetSpeed);
        }
    }

    static void syncPet(Player player) {
        if (player == null || !player.isOnline()) return;
        boolean want = centipedeSelected(player);
        Pet pet = PETS.get(player.getUniqueId());
        if (want && (pet == null || pet.model.isDestroyed() || pet.entity.isDestroyed())) {
            if (pet != null) removePet(player.getUniqueId(), pet);
            pet = spawnPet(player);
            if (pet != null) PETS.put(player.getUniqueId(), pet);
        } else if (!want && pet != null) {
            removePet(player.getUniqueId(), pet);
            return;
        }
        if (!want || pet == null) return;
        rescuesIfLost(pet, player);
        if (!pet.ownerSees || petTicks - pet.pairedAt > RE_PAIR_TICKS) {
            pet.ownerSees = ensureOwnerSees(player, pet);
            pet.pairedAt = petTicks;
        }
        if (!pet.attached) pet.attached = attachPivotToPlayer(pet);
        PlayerBodyTracker tracker = trackerFor(player);
        syncPetTransform(player, pet, tracker.getBodyYaw());
        ensureLivingAnimation(pet, tracker.getHorizSpeedBlocksPerTick());
        logPetReady(pet, pivotDistance(pet.model, player));
    }

    static void animatePets() {
        petTicks++;
        if (PETS.isEmpty()) return;
        for (java.util.Map.Entry<java.util.UUID, Pet> entry : new java.util.ArrayList<>(PETS.entrySet())) {
            java.util.UUID uuid = entry.getKey();
            Pet pet = entry.getValue();
            try {
                if (pet.model.isDestroyed() || pet.entity.isDestroyed()) {
                    removePet(uuid, pet);
                    continue;
                }
                Player wearer = Bukkit.getPlayer(uuid);
                if (wearer == null || !wearer.isOnline() || wearer.isDead()
                        || wearer.getGameMode() == GameMode.SPECTATOR) {
                    removePet(uuid, pet);
                    continue;
                }
                if (!pet.attached) pet.attached = attachPivotToPlayer(pet);
                PlayerBodyTracker tracker = trackerFor(wearer);
                tracker.stepServerTick(wearer);
                syncPetTransform(wearer, pet, tracker.getBodyYaw());
                ensureLivingAnimation(pet, tracker.getHorizSpeedBlocksPerTick());
                logPetReady(pet, pivotDistance(pet.model, wearer));
            } catch (Throwable failure) {
                reportOnce("питомец", failure);
            }
        }
    }

    private static void logPetReady(Pet pet, double pivotDistance) {
        if (pet.loggedReady || !pet.attached) return;
        pet.loggedReady = true;
        if (host == null) return;
        host.getLogger().info("[Аксессуары] сколопендра: живая анимация '" + CENTIPEDE_ANIM
            + "', модель привязана к шее и плечам игрока"
            + ", " + (pet.ownerSees ? "владелец в трекинге, куллинг выключен"
                                    : "ожидание трекинга владельца")
            + (pivotDistance < 0.0D ? ""
                                    : String.format(java.util.Locale.ROOT,
                                        ", pivot в %.2f блока", pivotDistance)));
    }

    private static void rescuesIfLost(Pet pet, Player player) {
        if (pet.rescued || !pet.attached) return;
        double distance = pivotDistance(pet.model, player);
        if (distance < 0.0D || distance < 8.0D) {
            pet.lostTicks = 0;
            return;
        }
        if (++pet.lostTicks < 3) return;
        pet.rescued = true;
        try {
            removePet(player.getUniqueId(), pet);
        } catch (Throwable ignored) {
        }
        if (host != null) host.getLogger().warning("[Аксессуары] сколопендра отстала от игрока на "
            + String.format(java.util.Locale.ROOT, "%.1f", distance) + " блока — пересоздал модель");
    }

    static double pivotDistance(ActiveModel model, Player player) {
        try {
            ModelRenderer renderer = model.getModelRenderer();
            if (!(renderer instanceof DisplayRenderer)) return -1.0D;
            DisplayRenderer display = (DisplayRenderer) renderer;
            DisplayRenderer.Pivot pivot = display.getPivot();
            if (pivot == null || pivot.getPosition() == null) return -1.0D;
            Object position = pivot.getPosition().get();
            if (!(position instanceof org.joml.Vector3f)) return -1.0D;
            org.joml.Vector3f p = (org.joml.Vector3f) position;
            org.bukkit.Location loc = player.getLocation();
            double dx = p.x - loc.getX(), dy = p.y - loc.getY(), dz = p.z - loc.getZ();
            return Math.sqrt(dx * dx + dy * dy + dz * dz);
        } catch (Throwable ignored) {
            return -1.0D;
        }
    }

    private static Pet spawnPet(Player player) {
        ModelBlueprint blueprint = ModelEngineAPI.getBlueprint(CENTIPEDE_BLUEPRINT);
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
            // Fallback for mock harnesses that only implement getOrCreateModeledEntity(Entity)
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

        Pet pet = new Pet(dummy, entity, model, pivot);
        pet.ownerSees = ensureOwnerSees(player, pet);
        pet.pairedAt = petTicks;
        pet.attached = attachPivotToPlayer(pet);
        ensureLivingAnimation(pet, tracker.getHorizSpeedBlocksPerTick());
        return pet;
    }

    private static void removePet(java.util.UUID playerUuid, Pet pet) {
        PETS.remove(playerUuid);
        if (pet == null) return;
        detachPivotFromPlayer(pet);
        try {
            if (!pet.entity.isDestroyed()) pet.entity.removeModel(CENTIPEDE_BLUEPRINT);
        } catch (Throwable ignored) {
        }
        try {
            if (!pet.model.isDestroyed()) pet.model.destroy();
        } catch (Throwable ignored) {
        }
        try {
            if (pet.dummy != null) {
                pet.dummy.setRemoved(true);
                ModelEngineAPI.removeModeledEntity(pet.dummy.getUUID());
            }
            if (!pet.entity.isDestroyed() && pet.dummy != null
                    && pet.entity.getBase() == pet.dummy) {
                pet.entity.destroy();
            }
        } catch (Throwable ignored) {
        }
    }

    static void releasePet(Player player) {
        if (player == null) return;
        Pet pet = PETS.get(player.getUniqueId());
        if (pet != null) removePet(player.getUniqueId(), pet);
    }

    static void logLoadedModels() {
        if (modelsLogged || host == null) return;
        modelsLogged = true;
        StringBuilder missing = new StringBuilder();
        for (String id : new String[] {"angel_wings", "angel_halo", "elytrix_kaneki_tentacles",
                                       CENTIPEDE_BLUEPRINT}) {
            if (ModelEngineAPI.getBlueprint(id) == null) {
                if (missing.length() > 0) missing.append(", ");
                missing.append(id);
            }
        }
        try {
            if (missing.length() == 0) {
                host.getLogger().info("[Аксессуары] ModelEngine загрузил все модели: крылья, нимб, кагуне, сколопендра");
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
                    syncPet(player);
                } catch (Throwable failure) {
                    reportOnce("питомец", failure);
                }
            }
        } catch (Throwable ignored) {
        }
    }

    // ------------------------------------------------------------------ player lifecycle events

    @EventHandler public void onMove(PlayerMoveEvent event) {
        Player player = event.getPlayer();
        if (player == null) return;
        Pet pet = PETS.get(player.getUniqueId());
        if (pet == null || pet.model.isDestroyed()) return;
        Location to = event.getTo();
        if (to == null) return;
        PlayerBodyTracker tracker = trackerFor(player);
        tracker.stepFromPacket(player, to);
        syncPetTransform(player, pet, tracker.getBodyYaw());
    }

    @EventHandler public void onTeleport(PlayerTeleportEvent event) {
        Player player = event.getPlayer();
        if (player == null) return;
        Pet pet = PETS.get(player.getUniqueId());
        if (pet == null) return;
        Location to = event.getTo();
        if (to != null) {
            PlayerBodyTracker tracker = trackerFor(player);
            tracker.resetToYaw(to.getYaw());
            syncPetTransform(player, pet, tracker.getBodyYaw());
        }
        pet.attached = false;
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
        releasePet(player);
        TRACKERS.remove(player.getUniqueId());
    }

    @EventHandler public void onDeath(PlayerDeathEvent event) {
        releasePet(event.getEntity());
    }

    @EventHandler public void onRespawn(PlayerRespawnEvent event) {
        releasePet(event.getPlayer());
    }

    @EventHandler public void onWorldChange(PlayerChangedWorldEvent event) {
        releasePet(event.getPlayer());
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
                syncPet(player);
            } catch (Throwable failure) {
                reportOnce("питомец", failure);
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
            kagune ? lore(chosen, "§7Анимированный аксессуар для спины", "§7Нажми ещё раз — снять")
                   : lore(hint, "§7Анимированный аксессуар для спины")));
        menu.setItem(15, item(Material.SPIDER_EYE, "§x§F§A§D§8§F§C§lСколопендра Гуля", "centipede_icon",
            bug ? lore(chosen, "§7Обвивает шею и плечи", "§7Живая волна тела, лап, усиков и жвал", "§7Нажми ещё раз — снять")
                : lore(hint, "§7Обвивает шею и плечи", "§7Живая волна тела, лап, усиков и жвал")));
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
            : slot == 14 ? "elytrix_kaneki_tentacles" : slot == 15 ? CENTIPEDE_BLUEPRINT : null;
        if (blueprint != null && ModelEngineAPI.getBlueprint(blueprint) == null) {
            player.sendMessage("§cМодель ещё не загружена. Обратитесь к администрации."); return;
        }
        if (slot == 12) { toggleBack(player, "wings", "Крылья"); }
        else if (slot == 14) { toggleBack(player, "kaneki", "Щупальца Канэки"); }
        else if (slot == 13) { toggleHead(player, "halo", "Нимб", "надет", "снят"); }
        else if (slot == 15) { togglePet(player); }
        else if (slot == 49) {
            set(player, BACK, ""); setHead(player, "");
            set(player, PET, "");
            Pet pet = PETS.get(player.getUniqueId());
            if (pet != null) removePet(player.getUniqueId(), pet);
            player.sendMessage("§7Все аксессуары сняты.");
        } else return;
        openMenu(player);
    }

    private static void togglePet(Player player) {
        if (get(player, PET).equals(PET_CHOICE)) {
            set(player, PET, "");
            Pet pet = PETS.get(player.getUniqueId());
            if (pet != null) removePet(player.getUniqueId(), pet);
            player.sendMessage("§7Сколопендра снята.");
            return;
        }
        if (ModelEngineAPI.getBlueprint(CENTIPEDE_BLUEPRINT) == null) {
            player.sendMessage("§cМодель сколопендры ещё не загружена. Обратитесь к администрации.");
            return;
        }
        set(player, PET, PET_CHOICE);
        try {
            syncPet(player);
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
        player.sendMessage("§dСколопендра обвилась вокруг шеи и плеч.");
    }

    private static void toggleBack(Player player, String choice, String name) {
        if (get(player, BACK).equals(choice)) {
            set(player, BACK, "");
            player.sendMessage("§7" + name + " сняты.");
        } else {
            set(player, BACK, choice);
            player.sendMessage("§d" + name + " надеты.");
        }
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
