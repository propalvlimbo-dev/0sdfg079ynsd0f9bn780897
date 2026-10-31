package pw.elytrix.freakmodel;

import com.ticxo.modelengine.api.ModelEngineAPI;
import com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint;
import com.ticxo.modelengine.api.model.ActiveModel;
import com.ticxo.modelengine.api.model.ModeledEntity;
import com.ticxo.modelengine.api.model.PivotOverride;
import com.ticxo.modelengine.api.model.PivotOverrideRegistry;
import com.ticxo.modelengine.api.model.bone.ManualAnimator;
import com.ticxo.modelengine.api.model.bone.ModelBone;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.PluginCommand;
import org.bukkit.entity.Entity;
import org.bukkit.entity.ItemDisplay;
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
 * Server-side accessories menu: wings, halo, kagune and Kaneki's mask.
 *
 * <p>The mask is a real ModelEngine mesh on the head (21 cubes), not an armour
 * layer: it never touches the helmet slot, and the blueprint's root bone is
 * named {@code h_mask}, the prefix ModelEngine reads as the HEAD behaviour, so
 * the whole mask turns with the head yaw and pitch.
 */
public final class AccessoryController implements CommandExecutor, Listener {
    static final NamespacedKey BACK = new NamespacedKey("elytrixaccessories", "back");
    static final NamespacedKey HALO = new NamespacedKey("elytrixaccessories", "halo");
    /** Head slot: "halo" or "mask".  HALO is kept as the legacy spelling. */
    static final NamespacedKey HEAD = new NamespacedKey("elytrixaccessories", "head");
    /** Marker of the v23 armour patch: it is retired and cleaned off the head. */
    static final NamespacedKey LEGACY_PATCH_ITEM = new NamespacedKey("elytrixaccessories", "eyepatch_item");
    /** Blueprint of the 3D mask (plugins/ModelEngine/blueprints/elytrix_kaneki_mask.bbmodel). */
    static final String MASK_CHOICE = "mask";
    static final String MASK_BLUEPRINT = "elytrix_kaneki_mask";
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
    private static final java.util.Map<java.util.UUID, ActiveModel> MASKS = new java.util.HashMap<>();
    private static final java.util.Map<java.util.UUID, ActiveModel> PETS = new java.util.HashMap<>();
    /** Players whose pet bones already carry the crawl animator. */
    private static final java.util.Set<java.util.UUID> PET_ANIMATED = new java.util.HashSet<>();
    /** Shared clock of the crawl wave, advanced once per server tick. */
    static double crawlPhase;
    private AccessoryController() {}
    private static FreakModelSpec cachedTentacles;

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
            // Маска живёт отдельно от рига крыльев: свой такт, чтобы её можно было
            // надеть и снять, даже когда на спине и на голове ничего нет.
            Bukkit.getScheduler().runTaskTimer(plugin, AccessoryController::tickAll, 40L, 5L);
            // Every tick only for the wave clock: without it the centipede freezes.
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

    /** Staff, or the donation rank (the permission that {@link #grantDonationAccess} sets). */
    static boolean allowed(Player player) {
        return player.hasPermission("elytrixaccessories.admin") || player.hasPermission(USE_PERMISSION);
    }

    private static String get(Player p, NamespacedKey k) {
        String v = p.getPersistentDataContainer().get(k, PersistentDataType.STRING);
        return v == null ? "" : v;
    }

    private static void set(Player p, NamespacedKey k, String v) {
        PersistentDataContainer data = p.getPersistentDataContainer();
        if (v.isEmpty()) data.remove(k); else data.set(k, PersistentDataType.STRING, v);
    }

    /** What sits on the head right now: "halo", "mask" or "" (nothing). */
    static String headChoice(Player player) {
        String choice = get(player, HEAD);
        if (choice.isEmpty()) choice = get(player, HALO);
        // v23 stored the flat armour patch under this name; it is the same mask now
        return choice.equals("eyepatch") ? MASK_CHOICE : choice;
    }

    /** Only the halo goes through the wing rig; the mask has its own model path. */
    public static FreakModelSpec halo(ElytrixFreakModelPlugin plugin, Player player) {
        if (!allowed(player)) return null;
        return headChoice(player).equals("halo") ? plugin.findModel("angel_halo") : null;
    }

    /** True when this player should be wearing Kaneki's 3D mask. */
    public static boolean maskSelected(Player player) {
        return allowed(player) && headChoice(player).equals(MASK_CHOICE);
    }

    /** True when this player should be followed by the centipede. */
    public static boolean centipedeSelected(Player player) {
        return allowed(player) && get(player, PET).equals(PET_CHOICE);
    }

