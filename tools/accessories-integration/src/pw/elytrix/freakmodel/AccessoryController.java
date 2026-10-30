package pw.elytrix.freakmodel;

import com.ticxo.modelengine.api.ModelEngineAPI;
import com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint;
import com.ticxo.modelengine.api.model.ActiveModel;
import com.ticxo.modelengine.api.model.ModeledEntity;
import com.ticxo.modelengine.api.model.PivotOverride;
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

/** Experimental server-side cosmetic selection. Installed inside ElytrixFreakModel. */
public final class AccessoryController implements CommandExecutor, Listener {
    static final NamespacedKey BACK = new NamespacedKey("elytrixaccessories", "back");
    static final NamespacedKey HALO = new NamespacedKey("elytrixaccessories", "halo");
    /** Head slot: "halo" or "eyepatch".  HALO is kept as the legacy spelling. */
    static final NamespacedKey HEAD = new NamespacedKey("elytrixaccessories", "head");
    private AccessoryController() {}
    private static FreakModelSpec cachedBase;
    private static FreakModelSpec cachedTentacles;
    private static FreakModelSpec cachedPatch;
    private static final String PATCH_BLUEPRINT = "elytrix_kaneki_eyepatch";
    private static final java.util.Map<java.util.UUID, PatchRig> PATCHES = new java.util.HashMap<>();
    public static void install(ElytrixFreakModelPlugin plugin) {
        AccessoryController controller = new AccessoryController();
        PluginCommand command = plugin.getCommand("accessories");
        if (command == null) throw new IllegalStateException("Missing аксессуары command");
        command.setExecutor(controller);
        Bukkit.getPluginManager().registerEvents(controller, plugin);
    }
    private static boolean allowed(Player player) { return player.hasPermission("elytrixaccessories.admin"); }
    private static String get(Player p, NamespacedKey k) {
        String v = p.getPersistentDataContainer().get(k, PersistentDataType.STRING);
        return v == null ? "" : v;
    }
    private static void set(Player p, NamespacedKey k, String v) {
        PersistentDataContainer data = p.getPersistentDataContainer();
        if (v.isEmpty()) data.remove(k); else data.set(k, PersistentDataType.STRING, v);
    }
    /** What sits on the head right now: "halo", "eyepatch" or "" (nothing). */
    static String headChoice(Player player) {
        String choice = get(player, HEAD);
        // players who picked a halo before the head slot existed keep it
        return choice.isEmpty() ? get(player, HALO) : choice;
    }

    public static FreakModelSpec halo(ElytrixFreakModelPlugin plugin, Player player) {
        return allowed(player) && headChoice(player).equals("halo") ? plugin.findModel("angel_halo") : null;
    }

    /** True when this player should be wearing Kaneki's eyepatch. */
    public static boolean eyepatchSelected(Player player) {
        return allowed(player) && headChoice(player).equals("eyepatch");
    }

    /**
     * The eyepatch has its own spec, like the kagune: it is a head accessory and
     * must never inherit numbers tuned for the halo (scale, offsets, glow).
     */
    static FreakModelSpec eyepatch(ElytrixFreakModelPlugin plugin) {
        FreakModelSpec configured = plugin.findModel(PATCH_BLUEPRINT);
        if (configured != null) return configured;
        FreakModelSpec base = plugin.findModel("angel_halo");
        if (base == null) base = plugin.findModel("angel_wings");
        if (base == null) return null;
        if (cachedBase == base && cachedPatch != null) return cachedPatch;
        cachedBase = base;
        cachedPatch = new FreakModelSpec(PATCH_BLUEPRINT, base.kind, PATCH_BLUEPRINT,
            java.util.List.of(), org.bukkit.Material.WHITE_DYE, "kaneki_eyepatch_icon", 36,
            "Повязка Канэки", java.util.List.of(), 1.0F, 0.0F, 0.0D, 0.9F, 0.9F, 1, 0,
            0.0D, 0.0D, 0.0D, 0.0D, 0.0D, 0.0D, 0.0D, 0.0D, 0.0F, 0.0D, false, false);
        return cachedPatch;
    }

