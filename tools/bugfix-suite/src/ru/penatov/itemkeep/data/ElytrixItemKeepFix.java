package ru.penatov.itemkeep.data;

import java.util.List;
import java.util.Map;
import org.bukkit.Material;
import org.bukkit.block.BlockState;
import org.bukkit.block.ShulkerBox;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.enchantments.Enchantment;
import org.bukkit.entity.Player;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.BlockStateMeta;
import org.bukkit.inventory.meta.EnchantmentStorageMeta;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.inventory.meta.PotionMeta;
import org.bukkit.potion.PotionType;

/**
 * Hardens ItemKeep DataManager.giveItem:
 *  1. Clones ItemStacks before PlayerInventory.addItem so cached YamlConfiguration lists are never mutated.
 *  2. Drops overflow items at the player's location when inventory is full instead of losing rewards.
 *  3. Guarantees proper enchantments on цыганский_щит and quest shulkers (*джамшут*) at runtime via Bukkit API
 *     even if an older data.yml entry lacked component enchants.
 */
public final class ElytrixItemKeepFix {

    private ElytrixItemKeepFix() {
    }

    public static void giveItem(FileConfiguration dataConfig, Player player, String name) {
        if (dataConfig == null || player == null || name == null) {
            return;
        }
        List<?> rawList = dataConfig.getList(name + ".items");
        if (rawList == null || rawList.isEmpty()) {
            return;
        }
        for (Object obj : rawList) {
            if (!(obj instanceof ItemStack)) {
                continue;
            }
            ItemStack clone = ((ItemStack) obj).clone();
            ensureExpectedEnchantments(name, clone);
            Map<Integer, ItemStack> leftovers = player.getInventory().addItem(clone);
            if (leftovers != null && !leftovers.isEmpty()) {
                for (ItemStack overflow : leftovers.values()) {
                    if (overflow != null && overflow.getType() != Material.AIR) {
                        player.getWorld().dropItemNaturally(player.getLocation(), overflow);
                    }
                }
            }
        }
    }

    public static void ensureExpectedEnchantments(String key, ItemStack stack) {
        if (key == null || stack == null || stack.getType() == Material.AIR) {
            return;
        }
        if ("цыганский_щит".equalsIgnoreCase(key) && stack.getType() == Material.SHIELD) {
            ItemMeta meta = stack.getItemMeta();
            if (meta != null && !meta.hasEnchants()) {
                meta.addEnchant(Enchantment.THORNS, 10, true);
                meta.addEnchant(Enchantment.VANISHING_CURSE, 1, true);
                meta.setUnbreakable(true);
                if (!meta.hasDisplayName()) {
                    meta.setDisplayName("\u00a7x\u00a7F\u00a78\u00a7B\u00a7E\u00a7F\u00a7BЦыганский щит");
                }
                stack.setItemMeta(meta);
            }
            return;
        }
        String lowerKey = key.toLowerCase();
        if (!lowerKey.contains("джамшут")) {
            return;
        }
        ItemMeta rawMeta = stack.getItemMeta();
        if (!(rawMeta instanceof BlockStateMeta)) {
            return;
        }
        BlockStateMeta bsm = (BlockStateMeta) rawMeta;
        BlockState state = bsm.getBlockState();
        if (!(state instanceof ShulkerBox)) {
            return;
        }
        ShulkerBox box = (ShulkerBox) state;
        Inventory inv = box.getInventory();
        boolean changed = false;
        for (int slot = 0; slot < inv.getSize(); slot++) {
            ItemStack inner = inv.getItem(slot);
            if (inner == null || inner.getType() == Material.AIR) {
                continue;
            }
            if (upgradeQuestRewardItem(lowerKey, slot, inner)) {
                inv.setItem(slot, inner);
                changed = true;
            }
        }
        if (changed) {
            bsm.setBlockState(box);
            stack.setItemMeta(bsm);
        }
    }

