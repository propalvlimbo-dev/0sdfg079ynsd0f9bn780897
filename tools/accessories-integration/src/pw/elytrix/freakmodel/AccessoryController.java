package pw.elytrix.freakmodel;

import com.ticxo.modelengine.api.ModelEngineAPI;
import com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint;
import com.ticxo.modelengine.api.model.ActiveModel;
import com.ticxo.modelengine.api.model.ModeledEntity;
import com.ticxo.modelengine.api.model.PivotOverride;
import com.ticxo.modelengine.api.model.PivotOverrideRegistry;
import com.ticxo.modelengine.api.model.bone.ManualAnimator;
import com.ticxo.modelengine.api.model.bone.ModelBone;
import com.ticxo.modelengine.api.model.render.DisplayRenderer;
import com.ticxo.modelengine.api.model.render.ModelRenderer;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.PluginCommand;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;

/**
 * Server-side accessories menu: wings, halo, kagune and the flying centipede.
 *
 * <p>The centipede is a ModelEngine mesh that rides on the player: after the
 * model is added, its pivot entity has to be registered as a passenger of the
 * player's {@link PivotOverride}.  That single call is what makes the animal
 * follow the player at all — without it the model exists but is never moved, so
 * nothing is visible.  The registration is retried every tick, because the
 * renderer is only ready a moment after the model is added.
 */
public final class AccessoryController implements CommandExecutor, Listener {
    static final NamespacedKey BACK = new NamespacedKey("elytrixaccessories", "back");
    static final NamespacedKey HALO = new NamespacedKey("elytrixaccessories", "halo");
    /** Head slot: only "halo" lives here.  HALO is kept as the legacy spelling. */
    static final NamespacedKey HEAD = new NamespacedKey("elytrixaccessories", "head");
    /** Pet slot: "centipede" or "" (nothing).  The animal flies above the head. */
    static final NamespacedKey PET = new NamespacedKey("elytrixaccessories", "pet");
    static final String PET_CHOICE = "centipede";
    /** Blueprint of the flying centipede. */
    static final String CENTIPEDE_BLUEPRINT = "elytrix_centipede";
    /** Donation rank that is allowed to wear the accessories, besides the staff. */
    static final String MEDIA_GROUP = "media";
    static final String USE_PERMISSION = "elytrixaccessories.use";
    private static boolean mediaGranted;
    private static ElytrixFreakModelPlugin host;
    private static final java.util.Map<java.util.UUID, Pet> PETS = new java.util.HashMap<>();
    /** Players whose pet bones already carry the crawl animator. */
    private static final java.util.Set<java.util.UUID> PET_ANIMATED = new java.util.HashSet<>();
    /** Bones of the centipede blueprint that carry the crawl wave. */
    static final int PET_BONES = 11;
    /** Shared clock of the crawl wave, advanced once per server tick. */
    static double crawlPhase;
    private AccessoryController() {}
    private static FreakModelSpec cachedTentacles;

    /** One live pet: the model, the pivot it must ride, and whether that worked. */
    private static final class Pet {
        final ActiveModel model;
        final PivotOverride pivot;
        boolean attached;
        /** The ready line is written once per wearer, not every tick. */
        boolean loggedBones;
        Pet(ActiveModel model, PivotOverride pivot) {
            this.model = model;
            this.pivot = pivot;
        }
    }

