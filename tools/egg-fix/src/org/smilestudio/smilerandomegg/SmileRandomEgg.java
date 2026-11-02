package org.smilestudio.smilerandomegg;

import java.util.*;
import org.bukkit.*;
import org.bukkit.command.*;
import org.bukkit.entity.*;
import org.bukkit.event.*;
import org.bukkit.event.block.Action;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.inventory.*;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.plugin.java.JavaPlugin;
import org.black_ixx.playerpoints.PlayerPoints;
import org.black_ixx.playerpoints.PlayerPointsAPI;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.TextDecoration;
import net.kyori.adventure.text.serializer.legacy.LegacyComponentSerializer;

/** Compatible replacement: keeps plugin name, configuration, and random_egg PDC key. */
public final class SmileRandomEgg extends JavaPlugin implements Listener, CommandExecutor {
    private static final int PRICE=119, COUNT=3;
    private NamespacedKey key;
    private final List<EntityType> spawnable = new ArrayList<>();
    private final Random random = new Random();
    @Override public void onEnable() {
        saveDefaultConfig();
        key = new NamespacedKey(this,"random_egg");
        for(EntityType t: EntityType.values()) if(t.isSpawnable() && t.isAlive() && t != EntityType.PLAYER) spawnable.add(t);
        getServer().getPluginManager().registerEvents(this,this);
        Objects.requireNonNull(getCommand("randomegg")).setExecutor(this);
        Objects.requireNonNull(getCommand("randomeggbuy")).setExecutor(this);
    }
    private String text(String s) { return ChatColor.translateAlternateColorCodes('&',s); }
    private ItemStack newEgg(int count) {
        Material material=Material.matchMaterial(getConfig().getString("egg-item.material", "PIG_SPAWN_EGG"));
        if(material==null) material=Material.PIG_SPAWN_EGG;
        ItemStack item=new ItemStack(material,count);
        ItemMeta meta=item.getItemMeta();
        if(meta==null) throw new IllegalStateException("random egg has no ItemMeta");
        LegacyComponentSerializer serializer=LegacyComponentSerializer.legacyAmpersand();
        meta.displayName(serializer.deserialize(getConfig().getString("egg-item.name","&b&lРандомное Яйцо")).decoration(TextDecoration.ITALIC,false));
        List<Component> lore=new ArrayList<>();
        for(String line:getConfig().getStringList("egg-item.lore")) lore.add(serializer.deserialize(line).decoration(TextDecoration.ITALIC,false));
        meta.lore(lore);
        meta.getPersistentDataContainer().set(key,PersistentDataType.BYTE,(byte)1);
        item.setItemMeta(meta);
        return item;
    }
    /** Count only storage slots, not armour, offhand, or extra inventory slots. */
    static boolean fits(ItemStack egg, ItemStack[] contents) {
        int need=egg.getAmount();
        for(ItemStack existing:contents) {
            if(existing==null || existing.getType().isAir()) need-=egg.getMaxStackSize();
            else if(existing.isSimilar(egg)) need-=Math.max(0,Math.min(existing.getMaxStackSize(),egg.getMaxStackSize())-existing.getAmount());
            if(need<=0) return true;
        }
        return false;
    }
    @Override public boolean onCommand(CommandSender sender,Command command,String label,String[] args) {
        if(!sender.hasPermission("smilerandomegg.give")) { sender.sendMessage(text("&cНедостаточно прав.")); return true; }
        boolean purchase=command.getName().equalsIgnoreCase("randomeggbuy");
        if(args.length>2 || (purchase && args.length!=1) || (args.length==0 && !(sender instanceof Player))) {sender.sendMessage(text("&cУкажите игрока.")); return true;}
        Player player=args.length==0 ? (Player)sender : Bukkit.getPlayerExact(args[0]);
        if(player==null) {sender.sendMessage(text("&cИгрок не в сети.")); return true;}
        int count=COUNT;
        if(!purchase) {
            count=1;
            if(args.length==2) try {count=Integer.parseInt(args[1]);} catch(NumberFormatException ex) {count=0;}
            if(count<1 || count>64) {sender.sendMessage(text("&cКоличество: 1–64."));return true;}
        }
        PlayerInventory inv=player.getInventory(); ItemStack egg=newEgg(count);
        if(!fits(egg,inv.getStorageContents())) {player.sendMessage(text("&cОсвободите место в инвентаре."));return true;}
        ItemStack[] before=copy(inv.getStorageContents());
        PlayerPointsAPI points=null;
        if(purchase) {
            if(Bukkit.getPluginManager().getPlugin("PlayerPoints")==null || !Bukkit.getPluginManager().getPlugin("PlayerPoints").isEnabled()) {sender.sendMessage("PlayerPoints unavailable");return true;}
            points=PlayerPoints.getInstance().getAPI();
            if(points.look(player.getUniqueId()) < PRICE || !points.take(player.getUniqueId(),PRICE)) { player.sendMessage(text("&cНедостаточно рилликов."));return true; }
        }
        try {
            if(!inv.addItem(egg).isEmpty()) throw new IllegalStateException("inventory changed after capacity check");
        } catch(RuntimeException ex) {
            inv.setStorageContents(before);
            if(purchase && !points.give(player.getUniqueId(),PRICE)) getLogger().severe("REFUND FAILED for " + player.getUniqueId()+" amount="+PRICE);
            getLogger().warning("Random egg delivery failed: " + ex);
            player.sendMessage(text("&cНе удалось выдать яйца. Обратитесь к администрации."));
            return true;
        }
        player.sendMessage(text("&aВы получили рандомные яйца: &f"+count));
        if(purchase) Bukkit.dispatchCommand(Bukkit.getConsoleSender(),"cashback give "+player.getName()+" "+PRICE);
        return true;
    }
    static ItemStack[] copy(ItemStack[] original) {
        ItemStack[] copy=original.clone();
        for(int i=0;i<copy.length;i++) if(copy[i]!=null) copy[i]=copy[i].clone();
        return copy;
    }
    @EventHandler(priority=EventPriority.HIGHEST,ignoreCancelled=true)
    public void onPlayerInteract(PlayerInteractEvent event) {
        if(event.getAction()!=Action.RIGHT_CLICK_BLOCK || event.getHand()!=EquipmentSlot.HAND || event.getClickedBlock()==null || event.getBlockFace()==null) return;
        ItemStack item=event.getItem();
        if(item==null || !item.hasItemMeta() || !item.getItemMeta().getPersistentDataContainer().has(key,PersistentDataType.BYTE)) return;
        event.setCancelled(true);
        if(spawnable.isEmpty()) {event.getPlayer().sendMessage(text("&cНет доступных существ."));return;}
        Location loc=event.getClickedBlock().getRelative(event.getBlockFace()).getLocation().add(0.5,0,0.5);
        EntityType type=spawnable.get(random.nextInt(spawnable.size()));
        try {
            Entity entity=loc.getWorld().spawnEntity(loc,type);
            if(entity==null || !entity.isValid()) {event.getPlayer().sendMessage(text("&cПризыв отменён, яйцо сохранено."));return;}
        } catch(RuntimeException ex) {
            getLogger().warning("Random egg could not spawn " + type + ": " + ex);
            event.getPlayer().sendMessage(text("&cНе удалось призвать существо, яйцо сохранено."));return;
        }
        if(event.getPlayer().getGameMode()!=GameMode.CREATIVE) item.setAmount(item.getAmount()-1);
    }
}
