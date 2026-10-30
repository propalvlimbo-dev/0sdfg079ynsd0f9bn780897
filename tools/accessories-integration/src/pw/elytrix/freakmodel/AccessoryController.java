package pw.elytrix.freakmodel;

import com.ticxo.modelengine.api.ModelEngineAPI;
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
    private AccessoryController() {}
    private static FreakModelSpec cachedBase;
    private static FreakModelSpec cachedTentacles;
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
    public static FreakModelSpec halo(ElytrixFreakModelPlugin plugin, Player player) {
        return allowed(player) && get(player, HALO).equals("halo") ? plugin.findModel("angel_halo") : null;
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
        menu.setItem(30, item(Material.BARRIER, "§cСнять со спины", null, "", "§7Снять крылья или щупальца", "", restriction));
        menu.setItem(31, item(Material.ARROW, "§x§F§A§D§8§F§C§lНазад в меню", null, "", "§7Вернуться в главное меню", "", "§dНажми, чтобы открыть"));
        menu.setItem(32, item(Material.BARRIER, "§cСнять нимб", null, "", "§7Нимб снимается отдельно", "", restriction));
        player.openInventory(menu); return true;
    }
    @EventHandler public void onClick(InventoryClickEvent event) {
        if (!(event.getView().getTopInventory().getHolder() instanceof Holder)) return;
        event.setCancelled(true);
        if (!(event.getWhoClicked() instanceof Player player)) return;
        int slot=event.getRawSlot();
        if (slot==31) { player.closeInventory(); player.performCommand("menu"); return; }
        if (!allowed(player)) { player.sendMessage("§cПока аксессуары доступны только администрации."); return; }
        String blueprint = slot==12 ? "elytrix_angel_wings" : slot==13 ? "elytrix_angel_halo" : slot==14 ? "elytrix_kaneki_tentacles" : null;
        if (blueprint != null && ModelEngineAPI.getBlueprint(blueprint) == null) {
            player.sendMessage("§cМодель ещё не загружена. Обратитесь к администрации."); return;
        }
        if (slot==12) { set(player,BACK,"wings"); player.sendMessage("§dВыбраны крылья."); }
        else if (slot==13) { set(player,HALO,"halo"); player.sendMessage("§eВыбран нимб."); }
        else if (slot==14) { set(player,BACK,"kaneki"); player.sendMessage("§cВыбраны щупальца Канэки."); }
        else if (slot==30) { set(player,BACK,""); player.sendMessage("§7Аксессуар со спины снят."); }
        else if (slot==32) { set(player,HALO,""); player.sendMessage("§7Нимб снят."); }
    }
    @EventHandler public void onDrag(InventoryDragEvent event) {
        if (event.getView().getTopInventory().getHolder() instanceof Holder) event.setCancelled(true);
    }
}