    public static void install(ElytrixFreakModelPlugin plugin) {
        // Никогда не бросаем исключение из onEnable: если оно улетит, ядро выключит
        // весь ElytrixFreakModel, и вместе с меню умрут крылья, нимб и кагуне.
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
            // Питомец живёт отдельно от рига крыльев: свой такт, чтобы его можно
            // было надеть и снять, даже когда на спине и на голове ничего нет.
            Bukkit.getScheduler().runTaskTimer(plugin, AccessoryController::tickAll, 40L, 5L);
            // Every tick only for the crawl wave and the pivot attachment retry.
            Bukkit.getScheduler().runTaskTimer(plugin, AccessoryController::animatePets, 5L, 1L);
            grantDonationAccess();
        } catch (Throwable failure) {
            plugin.getLogger().warning("[Аксессуары] меню не подключилось: " + failure);
        }
    }

    /**
     * Donators of the «media» rank must be able to take the accessories, so the
     * node is written into LuckPerms once at start-up instead of asking the owner
     * to type the command.  Idempotent, and silently skipped without LuckPerms.
     */
    private static void grantDonationAccess() {
        if (mediaGranted) return;
        try {
            if (!Bukkit.getPluginManager().isPluginEnabled("LuckPerms")) return;
            // If LuckPerms is still enabling, its command does not exist yet and the
            // dispatch answers false: keep the flag down so the next menu open retries.
            if (!Bukkit.dispatchCommand(Bukkit.getConsoleSender(),
                "lp group " + MEDIA_GROUP + " permission set " + USE_PERMISSION + " true")) return;
            mediaGranted = true;
        } catch (Throwable ignored) {
            // no LuckPerms / different core API: the node can still be set by hand
        }
    }

    /** Staff, or the donation rank (the permission that {@link #grantDonationAccess} sets). */
    static boolean allowed(Player player) {
        return player.hasPermission("elytrixaccessories.admin") || player.hasPermission(USE_PERMISSION);
    }

    /** Accessories already reported, so a broken model logs once and not every tick. */
    private static final java.util.Set<String> REPORTED = new java.util.HashSet<>();

    /** Logs a broken accessory once per start-up, with the real cause for the owner. */
    static void reportOnce(String what, Throwable failure) {
        if (!REPORTED.add(what)) return;
        try {
            if (host != null) {
                host.getLogger().warning("[Аксессуары] " + what + " не работает: " + failure);
            }
        } catch (Throwable ignored) {
            // logging must never throw on top of the original failure
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

    /** What sits on the head right now: "halo" or "" (nothing). */
    static String headChoice(Player player) {
        String choice = get(player, HEAD);
        if (choice.isEmpty()) choice = get(player, HALO);
        // v23-v26 stored "mask"/"eyepatch" here; that accessory is gone for good
        return choice.equals("halo") ? choice : "";
    }

    /** Only the halo goes through the wing rig. */
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

    /**
     * The kagune has its own spec instead of a copy of the wings one. The worn
     * rig only reads the blueprint id, the scale and the interpolation, so an
     * explicit accessory spec keeps the tentacles from inheriting numbers that
     * were tuned for feathers (and from silently picking up a future wings tweak).
     */
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

    /** True when this player should be wearing the kagune. */
    public static boolean kanekiSelected(Player player) {
        return allowed(player) && get(player, BACK).equals("kaneki");
    }

    // ------------------------------------------------------------------ centipede

    /** True when this player should be followed by the centipede. */
    public static boolean centipedeSelected(Player player) {
        return allowed(player) && get(player, PET).equals(PET_CHOICE);
    }

    /** Test hook: is the centipede model alive for this player right now? */
    static boolean wearingCentipede(Player player) {
        Pet pet = PETS.get(player.getUniqueId());
        return pet != null && !pet.model.isDestroyed();
    }

    /** Test hook: did the model's pivot get registered as a passenger of the player? */
    static boolean centipedeAttached(Player player) {
        Pet pet = PETS.get(player.getUniqueId());
        return pet != null && pet.attached;
    }

    /** Test hook: the angles the crawl animator asks for at a given phase. */
    static float[] crawlAngles(int index, boolean head, boolean root, double phase) {
        double p = phase - index * 0.62D;
        if (root) return new float[] {0.0F, (float) (26.0D * Math.sin(phase * 0.17D)), 0.0F};
        if (head) return new float[] {(float) (7.0D * Math.sin(phase * 0.80D + 1.0D)),
            (float) (18.0D * Math.sin(phase * 0.55D)), 0.0F};
        return new float[] {(float) (4.0D * Math.sin(p * 0.5D)),
            (float) (15.0D * Math.sin(p)), (float) (5.0D * Math.sin(p + 1.1D))};
    }

    /** One bone of the animal: the head looks around, the body carries the wave. */
    private static final class Crawl implements ManualAnimator {
        private final int index;
        private final boolean head;
        private final boolean root;
        Crawl(int index, boolean head, boolean root) {
            this.index = index;
            this.head = head;
            this.root = root;
        }
        @Override public boolean applyBoneDefaultLocal() {
            return true;                       // keep the pivot the blueprint asks for
        }
        @Override public void animate(ModelBone bone) {
            float[] angles = crawlAngles(index, head, root, crawlPhase);
            float pitch = angles[0], yaw = angles[1], roll = angles[2];
            bone.getLocalTransform().mutateSafe(transform ->
                transform.mutateLeftEuler(vector -> vector.set(pitch, yaw, roll)));
        }
    }

    /**
     * Registers the model's pivot entity as a passenger of the player's pivot
     * override.  This is the step that actually makes a ModelEngine model ride on
     * an entity: without it the model is created, its bones exist, and nothing is
     * ever visible because the pivot never moves with the player.
     */
    static boolean attachPivotToPlayer(ActiveModel model, PivotOverride pivot) {
        if (model == null || model.isDestroyed() || pivot == null) return false;
        ModelRenderer renderer;
        try {
            renderer = model.getModelRenderer();
        } catch (Throwable failure) {
            reportOnce("питомец", failure);
            return false;
        }
        if (!(renderer instanceof DisplayRenderer)) return false;
        DisplayRenderer display = (DisplayRenderer) renderer;
        if (!display.isInitialized()) return false;      // ready a moment after addModel
        DisplayRenderer.Pivot pivotEntity = display.getPivot();
        if (pivotEntity == null) return false;
        int id = pivotEntity.getId();
        if (!pivot.getPassengers().contains(id)) pivot.addPassenger(id);
        pivot.getPassengers().markDirty();               // resends the passenger packet
        return true;
    }

    /** Spawns or removes the pet and keeps the crawl animators + pivot attachment. */
    static void syncPet(Player player) {
        if (player == null || !player.isOnline()) return;
        boolean want = centipedeSelected(player);
        Pet pet = PETS.get(player.getUniqueId());
        if (want && (pet == null || pet.model.isDestroyed())) {
            pet = spawnPet(player);
            if (pet != null) PETS.put(player.getUniqueId(), pet);
        } else if (!want && pet != null) {
            removePet(player, pet);
            return;
        }
        if (!want || pet == null) return;
        if (!pet.attached) pet.attached = attachPivotToPlayer(pet.model, pet.pivot);
        int bound = attachCrawl(player.getUniqueId(), pet.model);
        logPetReady(pet, bound);
    }

    /** Called every tick: moves the wave, attaches the pivot, rescues a dead model. */
    static void animatePets() {
        crawlPhase += 0.27D;
        if (PETS.isEmpty()) return;
        for (java.util.Map.Entry<java.util.UUID, Pet> entry : new java.util.ArrayList<>(PETS.entrySet())) {
            Pet pet = entry.getValue();
            try {
                if (pet.model.isDestroyed()) {
                    PETS.remove(entry.getKey());
                    PET_ANIMATED.remove(entry.getKey());
                    continue;
                }
                if (!pet.attached) pet.attached = attachPivotToPlayer(pet.model, pet.pivot);
                logPetReady(pet, attachCrawl(entry.getKey(), pet.model));
            } catch (Throwable failure) {
                reportOnce("питомец", failure);
            }
        }
    }

    /** Hooks the crawl wave onto every bone; returns how many of the 11 were found. */
    private static int attachCrawl(java.util.UUID id, ActiveModel model) {
        if (model == null || model.isDestroyed()) return 0;
        if (PET_ANIMATED.contains(id)) return PET_BONES;
        int bound = hookBone(model, "body_root", new Crawl(0, false, true)) ? 1 : 0;
        bound += hookBone(model, "head", new Crawl(0, true, false)) ? 1 : 0;
        for (int index = 1; index <= 9; index++) {
            bound += hookBone(model, "c" + index, new Crawl(index, false, false)) ? 1 : 0;
        }
        if (bound == PET_BONES) PET_ANIMATED.add(id);
        return bound;
    }

    /**
     * Writes one line per wearer once the animal is complete, so the log alone
     * answers «видно её или нет»: bones bound, and whether the pivot rides the
     * player.  A model with unbound bones still shows, but it will not crawl.
     */
    private static void logPetReady(Pet pet, int bound) {
        if (pet.loggedBones || bound < PET_BONES) return;
        pet.loggedBones = true;
        if (host == null) return;
        host.getLogger().info("[Аксессуары] сороконожка: кости " + bound + "/" + PET_BONES
            + ", " + (pet.attached ? "модель едет на игроке"
                                   : "pivot пока не прикрепился, повторяю каждый тик"));
    }

    private static boolean hookBone(ActiveModel model, String boneId, ManualAnimator animator) {
        try {
            java.util.Optional<ModelBone> bone = model.getBone(boneId);
            if (bone == null || bone.isEmpty()) return false;
            bone.get().setManualAnimator(animator);
            return true;
        } catch (Throwable ignored) {
            return false;
        }
    }

    private static Pet spawnPet(Player player) {
        ModelBlueprint blueprint = ModelEngineAPI.getBlueprint(CENTIPEDE_BLUEPRINT);
        if (blueprint == null) return null;
        ModeledEntity entity = ModelEngineAPI.getOrCreateModeledEntity(player);
        if (entity == null || entity.isDestroyed()) return null;
        ActiveModel model = ModelEngineAPI.createActiveModel(blueprint);
        if (model == null) return null;
        // Same numbers the angel rig uses, plus enough light for the animal to be
        // visible at night: it would otherwise be a black silhouette after dusk.
        model.setBlockLight(15);
        model.setSkyLight(15);
        model.setCanHurt(false);
        model.setShadowVisible(false);
        model.setHitboxVisible(false);
        model.setLockPitch(true);
        model.setLockYaw(true);
        model.setViewRange(3.0F);
        PivotOverrideRegistry registry = ModelEngineAPI.getPivotOverrideRegistry();
        PivotOverride pivot = registry == null ? null : registry.getOrCreate(player);
        if (pivot != null) model.setPivotOverride(pivot);
        entity.addModel(model, false);        // same as the halo/wings rig: not a passenger model
        // follow the player's facing instead of standing still towards world north
        model.setModelRotationLocked(false);
        Pet pet = new Pet(model, pivot);
        pet.attached = attachPivotToPlayer(model, pivot);
        return pet;
    }

    private static void removePet(Player player, Pet pet) {
        PETS.remove(player.getUniqueId());
        PET_ANIMATED.remove(player.getUniqueId());
        try {
            ModeledEntity entity = ModelEngineAPI.getModeledEntity(player);
            if (entity != null && !entity.isDestroyed()) entity.removeModel(CENTIPEDE_BLUEPRINT);
        } catch (Throwable ignored) {
            // destroyed below anyway
        }
        try {
            if (!pet.model.isDestroyed()) pet.model.destroy();
            if (pet.pivot != null && !pet.attached) pet.pivot.getPassengers().markDirty();
        } catch (Throwable ignored) {
            // already gone
        }
    }

    /** Forgets a pet of a player who logged out: the model must not leak. */
    static void releasePet(Player player) {
        Pet pet = PETS.remove(player.getUniqueId());
        PET_ANIMATED.remove(player.getUniqueId());
        if (pet == null) return;
        try {
            if (!pet.model.isDestroyed()) pet.model.destroy();
        } catch (Throwable ignored) {
            // nothing else to do
        }
    }

    /** True once the start-up model report was written to the log. */
    private static boolean modelsLogged;

    /** Names every accessory blueprint ModelEngine actually loaded (once, at start-up). */
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
                host.getLogger().info("[Аксессуары] ModelEngine загрузил все модели: крылья, нимб, кагуне, сороконожка");
            } else {
                host.getLogger().warning("[Аксессуары] ModelEngine не загрузил: " + missing
                    + " — проверь plugins/ModelEngine/blueprints и лог ModelEngine");
            }
        } catch (Throwable ignored) {
            // diagnostics must never break the game loop
        }
    }

    /** Keeps every pet in sync; called every five ticks from install(). */
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
            // a broken model must never take the server tick down with it
        }
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

    /** Rewrites the whole menu, so a click can flip a button and show the new state. */
    static void openMenu(Player player) {
        Holder holder = new Holder();
        // The same frame, slot overlay and spacing glyphs as DeluxeMenus /shop.
        // ꏠ is the dedicated "АКСЕССУАРЫ" title added to the resource pack.
        Inventory menu = Bukkit.createInventory(holder, 54, "§fꈁꀀꈂꌀꈂꀁ§fꈃꏠ");
        holder.inventory = menu;
        boolean allowed = allowed(player);
        if (allowed) {
            // An accessory failure must never take the whole menu down: that is
            // exactly how v3.6.0 answered /аксессуары with a command exception.
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
        menu.setItem(15, item(Material.SPIDER_EYE, "§x§F§A§D§8§F§C§lСороконожка", null,
            bug ? lore(chosen, "§7Живая сороконожка над головой", "§7Ползает и покачивается", "§7Нажми ещё раз — снять")
                : lore(hint, "§7Живая сороконожка над головой", "§7Ползает и покачивается")));
        // 49 — нижний ряд, середина: кнопка «Снять всё» в самом низу меню
        menu.setItem(49, item(Material.BARRIER, "§cСнять всё", null,
            lore("§dНажми, чтобы снять", "§7Убирает и спину, и голову")));
        player.openInventory(menu);
    }

    @Override public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) { sender.sendMessage("Только для игроков."); return true; }
        grantDonationAccess();          // LuckPerms is certainly up by the time a player opens this
        try {
            openMenu(player);
        } catch (Throwable failure) {
            // the command must answer, never explode in the server console
            reportOnce("меню", failure);
            player.sendMessage("§cМеню аксессуаров не открылось, причина записана в лог.");
        }
        return true;
    }

    private static void setHead(Player player, String choice) {
        set(player, HEAD, choice);
        // a node written by the older build must not resurrect the halo on top
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
        // one click wears it, the same click takes it off again
        if (slot == 12) { toggleBack(player, "wings", "Крылья"); }
        else if (slot == 14) { toggleBack(player, "kaneki", "Щупальца Канэки"); }
        else if (slot == 13) { toggleHead(player, "halo", "Нимб", "надет", "снят"); }
        else if (slot == 15) { togglePet(player); }
        else if (slot == 49) {
            set(player, BACK, ""); setHead(player, "");
            set(player, PET, "");
            Pet pet = PETS.get(player.getUniqueId());
            if (pet != null) removePet(player, pet);
            player.sendMessage("§7Все аксессуары сняты.");
        } else return;
        openMenu(player);
    }

    private static void togglePet(Player player) {
        if (get(player, PET).equals(PET_CHOICE)) {
            set(player, PET, "");
            Pet pet = PETS.get(player.getUniqueId());
            if (pet != null) removePet(player, pet);
            player.sendMessage("§7Сороконожка улетела.");
            return;
        }
        if (ModelEngineAPI.getBlueprint(CENTIPEDE_BLUEPRINT) == null) {
            player.sendMessage("§cМодель сороконожки ещё не загружена. Обратитесь к администрации.");
            return;
        }
        set(player, PET, PET_CHOICE);
        try {
            syncPet(player);
        } catch (Throwable failure) {
            reportOnce("сороконожка", failure);
            set(player, PET, "");
            player.sendMessage("§cСороконожка не приползла: " + failure.getClass().getSimpleName());
            return;
        }
        if (!wearingCentipede(player)) {
            set(player, PET, "");
            player.sendMessage("§cСороконожка не приползла: модель не загрузилась.");
            return;
        }
        player.sendMessage("§dСороконожка приползла.");
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
