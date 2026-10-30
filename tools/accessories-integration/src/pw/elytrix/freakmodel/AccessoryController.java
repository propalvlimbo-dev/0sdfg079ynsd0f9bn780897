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
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.PlayerInventory;
import org.bukkit.inventory.meta.components.EquippableComponent;
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
    private static FreakModelSpec cachedTentacles;
    /** Marks the real helmet-slot item that draws the patch on the head. */
    static final NamespacedKey EYEPATCH_ITEM = new NamespacedKey("elytrixaccessories", "eyepatch_item");
    /** Equipment asset (assets/reallyworld/equipment/kaneki_eyepatch.json). */
    private static final NamespacedKey EYEPATCH_ASSET = new NamespacedKey("reallyworld", "kaneki_eyepatch");
    private static final NamespacedKey EYEPATCH_ICON = new NamespacedKey("reallyworld", "kaneki_eyepatch_icon");
    /** Donation rank that is allowed to wear the accessories, besides the staff. */
    static final String MEDIA_GROUP = "media";
    static final String USE_PERMISSION = "elytrixaccessories.use";
    private static boolean mediaGranted;
    public static void install(ElytrixFreakModelPlugin plugin) {
        // Никогда не бросаем исключение из onEnable: если оно улетит, ядро выключит
        // весь ElytrixFreakModel, и вместе с меню умрут крылья, нимб и кагуне.
        // Ровно это и случилось на DivineMC: "/аксессуары -> plugin is disabled".
        try {
            AccessoryController controller = new AccessoryController();
            PluginCommand command = plugin.getCommand("accessories");
            if (command == null) {
                plugin.getLogger().warning("[Аксессуары] команда accessories не найдена в plugin.yml — меню не подключено");
            } else {
                command.setExecutor(controller);
            }
            Bukkit.getPluginManager().registerEvents(controller, plugin);
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

    /**
     * The head slot spec.  Only the halo is a ModelEngine model now: Kaneki's
     * patch is a real helmet-slot item whose armour layer the client draws as
     * part of the player model, which is the only way to keep it out of the
     * first-person view while still showing it in F5.
     */
    public static FreakModelSpec halo(ElytrixFreakModelPlugin plugin, Player player) {
        if (!allowed(player)) return null;
        String choice = headChoice(player);
        if (choice.equals("halo")) return plugin.findModel("angel_halo");
        return null;
    }

    /** True when this player should be wearing Kaneki's eyepatch. */
    public static boolean eyepatchSelected(Player player) {
        return allowed(player) && headChoice(player).equals("eyepatch");
    }

    /** The white patch as a wearable: a leather helmet with our own armour layer. */
    static ItemStack eyepatchItem() {
        ItemStack stack = new ItemStack(Material.LEATHER_HELMET);
        ItemMeta meta = stack.getItemMeta();
        if (meta != null) {
            meta.setDisplayName("\u00a7x\u00a7F\u00a7A\u00a7D\u00a78\u00a7F\u00a7C\u00a7lПовязка Канэки");
            meta.setLore(java.util.Arrays.asList("", "\u00a77Белая повязка на левый глаз",
                "\u00a77Надета поверх головы, снимается из меню"));
            meta.setItemModel(EYEPATCH_ICON);
            EquippableComponent equippable = meta.getEquippable();
            if (equippable != null) {
                equippable.setSlot(EquipmentSlot.HEAD);
                equippable.setModel(EYEPATCH_ASSET);
                meta.setEquippable(equippable);
            }
            meta.getPersistentDataContainer().set(EYEPATCH_ITEM, PersistentDataType.STRING, "kaneki");
            stack.setItemMeta(meta);
        }
        return stack;
    }

    /** True when the stack on the head is our patch. */
    static boolean isPatchItem(ItemStack stack) {
        if (stack == null || stack.getType() == Material.AIR) return false;
        ItemMeta meta = stack.getItemMeta();
        return meta != null && meta.getPersistentDataContainer().get(EYEPATCH_ITEM, PersistentDataType.STRING) != null;
    }

    /** True when the player is physically wearing the patch right now. */
    static boolean wearingPatch(Player player) {
        return isPatchItem(player.getInventory().getHelmet());
    }

    /**
     * Keeps the stored choice and the item in sync: a player who died, dropped
     * the patch or pulled it into a chest must not keep a stale "worn" flag.
     */
    static void syncEyepatch(Player player) {
        boolean worn = wearingPatch(player);
        if (worn && !headChoice(player).equals("eyepatch")) setHead(player, "eyepatch");
        else if (!worn && headChoice(player).equals("eyepatch")) setHead(player, "");
    }

    private static void togglePatch(Player player) {
        if (headChoice(player).equals("eyepatch") || wearingPatch(player)) {
            setHead(player, "");
            player.sendMessage("\u00a77Повязка Канэки снята.");
            return;
        }
        if (!putOnPatch(player)) return;
        setHead(player, "eyepatch");
        player.sendMessage("\u00a7dПовязка Канэки надета.");
    }

    private static boolean putOnPatch(Player player) {
        PlayerInventory inventory = player.getInventory();
        ItemStack worn = inventory.getHelmet();
        if (worn != null && worn.getType() != Material.AIR && !isPatchItem(worn)) {
            // a real helmet is in the way: move it to the inventory, never into the void
            if (inventory.firstEmpty() < 0) {
                player.sendMessage("\u00a7cНет свободного слота: освободи место, чтобы снять текущий шлем.");
                return false;
            }
            inventory.setHelmet(null);
            inventory.addItem(worn);
        }
        inventory.setHelmet(eyepatchItem());
        return true;
    }

    private static void takeOffPatch(Player player) {
        PlayerInventory inventory = player.getInventory();
        ItemStack worn = inventory.getHelmet();
        if (!isPatchItem(worn)) return;
        inventory.setHelmet(null);
        java.util.Map<Integer, ItemStack> left = inventory.addItem(worn);
        if (left != null && !left.isEmpty()) {
            inventory.setHelmet(left.values().iterator().next());
            player.sendMessage("\u00a7eИнвентарь полон — повязка осталась на голове.");
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
        return item(mat, title, model, null, lore);
    }
    private static ItemStack item(Material mat, String title, String model, Integer customModelData, String... lore) {
        ItemStack result = new ItemStack(mat); ItemMeta meta = result.getItemMeta();
        if (meta != null) {
            meta.setDisplayName(title);
            meta.setLore(java.util.Arrays.asList(lore));
            if (model != null) meta.setItemModel(new NamespacedKey("reallyworld", model));
            if (customModelData != null) meta.setCustomModelData(customModelData);
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
        if (allowed) syncEyepatch(player);
        String hint = allowed ? "§dНажми, чтобы выбрать" : "§cДоступно с доната §dmedia";
        String chosen = allowed ? "§a● Сейчас надето" : "§8● Недоступно";
        String back = get(player, BACK);
        String head = headChoice(player);
        boolean wings = back.equals("wings"), kagune = back.equals("kaneki");
        boolean halo = head.equals("halo"), patch = head.equals("eyepatch");
        menu.setItem(12, item(Material.FEATHER, "§x§F§A§D§8§F§C§lАнгельские крылья", "angel_wings", null,
            wings ? lore(chosen, "§7Аксессуар для спины", "§7Не занимает слот брони", "§7Нажми ещё раз — снять")
                  : lore(hint, "§7Аксессуар для спины", "§7Не занимает слот брони")));
        menu.setItem(13, item(Material.NETHER_STAR, "§x§F§A§D§8§F§C§lБожественный нимб", "angel_halo", null,
            halo ? lore(chosen, "§7Нимб на голову", "§7Нажми ещё раз — снять")
                 : lore(hint, "§7Нимб на голову")));
        menu.setItem(14, item(Material.RED_DYE, "§x§F§A§D§8§F§C§lЩупальца Канэки", "kaneki_tentacles_icon", null,
            kagune ? lore(chosen, "§7Анимированный аксессуар для спины", "§7Нажми ещё раз — снять")
                   : lore(hint, "§7Анимированный аксессуар для спины")));
        menu.setItem(15, item(Material.WHITE_DYE, "§x§F§A§D§8§F§C§lПовязка Канэки", "kaneki_eyepatch_icon", null,
            patch ? lore(chosen, "§7Белая повязка на левый глаз", "§7Нажми ещё раз — снять")
                  : lore(hint, "§7Белая повязка на левый глаз")));
        // 49 — нижний ряд, середина: кнопка «Снять всё» в самом низу меню
        menu.setItem(49, item(Material.BARRIER, "§cСнять всё", null, null,
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
        // the halo is a model, the patch is an item: only one of them may stay on
        if (!choice.equals("eyepatch")) takeOffPatch(player);
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
            : slot == 14 ? "elytrix_kaneki_tentacles" : null;
        if (blueprint != null && ModelEngineAPI.getBlueprint(blueprint) == null) {
            player.sendMessage("§cМодель ещё не загружена. Обратитесь к администрации."); return;
        }
        // one click wears it, the same click takes it off again
        if (slot == 12) { toggleBack(player, "wings", "Крылья"); }
        else if (slot == 14) { toggleBack(player, "kaneki", "Щупальца Канэки"); }
        else if (slot == 13) { toggleHead(player, "halo", "Нимб", "надет", "снят"); }
        else if (slot == 15) { togglePatch(player); }
        else if (slot == 49) {
            set(player, BACK, ""); setHead(player, "");
            player.sendMessage("§7Все аксессуары сняты.");
        } else return;
        openMenu(player);
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
