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
        String selection=get(player, BACK);
        FreakModelSpec base = plugin.findModel("angel_wings");
        if (base == null) return null;
        if (selection.equals("wings")) return base;
        if (!selection.equals("kaneki")) return null;
        if (base == cachedBase && cachedTentacles != null) return cachedTentacles;
        cachedBase=base;
        cachedTentacles = new FreakModelSpec("elytrix_kaneki_tentacles", base.kind, "elytrix_kaneki_tentacles", base.aliases,
            base.material, base.itemModel, base.cmd, base.displayName, base.lore, base.scale, base.yawOffset,
            base.modelYOffset, base.hitboxWidth, base.hitboxHeight, base.interpolationTicks, base.seats,
            base.seatXOffset, base.seatYOffset, base.seatZOffset, base.maxSpeed, base.reverseSpeed,
            base.acceleration, base.braking, base.rollingFriction, base.turnRate, base.kmhMultiplier,
            base.hornEnabled, base.exhaustParticles);
        return cachedTentacles;
    }
    private static final class Holder implements InventoryHolder {
        private Inventory inventory;
        @Override public Inventory getInventory() { return inventory; }
    }
    private static ItemStack item(Material mat, String title, String model) {
        ItemStack result = new ItemStack(mat); ItemMeta meta = result.getItemMeta();
        if (meta != null) { meta.setDisplayName(title); if (model != null) meta.setItemModel(new NamespacedKey("reallyworld", model)); result.setItemMeta(meta); }
        return result;
    }
    @Override public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) { sender.sendMessage("Только для игроков."); return true; }
        Holder holder = new Holder();
        Inventory menu = Bukkit.createInventory(holder, 27, "§8Аксессуары"); holder.inventory=menu;
        menu.setItem(11, item(Material.FEATHER, "§dАнгельские крылья", "angel_wings"));
        menu.setItem(13, item(Material.NETHER_STAR, "§eБожественный нимб", "angel_halo"));
        menu.setItem(15, item(Material.RED_DYE, "§cЩупальца Канэки", "kaneki_tentacles_icon"));
        menu.setItem(21, item(Material.BARRIER, "§7Снять аксессуар со спины", null));
        menu.setItem(23, item(Material.BARRIER, "§7Снять нимб", null));
        player.openInventory(menu); return true;
    }
    @EventHandler public void onClick(InventoryClickEvent event) {
        if (!(event.getView().getTopInventory().getHolder() instanceof Holder)) return;
        event.setCancelled(true);
        if (!(event.getWhoClicked() instanceof Player player)) return;
        if (!allowed(player)) { player.sendMessage("§cПока аксессуары доступны только администрации."); return; }
        int slot=event.getRawSlot();
        String blueprint = slot==11 ? "elytrix_angel_wings" : slot==13 ? "elytrix_angel_halo" : slot==15 ? "elytrix_kaneki_tentacles" : null;
        if (blueprint != null && ModelEngineAPI.getBlueprint(blueprint) == null) {
            player.sendMessage("§cМодель ещё не загружена. Обратитесь к администрации."); return;
        }
        if (slot==11) { set(player,BACK,"wings"); player.sendMessage("§dВыбраны крылья."); }
        else if (slot==13) { set(player,HALO,"halo"); player.sendMessage("§eВыбран нимб."); }
        else if (slot==15) { set(player,BACK,"kaneki"); player.sendMessage("§cВыбраны щупальца Канэки."); }
        else if (slot==21) { set(player,BACK,""); player.sendMessage("§7Аксессуар со спины снят."); }
        else if (slot==23) { set(player,HALO,""); player.sendMessage("§7Нимб снят."); }
    }
    @EventHandler public void onDrag(InventoryDragEvent event) {
        if (event.getView().getTopInventory().getHolder() instanceof Holder) event.setCancelled(true);
    }
}