    /**
     * Keeps the eyepatch attached to the player.
     *
     * The halo and the kagune ride the WornAngelRig, which owns its own model
     * slots; the eyepatch adds a *second* model to the same ModeledEntity and
     * shares the player's pivot override.  That is the only way to wear the
     * patch together with the kagune, which is the whole Kaneki look, and it
     * cannot disturb the rig's own two slots.
     */
    public static void tickEyepatch(ElytrixFreakModelPlugin plugin, Player player) {
        java.util.UUID id = player.getUniqueId();
        if (!eyepatchSelected(player)) {
            PatchRig stale = PATCHES.remove(id);
            if (stale != null) stale.destroy();
            return;
        }
        PatchRig rig = PATCHES.get(id);
        if (rig == null) { rig = new PatchRig(); PATCHES.put(id, rig); }
        rig.sync(plugin, player);
    }

    /** One player's eyepatch model.  Dropped with the player's ModeledEntity. */
    static final class PatchRig {
        private ModeledEntity entity;
        private ActiveModel model;

        void destroy() {
            ModeledEntity owner = entity;
            ActiveModel attached = model;
            entity = null;
            model = null;
            try {
                if (owner != null && !owner.isDestroyed() && attached != null) owner.removeModel(PATCH_BLUEPRINT);
                if (attached != null && !attached.isDestroyed()) attached.destroy();
            } catch (RuntimeException ignored) {
                // the entity died before we got here: nothing is left to clean up
            }
        }

