package cs.cloudstudio.recovered.cloudenchants;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataType;

/** Recognise the original plugin's keys without mutating or reissuing old items. */
public final class LegacyEnchantCompat {
    private LegacyEnchantCompat() {}
    public static boolean has(ItemStack item, CustomEnchant enchant) {
        if(item==null || item.getType().isAir() || enchant==null || !item.hasItemMeta()) return false;
        ItemMeta meta=item.getItemMeta();
        if(meta==null) return false;
        String key=enchant.configKey();
        String value=meta.getPersistentDataContainer().get(new NamespacedKey("really-enchants",key),PersistentDataType.STRING);
        if(value==null) return false;
        if(value.equalsIgnoreCase(key) || value.equalsIgnoreCase(enchant.name())) return true;
        return item.getType()==Material.ENCHANTED_BOOK && value.equalsIgnoreCase(enchant.name()+"_BOOK");
    }
}