    private static boolean upgradeQuestRewardItem(String lowerKey, int slot, ItemStack inner) {
        Material type = inner.getType();
        ItemMeta meta = inner.getItemMeta();
        if (meta == null) {
            return false;
        }
        if (type == Material.NETHERITE_PICKAXE && !meta.hasEnchants()) {
            meta.addEnchant(Enchantment.EFFICIENCY, 5, true);
            meta.addEnchant(Enchantment.FORTUNE, 3, true);
            meta.addEnchant(Enchantment.UNBREAKING, 3, true);
            meta.addEnchant(Enchantment.MENDING, 1, true);
            inner.setItemMeta(meta);
            return true;
        }
        if (type == Material.FISHING_ROD && !meta.hasEnchants()) {
            meta.addEnchant(Enchantment.LUCK_OF_THE_SEA, 3, true);
            meta.addEnchant(Enchantment.LURE, 3, true);
            meta.addEnchant(Enchantment.UNBREAKING, 3, true);
            meta.addEnchant(Enchantment.MENDING, 1, true);
            inner.setItemMeta(meta);
            return true;
        }
        if (type == Material.NETHERITE_AXE && !meta.hasEnchants()) {
            meta.addEnchant(Enchantment.EFFICIENCY, 5, true);
            meta.addEnchant(Enchantment.SHARPNESS, 5, true);
            if (lowerKey.contains("средний")) {
                meta.addEnchant(Enchantment.FORTUNE, 3, true);
            }
            meta.addEnchant(Enchantment.UNBREAKING, 3, true);
            meta.addEnchant(Enchantment.MENDING, 1, true);
            inner.setItemMeta(meta);
            return true;
        }
        if (type == Material.NETHERITE_SWORD && !meta.hasEnchants()) {
            meta.addEnchant(Enchantment.SHARPNESS, 5, true);
            meta.addEnchant(Enchantment.FIRE_ASPECT, 2, true);
            meta.addEnchant(Enchantment.LOOTING, 3, true);
            if (lowerKey.contains("тяжел")) {
                meta.addEnchant(Enchantment.SWEEPING_EDGE, 3, true);
            }
            meta.addEnchant(Enchantment.UNBREAKING, 3, true);
            meta.addEnchant(Enchantment.MENDING, 1, true);
            inner.setItemMeta(meta);
            return true;
        }
        if (type == Material.TRIDENT && !meta.hasEnchants()) {
            meta.addEnchant(Enchantment.IMPALING, 5, true);
            if (slot == 16) {
                meta.addEnchant(Enchantment.RIPTIDE, 3, true);
            } else {
                meta.addEnchant(Enchantment.LOYALTY, 3, true);
                meta.addEnchant(Enchantment.CHANNELING, 1, true);
            }
            meta.addEnchant(Enchantment.UNBREAKING, 3, true);
            meta.addEnchant(Enchantment.MENDING, 1, true);
            inner.setItemMeta(meta);
            return true;
        }
        if (type == Material.ELYTRA && !meta.hasEnchants()) {
            meta.addEnchant(Enchantment.UNBREAKING, 3, true);
            meta.addEnchant(Enchantment.MENDING, 1, true);
            inner.setItemMeta(meta);
            return true;
        }
        if (type == Material.ENCHANTED_BOOK && meta instanceof EnchantmentStorageMeta) {
            EnchantmentStorageMeta esm = (EnchantmentStorageMeta) meta;
            if (!esm.hasStoredEnchants()) {
                if (slot == 10) {
                    esm.addStoredEnchant(Enchantment.PROTECTION, 4, true);
                    esm.addStoredEnchant(Enchantment.UNBREAKING, 3, true);
                    esm.addStoredEnchant(Enchantment.MENDING, 1, true);
                } else {
                    esm.addStoredEnchant(Enchantment.SHARPNESS, 5, true);
                    esm.addStoredEnchant(Enchantment.EFFICIENCY, 5, true);
                    esm.addStoredEnchant(Enchantment.MENDING, 1, true);
                }
                inner.setItemMeta(esm);
                return true;
            }
        }
        if (type == Material.POTION && meta instanceof PotionMeta) {
            PotionMeta pm = (PotionMeta) meta;
            if (pm.getBasePotionType() == null && !pm.hasCustomEffects()) {
                PotionType chosen = resolvePotionType(
                        slot <= 6 ? "STRONG_STRENGTH" : "STRONG_SWIFTNESS",
                        slot <= 6 ? PotionType.STRENGTH : PotionType.SWIFTNESS
                );
                pm.setBasePotionType(chosen);
                inner.setItemMeta(pm);
                return true;
            }
        }
        return false;
    }

    private static PotionType resolvePotionType(String preferred, PotionType fallback) {
        try {
            return PotionType.valueOf(preferred);
        } catch (IllegalArgumentException ignored) {
            return fallback;
        }
    }
}