    /** Test hook: is the centipede model alive for this player right now? */
    static boolean wearingCentipede(Player player) {
        ActiveModel model = PETS.get(player.getUniqueId());
        return model != null && !model.isDestroyed();
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

    /** Spawns or removes the pet and keeps the crawl animators attached. */
    static void syncPet(Player player) {
        if (player == null || !player.isOnline()) return;
        boolean want = centipedeSelected(player);
        ActiveModel model = PETS.get(player.getUniqueId());
        if (want && (model == null || model.isDestroyed())) {
            model = spawnPet(player);
            if (model != null) PETS.put(player.getUniqueId(), model);
        } else if (!want && model != null) {
            removePet(player, model);
            return;
        }
        if (want) attachCrawl(player.getUniqueId(), model);
    }

    /** Called every tick: moves the wave and fills in animators that were not ready yet. */
    static void animatePets() {
        crawlPhase += 0.27D;
        for (java.util.Map.Entry<java.util.UUID, ActiveModel> entry : PETS.entrySet()) {
            attachCrawl(entry.getKey(), entry.getValue());
        }
    }

    private static void attachCrawl(java.util.UUID id, ActiveModel model) {
        if (model == null || model.isDestroyed() || PET_ANIMATED.contains(id)) return;
        boolean root = hookBone(model, "body_root", new Crawl(0, false, true));
        boolean head = hookBone(model, "head", new Crawl(0, true, false));
        boolean body = true;
        for (int index = 1; index <= 9; index++) {
            body &= hookBone(model, "c" + index, new Crawl(index, false, false));
        }
        if (root && head && body) PET_ANIMATED.add(id);
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

    private static ActiveModel spawnPet(Player player) {
        ModelBlueprint blueprint = ModelEngineAPI.getBlueprint(CENTIPEDE_BLUEPRINT);
        if (blueprint == null) return null;
        ModeledEntity entity = ModelEngineAPI.getOrCreateModeledEntity(player);
        if (entity == null || entity.isDestroyed()) return null;
        ActiveModel model = ModelEngineAPI.createActiveModel(blueprint);
        if (model == null) return null;
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
        entity.addModel(model, false);   // same as the halo/wings rig: not a passenger model
        return model;
    }

    private static void removePet(Player player, ActiveModel model) {
        PETS.remove(player.getUniqueId());
        PET_ANIMATED.remove(player.getUniqueId());
        try {
            ModeledEntity entity = ModelEngineAPI.getModeledEntity(player);
            if (entity != null && !entity.isDestroyed()) entity.removeModel(CENTIPEDE_BLUEPRINT);
        } catch (Throwable ignored) {
            // destroyed below anyway
        }
        try {
            if (!model.isDestroyed()) model.destroy();
        } catch (Throwable ignored) {
            // already gone
        }
    }

    /** Test hook: is the 3D mask model alive for this player right now? */
    static boolean wearingMaskModel(Player player) {
        ActiveModel model = MASKS.get(player.getUniqueId());
        return model != null && !model.isDestroyed();
    }

    /** Spawns or removes the mask model so the world matches the stored choice. */
    static void syncMask(Player player) {
        if (player == null || !player.isOnline()) return;
        boolean want = maskSelected(player);
        ActiveModel model = MASKS.get(player.getUniqueId());
        if (want && (model == null || model.isDestroyed())) {
            model = spawnMask(player);
            if (model != null) MASKS.put(player.getUniqueId(), model);
        } else if (!want && model != null) {
            removeMask(player, model);
        }
        if (want) hideOwnMask(player);
        syncPet(player);
    }

    /** True once the start-up model report was written to the log. */
    private static boolean modelsLogged;

    /** Names every accessory blueprint ModelEngine actually loaded (once, at start-up). */
    static void logLoadedModels() {
        if (modelsLogged || host == null) return;
        modelsLogged = true;
        StringBuilder missing = new StringBuilder();
        for (String id : new String[] {"angel_wings", "angel_halo", "elytrix_kaneki_tentacles",
                                       MASK_BLUEPRINT, CENTIPEDE_BLUEPRINT}) {
            if (ModelEngineAPI.getBlueprint(id) == null) {
                if (missing.length() > 0) missing.append(", ");
                missing.append(id);
            }
        }
        try {
            if (missing.length() == 0) {
                host.getLogger().info("[Аксессуары] ModelEngine загрузил все модели: крылья, нимб, кагуне, маска, сороконожка");
            } else {
                host.getLogger().warning("[Аксессуары] ModelEngine не загрузил: " + missing
                    + " — проверь plugins/ModelEngine/blueprints и лог ModelEngine");
            }
        } catch (Throwable ignored) {
            // diagnostics must never break the game loop
        }
    }

    /** Keeps every masked player in sync; called every five ticks from install(). */
    static void tickAll() {
        try {
            logLoadedModels();
            for (Player player : Bukkit.getOnlinePlayers()) {
                try {
                    syncMask(player);
                } catch (Throwable failure) {
                    reportOnce("маска", failure);
                }
            }
        } catch (Throwable ignored) {
            // a broken model must never take the server tick down with it
        }
    }

    private static ActiveModel spawnMask(Player player) {
        ModelBlueprint blueprint = ModelEngineAPI.getBlueprint(MASK_BLUEPRINT);
        if (blueprint == null) return null;                 // blueprint not imported yet
        ModeledEntity entity = ModelEngineAPI.getOrCreateModeledEntity(player);
        if (entity == null || entity.isDestroyed()) return null;
        ActiveModel model = ModelEngineAPI.createActiveModel(blueprint);
        if (model == null) return null;
        // Same numbers the angel rig uses, so the mask is lit like the rest of the
        // accessories and never draws a hitbox, a shadow or a fire overlay.
        model.setBlockLight(2);
        model.setSkyLight(2);
        model.setCanHurt(false);
        model.setShadowVisible(false);
        model.setHitboxVisible(false);
        model.setLockPitch(true);
        model.setLockYaw(true);
        model.setViewRange(2.0F);
        PivotOverrideRegistry registry = ModelEngineAPI.getPivotOverrideRegistry();
        PivotOverride pivot = registry == null ? null : registry.getOrCreate(player);
        if (pivot != null) model.setPivotOverride(pivot);
        entity.addModel(model, false);   // same as the halo/wings rig: not a passenger model
        return model;
    }

    private static void removeMask(Player player, ActiveModel model) {
        MASKS.remove(player.getUniqueId());
        try {
            ModeledEntity entity = ModelEngineAPI.getModeledEntity(player);
            if (entity != null && !entity.isDestroyed()) entity.removeModel(MASK_BLUEPRINT);
        } catch (Throwable ignored) {
            // the model is destroyed below either way
        }
        try {
            if (!model.isDestroyed()) model.destroy();
        } catch (Throwable ignored) {
            // already gone
        }
    }

    /** Forgets a model of a player who logged out or died. */
    static void releaseMask(Player player) {
        ActiveModel model = MASKS.remove(player.getUniqueId());
        if (model != null && !model.isDestroyed()) {
            try {
                model.destroy();
            } catch (Throwable ignored) {
                // nothing else to do
            }
        }
    }

    /**
     * The mask sits two pixels in front of the eyes, i.e. right inside the
     * first-person camera.  ModelEngine spawns real ItemDisplay entities, so the
     * wearer simply gets those hidden — the first person view stays clear and
     * everybody else sees the mask normally.
     */
    private static void hideOwnMask(Player player) {
        if (host == null) return;
        org.bukkit.Location eye = player.getEyeLocation();
        if (eye == null || eye.getWorld() == null) return;
        try {
            for (Entity nearby : eye.getWorld().getNearbyEntities(eye, 0.62D, 0.34D, 0.62D)) {
                if (!(nearby instanceof ItemDisplay)) continue;
                if (nearby.getUniqueId().equals(player.getUniqueId())) continue;
                double dy = Math.abs(nearby.getLocation().getY() - eye.getY());
                if (dy > 0.34D) continue;                 // the halo ring and the wings are higher
                player.hideEntity(host, nearby);
            }
        } catch (Throwable ignored) {
            // an engine without real display entities simply keeps the mask visible
        }
    }

    /**
     * Takes the v23 armour patch off the head: it drew a flat white band over the
     * helmet slot, the exact thing this build replaces.
     */
    static void cleanupLegacyPatch(Player player) {
        ItemStack worn = player.getInventory().getHelmet();
        if (worn == null || worn.getType() == Material.AIR) return;
        ItemMeta meta = worn.getItemMeta();
        if (meta == null) return;
        if (meta.getPersistentDataContainer().get(LEGACY_PATCH_ITEM, PersistentDataType.STRING) != null) {
            player.getInventory().setHelmet(null);
        }
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
                cleanupLegacyPatch(player);
            } catch (Throwable failure) {
                reportOnce("снятие старой повязки", failure);
            }
            try {
                syncMask(player);
            } catch (Throwable failure) {
                reportOnce("маска", failure);
            }
        }
        String hint = allowed ? "§dНажми, чтобы выбрать" : "§cДоступно с доната §dmedia";
        String chosen = allowed ? "§a● Сейчас надето" : "§8● Недоступно";
        String back = get(player, BACK);
        String head = headChoice(player);
        boolean wings = back.equals("wings"), kagune = back.equals("kaneki");
        boolean halo = head.equals("halo"), mask = head.equals(MASK_CHOICE);
        menu.setItem(12, item(Material.FEATHER, "§x§F§A§D§8§F§C§lАнгельские крылья", "angel_wings",
            wings ? lore(chosen, "§7Аксессуар для спины", "§7Не занимает слот брони", "§7Нажми ещё раз — снять")
                  : lore(hint, "§7Аксессуар для спины", "§7Не занимает слот брони")));
        menu.setItem(13, item(Material.NETHER_STAR, "§x§F§A§D§8§F§C§lБожественный нимб", "angel_halo",
            halo ? lore(chosen, "§7Нимб на голову", "§7Нажми ещё раз — снять")
                 : lore(hint, "§7Нимб на голову")));
        menu.setItem(14, item(Material.RED_DYE, "§x§F§A§D§8§F§C§lЩупальца Канэки", "kaneki_tentacles_icon",
            kagune ? lore(chosen, "§7Анимированный аксессуар для спины", "§7Нажми ещё раз — снять")
                   : lore(hint, "§7Анимированный аксессуар для спины")));
        menu.setItem(15, item(Material.PAPER, "§x§F§A§D§8§F§C§lМаска Канэки", "kaneki_eyepatch_icon",
            mask ? lore(chosen, "§73D-маска на лицо", "§7Не занимает слот брони", "§7Нажми ещё раз — снять")
                 : lore(hint, "§73D-маска на лицо", "§7Не занимает слот брони")));
        boolean bug = allowed && get(player, PET).equals(PET_CHOICE);
        menu.setItem(16, item(Material.SPIDER_EYE, "§x§F§A§D§8§F§C§lСороконожка", null,
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
        openMenu(player);
        return true;
    }

    private static void setHead(Player player, String choice) {
        set(player, HEAD, choice);
        // a node written by the older build must not resurrect the halo on top
        set(player, HALO, "");
        // the halo and the mask both live on the head: only one may stay on
        if (!choice.equals(MASK_CHOICE)) {
            ActiveModel model = MASKS.get(player.getUniqueId());
            if (model != null) removeMask(player, model);
        }
    }

    private static void toggleMask(Player player) {
        if (headChoice(player).equals(MASK_CHOICE)) {
            setHead(player, "");
            player.sendMessage("§7Маска Канэки снята.");
            return;
        }
        if (ModelEngineAPI.getBlueprint(MASK_BLUEPRINT) == null) {
            player.sendMessage("§cМодель маски ещё не загружена. Обратитесь к администрации.");
            return;
        }
        setHead(player, MASK_CHOICE);
        try {
            syncMask(player);
        } catch (Throwable failure) {
            reportOnce("маска", failure);
            setHead(player, "");                 // never remember a mask that is not there
            player.sendMessage("§cМаска не наделась: " + failure.getClass().getSimpleName());
            return;
        }
        if (!wearingMaskModel(player)) {         // spawn refused quietly (no blueprint/entity)
            setHead(player, "");
            player.sendMessage("§cМаска не наделась: модель не загрузилась.");
            return;
        }
        player.sendMessage("§dМаска Канэки надета.");
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
            : slot == 14 ? "elytrix_kaneki_tentacles" : slot == 15 ? MASK_BLUEPRINT
            : slot == 16 ? CENTIPEDE_BLUEPRINT : null;
        if (blueprint != null && ModelEngineAPI.getBlueprint(blueprint) == null) {
            player.sendMessage("§cМодель ещё не загружена. Обратитесь к администрации."); return;
        }
        // one click wears it, the same click takes it off again
        if (slot == 12) { toggleBack(player, "wings", "Крылья"); }
        else if (slot == 14) { toggleBack(player, "kaneki", "Щупальца Канэки"); }
        else if (slot == 13) { toggleHead(player, "halo", "Нимб", "надет", "снят"); }
        else if (slot == 15) { toggleMask(player); }
        else if (slot == 16) { togglePet(player); }
        else if (slot == 49) {
            set(player, BACK, ""); setHead(player, "");
            ActiveModel model = MASKS.get(player.getUniqueId());
            if (model != null) removeMask(player, model);
            ActiveModel pet = PETS.get(player.getUniqueId());
            if (pet != null) removePet(player, pet);
            set(player, PET, "");
            player.sendMessage("§7Все аксессуары сняты.");
        } else return;
        openMenu(player);
    }

    private static void togglePet(Player player) {
        if (get(player, PET).equals(PET_CHOICE)) {
            set(player, PET, "");
            ActiveModel model = PETS.get(player.getUniqueId());
            if (model != null) removePet(player, model);
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
            ActiveModel model = MASKS.get(player.getUniqueId());
            if (model != null) removeMask(player, model);       // the halo wins the head
            player.sendMessage("§d" + name + " " + on + ".");
        }
    }

    @EventHandler public void onDrag(InventoryDragEvent event) {
        if (event.getView().getTopInventory().getHolder() instanceof Holder) event.setCancelled(true);
    }
}