        void sync(ElytrixFreakModelPlugin plugin, Player player) {
            ModeledEntity current = ModelEngineAPI.getOrCreateModeledEntity(player);
            if (current == null || current.isDestroyed()) { model = null; entity = null; return; }
            if (model == null || model.isDestroyed() || entity != current) {
                entity = current;
                model = null;
                // a cosmetic must never hide the player underneath it
                current.setBaseEntityVisible(true);
                // a reload can leave the patch attached: adopt it instead of stacking a twin
                java.util.Optional<ActiveModel> existing = current.getModel(PATCH_BLUEPRINT);
                if (existing != null && existing.isPresent() && !existing.get().isDestroyed()) {
                    model = existing.get();
                } else {
                    ModelBlueprint blueprint = ModelEngineAPI.getBlueprint(PATCH_BLUEPRINT);
                    if (blueprint == null) return;
                    ActiveModel created = ModelEngineAPI.createActiveModel(blueprint);
                    if (created == null) return;
                    created.setCanHurt(false);
                    created.setShadowVisible(false);
                    created.setHitboxVisible(false);
                    created.setLockPitch(true);
                    created.setLockYaw(true);
                    created.setViewRange(64.0F);
                    PivotOverride pivot = ModelEngineAPI.getPivotOverrideRegistry() == null ? null
                        : ModelEngineAPI.getPivotOverrideRegistry().getOrCreate(player);
                    if (pivot != null) created.setPivotOverride(pivot);
                    // the same locking the rig uses for the halo: the model follows the
                    // player's body rotation instead of spinning on its own
                    created.setModelRotationLocked(Boolean.TRUE);
                    created.setLockedXHeadRot(0.0F);
                    created.setLockedYHeadRot(0.0F);
                    created.setLockedYBodyRot(0.0F);
                    java.util.Optional<ActiveModel> added = current.addModel(created, false);
                    model = added != null && added.isPresent() ? added.get() : created;
                }
            }
            // No yaw push here: the model hangs off the player's own ModeledEntity,
            // and ModelEngine reads the body rotation from the entity every tick.
            // (The halo rig has to push it by hand only because it rides a fake
            // attachment entity that has no rotation of its own.)
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
        if (cachedBase == base && cachedTentacles != null) return cachedTentacles;
        cachedBase = base;
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
        ItemStack result = new ItemStack(mat); ItemMeta meta = result.getItemMeta();
        if (meta != null) { meta.setDisplayName(title); meta.setLore(java.util.Arrays.asList(lore)); if (model != null) meta.setItemModel(new NamespacedKey("reallyworld", model)); result.setItemMeta(meta); }
        return result;
    }
    @Override public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) { sender.sendMessage("Только для игроков."); return true; }
        Holder holder = new Holder();
        // The same frame, slot overlay and spacing glyphs as DeluxeMenus /shop.
        // ꏠ is the dedicated "АКСЕССУАРЫ" title added to the resource pack.
        Inventory menu = Bukkit.createInventory(holder, 54, "§fꈁꀀꈂꌀꈂꀁ§fꈃꏠ"); holder.inventory=menu;
        String restriction = allowed(player) ? "§dНажми, чтобы выбрать" : "§cПока доступно только администрации";
        menu.setItem(12, item(Material.FEATHER, "§x§F§A§D§8§F§C§lАнгельские крылья", "angel_wings", "", "§7Аксессуар для спины", "§7Не занимает слот брони", "", restriction));
        menu.setItem(13, item(Material.NETHER_STAR, "§x§F§A§D§8§F§C§lБожественный нимб", "angel_halo", "", "§7Нимб можно носить вместе", "§7с аксессуаром для спины", "", restriction));
        menu.setItem(14, item(Material.RED_DYE, "§x§F§A§D§8§F§C§lЩупальца Канэки", "kaneki_tentacles_icon", "", "§7Анимированный аксессуар для спины", "§7Только внешний вид, без способностей", "", restriction));
        menu.setItem(15, item(Material.WHITE_DYE, "§x§F§A§D§8§F§C§lПовязка Канэки", "kaneki_eyepatch_icon", "", "§7Белая повязка на левый глаз", "§7Носится вместе с щупальцами", "", restriction));
        menu.setItem(30, item(Material.BARRIER, "§cСнять со спины", null, "", "§7Снять крылья или щупальца", "", restriction));
        menu.setItem(31, item(Material.ARROW, "§x§F§A§D§8§F§C§lНазад в меню", null, "", "§7Вернуться в главное меню", "", "§dНажми, чтобы открыть"));
        menu.setItem(32, item(Material.BARRIER, "§cСнять с головы", null, "", "§7Нимб или повязка — отдельно от спины", "", restriction));
        player.openInventory(menu); return true;
    }
    @EventHandler public void onClick(InventoryClickEvent event) {
        if (!(event.getView().getTopInventory().getHolder() instanceof Holder)) return;
        event.setCancelled(true);
        if (!(event.getWhoClicked() instanceof Player player)) return;
        int slot=event.getRawSlot();
        if (slot==31) { player.closeInventory(); player.performCommand("menu"); return; }
        if (!allowed(player)) { player.sendMessage("§cПока аксессуары доступны только администрации."); return; }
        String blueprint = slot==12 ? "elytrix_angel_wings" : slot==13 ? "elytrix_angel_halo"
            : slot==14 ? "elytrix_kaneki_tentacles" : slot==15 ? PATCH_BLUEPRINT : null;
        if (blueprint != null && ModelEngineAPI.getBlueprint(blueprint) == null) {
            player.sendMessage("§cМодель ещё не загружена. Обратитесь к администрации."); return;
        }
        if (slot==12) { set(player,BACK,"wings"); player.sendMessage("§dВыбраны крылья."); }
        else if (slot==13) { set(player,HEAD,"halo"); player.sendMessage("§eВыбран нимб."); }
        else if (slot==14) { set(player,BACK,"kaneki"); player.sendMessage("§cВыбраны щупальца Канэки."); }
        else if (slot==15) { set(player,HEAD,"eyepatch"); player.sendMessage("§fВыбрана повязка Канэки."); }
        else if (slot==30) { set(player,BACK,""); player.sendMessage("§7Аксессуар со спины снят."); }
        else if (slot==32) { set(player,HEAD,""); set(player,HALO,""); player.sendMessage("§7Голова свободна."); }
    }
    @EventHandler public void onDrag(InventoryDragEvent event) {
        if (event.getView().getTopInventory().getHolder() instanceof Holder) event.setCancelled(true);
    }
}
