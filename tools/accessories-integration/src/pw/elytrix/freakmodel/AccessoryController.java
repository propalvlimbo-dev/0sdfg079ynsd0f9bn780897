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
import java.util.Locale;
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
 * Server-side 3-section accessories menu & unified ModelEngine controller (v3.16.0):
 * <ul>
 *   <li><b>Спина</b>: Ангельские крылья ({@code angel_wings}) и Щупальца Канэки ({@code elytrix_kaneki_tentacles})</li>
 *   <li><b>Шапки</b>: Божественный нимб ({@code angel_halo})</li>
 *   <li><b>Питомцы</b>: Мини-Роузи ({@code elytrix_mini_me}), Милый котёнок ({@code elytrix_cute_kitten}),
 *       Меллстрой ({@code elytrix_mellstroy}, с 3D-анимациями табличек внутри модели и настоящей озвучкой)
 *       и Сколопендра Гуля ({@code elytrix_centipede})</li>
 * </ul>
 */
public final class AccessoryController implements CommandExecutor, Listener {
    static final NamespacedKey BACK = new NamespacedKey("elytrixaccessories", "back");
    static final NamespacedKey HALO = new NamespacedKey("elytrixaccessories", "halo");
    static final NamespacedKey HEAD = new NamespacedKey("elytrixaccessories", "head");
    static final NamespacedKey PET = new NamespacedKey("elytrixaccessories", "pet");

    static final String PET_CENTIPEDE = "centipede";
    static final String PET_CHOICE = PET_CENTIPEDE;
    static final String PET_MINI_ME = "mini_me";
    static final String PET_KITTEN = "kitten";
    static final String PET_MELLSTROY = "mellstroy";

    static final String CENTIPEDE_BLUEPRINT = "elytrix_centipede";
    static final String MINI_ME_BLUEPRINT = "elytrix_mini_me";
    static final String KITTEN_BLUEPRINT = "elytrix_cute_kitten";
    static final String MELLSTROY_BLUEPRINT = "elytrix_mellstroy";
    static final String KANEKI_BLUEPRINT = "elytrix_kaneki_tentacles";

    static final String IDLE_ANIM = "idle";
    static final String MEDIA_GROUP = "media";
    static final String USE_PERMISSION = "elytrixaccessories.use";
    static final int BACK_ARROW_CMD = 10002;
    static final int VIEW_RANGE = 96;
    static final long RE_PAIR_TICKS = 40L;
    static final int WARMUP_SYNC_TICKS = 40;
    static final double TELEPORT_JUMP_DIST_SQ = 24.0D * 24.0D;
    static final long EMOTE_MIN_DELAY_TICKS = 500L; // 25s
    static final long EMOTE_MAX_DELAY_TICKS = 900L; // 45s

    /** Synchronized (in-model 3D `D.Admin BAN`-style badge animation, real Mellstroy Ogg Vorbis sound) pairs. */
    static final String[][] MELLSTROY_EMOTES = {
        {"say_svet",     "reallyworld:mellstroy.privet"},
        {"say_amam",     "reallyworld:mellstroy.amam"},
        {"say_voznya",   "reallyworld:mellstroy.voznya"},
        {"say_babki",    "reallyworld:mellstroy.babki"},
        {"say_tancuem",  "reallyworld:mellstroy.tancuem"},
        {"say_miliciya", "reallyworld:mellstroy.miliciya"}
    };

    static final String TITLE_HUB = "§fꈁꀀꈂꏡꈂꀁ§fꈃꏠ";
    static final String TITLE_BACK = "§fꈁꀀꈂꏢꈂꀁ§fꈃꏤ";
    static final String TITLE_HATS = "§fꈁꀀꈂꏣꈂꀁ§fꈃꏥ";
    static final String TITLE_PETS = "§fꈁꀀꈂꏨꈂꀁ§fꈃꏦ";

    enum Section {
        HUB, BACK, HATS, PETS
    }

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

    /** Isolated Dummy-backed ModelEngine rig (Mini-Me Dancer, Scolopendra, or Kaneki Rinkaku Kagune). */
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
        long nextEmoteTick;
        int lastEmoteIndex = -1;
        String lastEmoteAnim;
        String lastEmoteSound;

        GhoulRig(String blueprintId, Dummy<Player> dummy, ModeledEntity entity,
                 ActiveModel model, PivotOverride pivot, Location spawnLoc) {
            this.blueprintId = blueprintId;
            this.dummy = dummy;
            this.entity = entity;
            this.model = model;
            this.pivot = pivot;
            this.nextEmoteTick = petTicks + randomEmoteDelayTicks();
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

    static String petChoice(Player player) {
        String choice = get(player, PET);
        if (PET_MINI_ME.equals(choice) || PET_KITTEN.equals(choice)
                || PET_MELLSTROY.equals(choice) || PET_CENTIPEDE.equals(choice)) {
            return choice;
        }
        return "";
    }

    static String desiredPetBlueprint(Player player) {
        if (player == null || !player.isOnline() || player.isDead()
                || player.getGameMode() == GameMode.SPECTATOR || !allowed(player)) {
            return null;
        }
        String choice = petChoice(player);
        if (PET_MINI_ME.equals(choice)) return MINI_ME_BLUEPRINT;
        if (PET_KITTEN.equals(choice)) return KITTEN_BLUEPRINT;
        if (PET_MELLSTROY.equals(choice)) return MELLSTROY_BLUEPRINT;
        if (PET_CENTIPEDE.equals(choice)) return CENTIPEDE_BLUEPRINT;
        return null;
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
        return CENTIPEDE_BLUEPRINT.equals(desiredPetBlueprint(player));
    }

    public static boolean miniMeSelected(Player player) {
        return MINI_ME_BLUEPRINT.equals(desiredPetBlueprint(player));
    }

    public static boolean kittenSelected(Player player) {
        return KITTEN_BLUEPRINT.equals(desiredPetBlueprint(player));
    }

    public static boolean mellstroySelected(Player player) {
        return MELLSTROY_BLUEPRINT.equals(desiredPetBlueprint(player));
    }

    static boolean wearingKaneki(Player player) {
        GhoulRig rig = KAGUNES.get(player.getUniqueId());
        return rig != null && KANEKI_BLUEPRINT.equals(rig.blueprintId)
            && !rig.model.isDestroyed() && !rig.entity.isDestroyed();
    }

    static boolean wearingCentipede(Player player) {
        GhoulRig rig = PETS.get(player.getUniqueId());
        return rig != null && CENTIPEDE_BLUEPRINT.equals(rig.blueprintId)
            && !rig.model.isDestroyed() && !rig.entity.isDestroyed();
    }

    static boolean wearingMiniMe(Player player) {
        GhoulRig rig = PETS.get(player.getUniqueId());
        return rig != null && MINI_ME_BLUEPRINT.equals(rig.blueprintId)
            && !rig.model.isDestroyed() && !rig.entity.isDestroyed();
    }

    static boolean wearingKitten(Player player) {
        GhoulRig rig = PETS.get(player.getUniqueId());
        return rig != null && KITTEN_BLUEPRINT.equals(rig.blueprintId)
            && !rig.model.isDestroyed() && !rig.entity.isDestroyed();
    }

    static boolean wearingMellstroy(Player player) {
        GhoulRig rig = PETS.get(player.getUniqueId());
        return rig != null && MELLSTROY_BLUEPRINT.equals(rig.blueprintId)
            && !rig.model.isDestroyed() && !rig.entity.isDestroyed();
    }

    static boolean centipedeAttached(Player player) {
        GhoulRig rig = PETS.get(player.getUniqueId());
        return rig != null && CENTIPEDE_BLUEPRINT.equals(rig.blueprintId) && rig.attached;
    }

    static boolean miniMeAttached(Player player) {
        GhoulRig rig = PETS.get(player.getUniqueId());
        return rig != null && MINI_ME_BLUEPRINT.equals(rig.blueprintId) && rig.attached;
    }

    static boolean kittenAttached(Player player) {
        GhoulRig rig = PETS.get(player.getUniqueId());
        return rig != null && KITTEN_BLUEPRINT.equals(rig.blueprintId) && rig.attached;
    }

    static boolean mellstroyAttached(Player player) {
        GhoulRig rig = PETS.get(player.getUniqueId());
        return rig != null && MELLSTROY_BLUEPRINT.equals(rig.blueprintId) && rig.attached;
    }

    static boolean kanekiAttached(Player player) {
        GhoulRig rig = KAGUNES.get(player.getUniqueId());
        return rig != null && rig.attached;
    }

    static boolean centipedeAnimating(Player player) {
        GhoulRig rig = PETS.get(player.getUniqueId());
        if (rig == null || !CENTIPEDE_BLUEPRINT.equals(rig.blueprintId) || rig.model.isDestroyed()) return false;
        AnimationHandler handler = rig.model.getAnimationHandler();
        return handler != null && handler.isPlayingAnimation(IDLE_ANIM);
    }

    static boolean miniMeAnimating(Player player) {
        GhoulRig rig = PETS.get(player.getUniqueId());
        if (rig == null || !MINI_ME_BLUEPRINT.equals(rig.blueprintId) || rig.model.isDestroyed()) return false;
        AnimationHandler handler = rig.model.getAnimationHandler();
        return handler != null && handler.isPlayingAnimation(IDLE_ANIM);
    }

    static boolean kittenAnimating(Player player) {
        GhoulRig rig = PETS.get(player.getUniqueId());
        if (rig == null || !KITTEN_BLUEPRINT.equals(rig.blueprintId) || rig.model.isDestroyed()) return false;
        AnimationHandler handler = rig.model.getAnimationHandler();
        return handler != null && handler.isPlayingAnimation(IDLE_ANIM);
    }

    static boolean mellstroyAnimating(Player player) {
        GhoulRig rig = PETS.get(player.getUniqueId());
        if (rig == null || !MELLSTROY_BLUEPRINT.equals(rig.blueprintId) || rig.model.isDestroyed()) return false;
        AnimationHandler handler = rig.model.getAnimationHandler();
        return handler != null && handler.isPlayingAnimation(IDLE_ANIM);
    }

    static String mellstroyLastEmote(Player player) {
        GhoulRig rig = PETS.get(player.getUniqueId());
        return rig != null && MELLSTROY_BLUEPRINT.equals(rig.blueprintId) ? rig.lastEmoteAnim : null;
    }

    static String mellstroyLastSound(Player player) {
        GhoulRig rig = PETS.get(player.getUniqueId());
        return rig != null && MELLSTROY_BLUEPRINT.equals(rig.blueprintId) ? rig.lastEmoteSound : null;
    }

    static void forceNextEmoteDue(Player player) {
        GhoulRig rig = PETS.get(player.getUniqueId());
        if (rig != null && MELLSTROY_BLUEPRINT.equals(rig.blueprintId)) {
            rig.nextEmoteTick = petTicks;
        }
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
        double speedBoost = KANEKI_BLUEPRINT.equals(rig.blueprintId)
            ? 2.5D
            : (MINI_ME_BLUEPRINT.equals(rig.blueprintId) ? 1.5D : 1.8D);
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

    private static void syncSingleSlot(Player player, String desiredBlueprintId,
                                       java.util.Map<java.util.UUID, GhoulRig> store) {
        java.util.UUID uuid = player.getUniqueId();
        GhoulRig rig = store.get(uuid);
        if (desiredBlueprintId == null || desiredBlueprintId.isEmpty()) {
            if (rig != null) removeRig(uuid, rig, store);
            return;
        }
        Long cooldownUntil = TELEPORT_RESPAWN_AT.get(uuid);
        if (cooldownUntil != null && petTicks < cooldownUntil.longValue()) {
            if (rig != null) removeRig(uuid, rig, store);
            return;
        }
        if (rig != null && (!desiredBlueprintId.equals(rig.blueprintId)
                || hasTeleportJumped(player.getLocation(), rig))) {
            removeRig(uuid, rig, store);
            rig = null;
        }
        if (rig == null || rig.model.isDestroyed() || rig.entity.isDestroyed()) {
            if (rig != null) removeRig(uuid, rig, store);
            rig = spawnRig(player, desiredBlueprintId);
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
        syncSingleSlot(player, desiredPetBlueprint(player), PETS);
        syncSingleSlot(player, kanekiSelected(player) ? KANEKI_BLUEPRINT : null, KAGUNES);
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
            tickActiveRig(uuid, wearer, tracker, PETS, desiredPetBlueprint(wearer));
            tickActiveRig(uuid, wearer, tracker, KAGUNES, kanekiSelected(wearer) ? KANEKI_BLUEPRINT : null);
        }
    }

    private static void tickActiveRig(java.util.UUID uuid, Player wearer, PlayerBodyTracker tracker,
                                      java.util.Map<java.util.UUID, GhoulRig> store,
                                      String expectedBlueprintId) {
        GhoulRig rig = store.get(uuid);
        if (rig == null) return;
        try {
            if (expectedBlueprintId == null || !expectedBlueprintId.equals(rig.blueprintId)
                    || rig.model.isDestroyed() || rig.entity.isDestroyed()) {
                removeRig(uuid, rig, store);
                if (expectedBlueprintId != null) {
                    syncSingleSlot(wearer, expectedBlueprintId, store);
                }
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
            float bodyYaw = tracker.getBodyYaw();
            syncRigTransform(wearer, rig, bodyYaw);
            ensureLivingAnimation(rig, tracker.getHorizSpeedBlocksPerTick());
            if (MELLSTROY_BLUEPRINT.equals(rig.blueprintId)) {
                tickMellstroyEmote(wearer, rig, bodyYaw);
            }
            logRigReady(rig);
        } catch (Throwable failure) {
            reportOnce("тик аксессуара", failure);
        }
    }

    static long randomEmoteDelayTicks() {
        return java.util.concurrent.ThreadLocalRandom.current()
            .nextLong(EMOTE_MIN_DELAY_TICKS, EMOTE_MAX_DELAY_TICKS + 1L);
    }

    private static int nextRandomEmoteIndex(int previousIndex) {
        int n = MELLSTROY_EMOTES.length;
        if (n <= 1) return 0;
        int pick = java.util.concurrent.ThreadLocalRandom.current().nextInt(n - 1);
        if (previousIndex >= 0 && pick >= previousIndex) pick++;
        return pick;
    }

    private static Location computeShoulderSoundLocation(Location base, float bodyYaw) {
        if (base == null) return null;
        double rad = Math.toRadians(bodyYaw);
        double sin = Math.sin(rad);
        double cos = Math.cos(rad);
        double left = 0.55D;
        double fwd = 0.03D;
        double dx = left * cos - fwd * sin;
        double dz = left * sin + fwd * cos;
        return new Location(base.getWorld(), base.getX() + dx, base.getY() + 1.65D, base.getZ() + dz, 0.0F, 0.0F);
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private static void playMellstroyVoiceSound(Player wearer, float bodyYaw, String soundKey) {
        try {
            Location soundLoc = computeShoulderSoundLocation(wearer.getLocation(), bodyYaw);
            if (soundLoc == null) return;
            World world = soundLoc.getWorld();
            if (world == null) return;
            try {
                Class<? extends Enum> catEnum = (Class<? extends Enum>) Class.forName("org.bukkit.SoundCategory");
                Object playersCat = Enum.valueOf(catEnum, "PLAYERS");
                java.lang.reflect.Method playCat = world.getClass().getMethod(
                    "playSound", Location.class, String.class, catEnum, float.class, float.class);
                playCat.invoke(world, soundLoc, soundKey, playersCat, Float.valueOf(1.0F), Float.valueOf(1.0F));
                return;
            } catch (Throwable ignored) {
            }
            world.playSound(soundLoc, soundKey, 1.0F, 1.0F);
        } catch (Throwable ignored) {
        }
    }

    private static void triggerMellstroyEmote(Player wearer, GhoulRig rig, float bodyYaw, int forcedIndex) {
        if (wearer == null || rig == null || !MELLSTROY_BLUEPRINT.equals(rig.blueprintId)) return;
        int idx = (forcedIndex >= 0 && forcedIndex < MELLSTROY_EMOTES.length)
            ? forcedIndex
            : nextRandomEmoteIndex(rig.lastEmoteIndex);
        String animId = MELLSTROY_EMOTES[idx][0];
        String soundKey = MELLSTROY_EMOTES[idx][1];
        rig.lastEmoteIndex = idx;
        rig.lastEmoteAnim = animId;
        rig.lastEmoteSound = soundKey;
        rig.nextEmoteTick = petTicks + randomEmoteDelayTicks();

        AnimationHandler handler = rig.model.isDestroyed() ? null : rig.model.getAnimationHandler();
        if (handler != null) {
            for (String[] pair : MELLSTROY_EMOTES) {
                if (!pair[0].equals(animId) && handler.isPlayingAnimation(pair[0])) {
                    handler.forceStopAnimation(pair[0]);
                }
            }
            handler.playAnimation(animId, 0.10D, 0.15D, 1.0D, true);
        }
        playMellstroyVoiceSound(wearer, bodyYaw, soundKey);
    }

    private static void tickMellstroyEmote(Player wearer, GhoulRig rig, float bodyYaw) {
        if (petTicks >= rig.nextEmoteTick) {
            triggerMellstroyEmote(wearer, rig, bodyYaw, -1);
        }
    }

    private static void logRigReady(GhoulRig rig) {
        if (rig.loggedReady || !rig.attached) return;
        rig.loggedReady = true;
        if (host == null) return;
        String label = KANEKI_BLUEPRINT.equals(rig.blueprintId)
            ? "кагуне Канэки Кена"
            : MINI_ME_BLUEPRINT.equals(rig.blueprintId)
                ? "танцующая Мини-Роузи у плеча"
                : KITTEN_BLUEPRINT.equals(rig.blueprintId)
                    ? "милый котёнок на плече"
                    : MELLSTROY_BLUEPRINT.equals(rig.blueprintId)
                        ? "Меллстрой на плече (3D-анимации и озвучка)"
                        : "сколопендра (по всему телу)";
        host.getLogger().info("[Аксессуары] " + label + ": живая анимация '" + IDLE_ANIM
            + "', привязка к PivotOverride активна");
    }

    static ModelBlueprint resolveBlueprint(String blueprintId) {
        if (blueprintId == null || blueprintId.isEmpty()) return null;
        ModelBlueprint existing = ModelEngineAPI.getBlueprint(blueprintId);
        if (existing != null) return existing;
        try {
            java.lang.reflect.Method getApi = ModelEngineAPI.class.getMethod("getAPI");
            Object api = getApi.invoke(null);
            if (api == null) return null;
            Object generator = api.getClass().getMethod("getModelGenerator").invoke(api);
            Object registry = api.getClass().getMethod("getModelRegistry").invoke(api);
            if (generator == null || registry == null) return null;

            java.io.File dataFolder = (java.io.File) api.getClass().getMethod("getDataFolder").invoke(api);
            java.io.File bbFile = dataFolder != null
                ? new java.io.File(new java.io.File(dataFolder, "blueprints"), blueprintId + ".bbmodel")
                : new java.io.File("plugins/ModelEngine/blueprints/" + blueprintId + ".bbmodel");
            if (!bbFile.isFile()) {
                bbFile = new java.io.File("plugins/ModelEngine/blueprints/" + blueprintId + ".bbmodel");
            }
            if (!bbFile.isFile()) return null;

            for (java.lang.reflect.Method m : generator.getClass().getDeclaredMethods()) {
                Class<?>[] pt = m.getParameterTypes();
                if (m.getReturnType() == void.class && pt.length == 2
                        && pt[0] == java.io.File.class
                        && pt[1].isAssignableFrom(registry.getClass())) {
                    m.setAccessible(true);
                    m.invoke(generator, bbFile, registry);
                    break;
                }
            }
            ModelBlueprint loaded = ModelEngineAPI.getBlueprint(blueprintId);
            if (loaded != null && host != null) {
                host.getLogger().info("[Аксессуары] Авто-догружена модель из blueprints: " + blueprintId);
            }
            return loaded;
        } catch (Throwable ignored) {
            return ModelEngineAPI.getBlueprint(blueprintId);
        }
    }

    private static GhoulRig spawnRig(Player player, String blueprintId) {
        ModelBlueprint blueprint = resolveBlueprint(blueprintId);
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
        if (desiredPetBlueprint(player) != null || kanekiSelected(player)) {
            TELEPORT_RESPAWN_AT.put(uuid, Long.valueOf(petTicks + Math.max(1L, delayTicks)));
        }
    }

    static void logLoadedModels() {
        if (modelsLogged || host == null || petTicks < 60L) return;
        modelsLogged = true;
        StringBuilder missing = new StringBuilder();
        for (String id : new String[] {"elytrix_angel_wings", "elytrix_angel_halo",
                                       KANEKI_BLUEPRINT, CENTIPEDE_BLUEPRINT, MINI_ME_BLUEPRINT,
                                       KITTEN_BLUEPRINT, MELLSTROY_BLUEPRINT,
                                       "elytrix_priora_black", "elytrix_priora_white", "elytrix_priora_pink"}) {
            if (resolveBlueprint(id) == null && !id.startsWith("elytrix_priora_")) {
                if (missing.length() > 0) missing.append(", ");
                missing.append(id);
            }
        }
        try {
            if (missing.length() == 0) {
                host.getLogger().info("[Аксессуары] ModelEngine загрузил все модели: крылья, нимб, кагуне Канэки, сколопендра, Мини-Роузи, котёнок, Меллстрой");
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

    // ------------------------------------------------------------------ 3-section menu (Спина, Шапки, Питомцы)

    private static final class Holder implements InventoryHolder {
        final Section section;
        private Inventory inventory;

        Holder(Section section) {
            this.section = section;
        }

        @Override public Inventory getInventory() { return inventory; }
    }

    private static ItemStack item(Material mat, String title, String model, Integer cmd, String... lore) {
        ItemStack result = new ItemStack(mat);
        ItemMeta meta = result.getItemMeta();
        if (meta != null) {
            meta.setDisplayName(title);
            meta.setLore(java.util.Arrays.asList(lore));
            if (model != null) meta.setItemModel(new NamespacedKey("reallyworld", model));
            if (cmd != null) meta.setCustomModelData(cmd);
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

    private static String activeBackLabel(Player player, boolean allowed) {
        if (!allowed) return "§8Недоступно";
        String back = get(player, BACK);
        if ("wings".equals(back)) return "§dАнгельские крылья";
        if ("kaneki".equals(back)) return "§dЩупальца Канэки";
        return "§8Не выбрано";
    }

    private static String activeHatLabel(Player player, boolean allowed) {
        if (!allowed) return "§8Недоступно";
        return "halo".equals(headChoice(player)) ? "§dБожественный нимб" : "§8Не выбрано";
    }

    private static String activePetLabel(Player player, boolean allowed) {
        if (!allowed) return "§8Недоступно";
        String pet = petChoice(player);
        if (PET_MINI_ME.equals(pet)) return "§dМини-Роузи";
        if (PET_KITTEN.equals(pet)) return "§dМилый котёнок";
        if (PET_MELLSTROY.equals(pet)) return "§dМеллстрой";
        if (PET_CENTIPEDE.equals(pet)) return "§dСколопендра Гуля";
        return "§8Не выбрано";
    }

    private static void placeSectionTabs(Inventory menu, Player player, boolean allowed, Section current) {
        String openHint = "§a● Открыт раздел";
        String switchHint = "§x§F§8§B§E§F§BНажми, чтобы перейти";
        menu.setItem(12, item(Material.FEATHER, "§x§F§A§D§8§F§C§lСпина", "angel_wings", null,
            lore(current == Section.BACK ? openHint : switchHint,
                "§7Крылья и кагуне на спину",
                "§7Надето: " + activeBackLabel(player, allowed))));
        menu.setItem(13, item(Material.NETHER_STAR, "§x§F§A§D§8§F§C§lШапки", "angel_halo", null,
            lore(current == Section.HATS ? openHint : switchHint,
                "§7Нимбы и украшения на голову",
                "§7Надето: " + activeHatLabel(player, allowed))));
        menu.setItem(14, item(Material.WHITE_DYE, "§x§F§A§D§8§F§C§lПитомцы", "mini_me_icon", null,
            lore(current == Section.PETS ? openHint : switchHint,
                "§7Мини-Роузи, Меллстрой, котёнок и спутники",
                "§7Надето: " + activePetLabel(player, allowed))));
    }

    private static void placeBackAndClear(Inventory menu, boolean includeBackArrow) {
        if (includeBackArrow) {
            menu.setItem(45, item(Material.ARROW, "§x§F§8§B§E§F§BНазад", null, Integer.valueOf(BACK_ARROW_CMD),
                lore("§dНажми, чтобы вернуться", "§7Возврат к разделам аксессуаров")));
        }
        menu.setItem(49, item(Material.BARRIER, "§cСнять всё", null, null,
            lore("§dНажми, чтобы снять", "§7Убирает все надетые аксессуары")));
    }

    static void openMenu(Player player) {
        openMenu(player, Section.HUB);
    }

    static void openMenu(Player player, Section section) {
        Section target = section == null ? Section.HUB : section;
        String title = target == Section.BACK ? TITLE_BACK
            : target == Section.HATS ? TITLE_HATS
            : target == Section.PETS ? TITLE_PETS
            : TITLE_HUB;
        Holder holder = new Holder(target);
        Inventory menu = Bukkit.createInventory(holder, 54, title);
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
        String openSectionHint = "§x§F§8§B§E§F§BНажми, чтобы открыть раздел";

        if (target == Section.HUB) {
            menu.setItem(20, item(Material.FEATHER, "§x§F§A§D§8§F§C§lСпина", "angel_wings", null,
                lore(openSectionHint,
                    "§7Крылья и кагуне на спину",
                    "§7Надето: " + activeBackLabel(player, allowed),
                    "")));
            menu.setItem(22, item(Material.NETHER_STAR, "§x§F§A§D§8§F§C§lШапки", "angel_halo", null,
                lore(openSectionHint,
                    "§7Нимбы и украшения на голову",
                    "§7Надето: " + activeHatLabel(player, allowed),
                    "")));
            menu.setItem(24, item(Material.WHITE_DYE, "§x§F§A§D§8§F§C§lПитомцы", "mini_me_icon", null,
                lore(openSectionHint,
                    "§7Мини-Роузи, Меллстрой, котёнок и спутники",
                    "§7Надето: " + activePetLabel(player, allowed),
                    "")));
            placeBackAndClear(menu, false);
        } else if (target == Section.BACK) {
            placeSectionTabs(menu, player, allowed, Section.BACK);
            String back = get(player, BACK);
            boolean wings = allowed && "wings".equals(back);
            boolean kagune = allowed && "kaneki".equals(back);
            menu.setItem(30, item(Material.FEATHER, "§x§F§A§D§8§F§C§lАнгельские крылья", "angel_wings", null,
                wings ? lore(chosen, "§7Аксессуар для спины", "§7Не занимает слот брони", "§7Нажми ещё раз — снять")
                      : lore(hint, "§7Аксессуар для спины", "§7Не занимает слот брони")));
            menu.setItem(32, item(Material.RED_DYE, "§x§F§A§D§8§F§C§lЩупальца Канэки", "kaneki_tentacles_icon", null,
                kagune ? lore(chosen, "§7Кагуне Ринкаку Канэки Кена (Токийский Гуль)", "§74 живых алых хвоста из какухо на спине", "§7Нажми ещё раз — снять")
                       : lore(hint, "§7Кагуне Ринкаку Канэки Кена (Токийский Гуль)", "§74 живых алых хвоста из какухо на спине")));
            placeBackAndClear(menu, true);
        } else if (target == Section.HATS) {
            placeSectionTabs(menu, player, allowed, Section.HATS);
            boolean halo = allowed && "halo".equals(headChoice(player));
            menu.setItem(31, item(Material.NETHER_STAR, "§x§F§A§D§8§F§C§lБожественный нимб", "angel_halo", null,
                halo ? lore(chosen, "§7Нимб на голову", "§7Нажми ещё раз — снять")
                     : lore(hint, "§7Нимб на голову")));
            placeBackAndClear(menu, true);
        } else if (target == Section.PETS) {
            placeSectionTabs(menu, player, allowed, Section.PETS);
            String pet = petChoice(player);
            boolean miniMe = allowed && PET_MINI_ME.equals(pet);
            boolean kitten = allowed && PET_KITTEN.equals(pet);
            boolean mellstroy = allowed && PET_MELLSTROY.equals(pet);
            boolean bug = allowed && PET_CENTIPEDE.equals(pet);
            menu.setItem(28, item(Material.WHITE_DYE, "§x§F§A§D§8§F§C§lМини-Роузи", "mini_me_icon", null,
                miniMe ? lore(chosen, "§7Маленькая копия Роузи возле плеча", "§7Зажигательно танцует рядом с тобой", "§7Нажми ещё раз — снять")
                       : lore(hint, "§7Маленькая копия Роузи возле плеча", "§7Зажигательно танцует рядом с тобой")));
            menu.setItem(30, item(Material.PINK_DYE, "§x§F§A§D§8§F§C§lМилый котёнок", "kitten_icon", null,
                kitten ? lore(chosen, "§7Пушистый котёнок сидит прямо на плече", "§7Наклоняет головку и машет лапкой", "§7Нажми ещё раз — снять")
                       : lore(hint, "§7Пушистый котёнок сидит прямо на плече", "§7Наклоняет головку и машет лапкой")));
            menu.setItem(32, item(Material.GOLD_INGOT, "§x§F§A§D§8§F§C§lМеллстрой", "mellstroy_icon", null,
                mellstroy ? lore(chosen, "§7Мини-Меллстрой в кепке Rolex и цепи", "§73D-анимации фраз и настоящая озвучка!", "§7Нажми ещё раз — снять")
                          : lore(hint, "§7Мини-Меллстрой в кепке Rolex и цепи", "§73D-анимации фраз и настоящая озвучка!")));
            menu.setItem(34, item(Material.SPIDER_EYE, "§x§F§A§D§8§F§C§lСколопендра Гуля", "centipede_icon", null,
                bug ? lore(chosen, "§7Живая сколопендра ползает по всему телу", "§7Грудь, плечи, шея, спина, руки и бёдра", "§7Нажми ещё раз — снять")
                    : lore(hint, "§7Живая сколопендра ползает по всему телу", "§7Грудь, плечи, шея, спина, руки и бёдра")));
            placeBackAndClear(menu, true);
        }

        player.openInventory(menu);
    }

    private static Section parseSectionArg(String[] args) {
        if (args == null || args.length == 0 || args[0] == null) return Section.HUB;
        String key = args[0].trim().toLowerCase(Locale.ROOT);
        if (key.equals("спина") || key.equals("back")) return Section.BACK;
        if (key.equals("шапки") || key.equals("шапка") || key.equals("hats") || key.equals("head")) return Section.HATS;
        if (key.equals("питомцы") || key.equals("питомец") || key.equals("pets") || key.equals("pet")) return Section.PETS;
        return Section.HUB;
    }

    @Override public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) { sender.sendMessage("Только для игроков."); return true; }
        grantDonationAccess();
        try {
            openMenu(player, parseSectionArg(args));
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
        if (!(event.getView().getTopInventory().getHolder() instanceof Holder holder)) return;
        event.setCancelled(true);
        if (!(event.getWhoClicked() instanceof Player player)) return;
        int slot = event.getRawSlot();
        Section current = holder.section;

        // Navigation clicks (open to everyone so players can browse all 3 sections!)
        if (current == Section.HUB) {
            if (slot == 20) { openMenu(player, Section.BACK); return; }
            if (slot == 22) { openMenu(player, Section.HATS); return; }
            if (slot == 24) { openMenu(player, Section.PETS); return; }
        } else {
            if (slot == 45) { openMenu(player, Section.HUB); return; }
            if (slot == 12) { openMenu(player, Section.BACK); return; }
            if (slot == 13) { openMenu(player, Section.HATS); return; }
            if (slot == 14) { openMenu(player, Section.PETS); return; }
        }

        // Action clicks require permission
        boolean isActionSlot = (slot == 49)
            || (current == Section.BACK && (slot == 30 || slot == 32))
            || (current == Section.HATS && slot == 31)
            || (current == Section.PETS && (slot == 28 || slot == 30 || slot == 32 || slot == 34));
        if (!isActionSlot) return;

        if (!allowed(player)) {
            player.sendMessage("§cАксессуары доступны с доната §d" + MEDIA_GROUP + "§c.");
            return;
        }

        if (slot == 49) {
            set(player, BACK, "");
            setHead(player, "");
            set(player, PET, "");
            TELEPORT_RESPAWN_AT.remove(player.getUniqueId());
            releaseByUuid(player.getUniqueId());
            player.sendMessage("§7Все аксессуары сняты.");
            openMenu(player, current);
            return;
        }

        String requiredBlueprint = null;
        if (current == Section.BACK && slot == 30) requiredBlueprint = "elytrix_angel_wings";
        else if (current == Section.BACK && slot == 32) requiredBlueprint = KANEKI_BLUEPRINT;
        else if (current == Section.HATS && slot == 31) requiredBlueprint = "elytrix_angel_halo";
        else if (current == Section.PETS && slot == 28) requiredBlueprint = MINI_ME_BLUEPRINT;
        else if (current == Section.PETS && slot == 30) requiredBlueprint = KITTEN_BLUEPRINT;
        else if (current == Section.PETS && slot == 32) requiredBlueprint = MELLSTROY_BLUEPRINT;
        else if (current == Section.PETS && slot == 34) requiredBlueprint = CENTIPEDE_BLUEPRINT;

        if (requiredBlueprint != null && resolveBlueprint(requiredBlueprint) == null) {
            player.sendMessage("§cМодель ещё не загружена. Обратитесь к администрации.");
            return;
        }

        if (current == Section.BACK && slot == 30) {
            toggleWings(player);
        } else if (current == Section.BACK && slot == 32) {
            toggleKaneki(player);
        } else if (current == Section.HATS && slot == 31) {
            toggleHead(player, "halo", "Нимб", "надет", "снят");
        } else if (current == Section.PETS && slot == 28) {
            togglePetChoice(player, PET_MINI_ME, MINI_ME_BLUEPRINT,
                "Мини-Роузи",
                "§dМини-Роузи вызвана и танцует возле плеча!",
                "§7Мини-Роузи убрана.");
        } else if (current == Section.PETS && slot == 30) {
            togglePetChoice(player, PET_KITTEN, KITTEN_BLUEPRINT,
                "Милый котёнок",
                "§dМилый котёнок уютно устроился на плече!",
                "§7Милый котёнок убран.");
        } else if (current == Section.PETS && slot == 32) {
            togglePetChoice(player, PET_MELLSTROY, MELLSTROY_BLUEPRINT,
                "Меллстрой",
                "§dМеллстрой выскочил на плечо и готов зажигать!",
                "§7Меллстрой убран.");
        } else if (current == Section.PETS && slot == 34) {
            togglePetChoice(player, PET_CENTIPEDE, CENTIPEDE_BLUEPRINT,
                "Сколопендра",
                "§dСколопендра Гуля выпущена и ползает по всему телу.",
                "§7Сколопендра снята.");
        }
        openMenu(player, current);
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
        if (resolveBlueprint(KANEKI_BLUEPRINT) == null) {
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

    private static void togglePetChoice(Player player, String choice, String blueprintId,
                                        String shortName, String equippedMsg, String removedMsg) {
        if (petChoice(player).equals(choice)) {
            set(player, PET, "");
            GhoulRig pet = PETS.get(player.getUniqueId());
            if (pet != null) removeRig(player.getUniqueId(), pet, PETS);
            player.sendMessage(removedMsg);
            return;
        }
        if (resolveBlueprint(blueprintId) == null) {
            player.sendMessage("§cМодель (" + shortName + ") ещё не загружена. Обратитесь к администрации.");
            return;
        }
        set(player, PET, choice);
        TELEPORT_RESPAWN_AT.remove(player.getUniqueId());
        try {
            syncPlayerRigs(player);
        } catch (Throwable failure) {
            reportOnce(shortName, failure);
            set(player, PET, "");
            player.sendMessage("§c" + shortName + " не появился: " + failure.getClass().getSimpleName());
            return;
        }
        boolean spawned = PET_MINI_ME.equals(choice) ? wearingMiniMe(player)
            : PET_KITTEN.equals(choice) ? wearingKitten(player)
            : PET_MELLSTROY.equals(choice) ? wearingMellstroy(player)
            : wearingCentipede(player);
        if (!spawned) {
            set(player, PET, "");
            player.sendMessage("§c" + shortName + " не появился: модель не загрузилась.");
            return;
        }
        player.sendMessage(equippedMsg);
        if (PET_MELLSTROY.equals(choice)) {
            GhoulRig rig = PETS.get(player.getUniqueId());
            if (rig != null) {
                triggerMellstroyEmote(player, rig, trackerFor(player).getBodyYaw(), 0);
            }
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
