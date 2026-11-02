package org.bukkit.inventory;
public interface PlayerInventory { ItemStack getHelmet(); void setHelmet(ItemStack item); int firstEmpty(); java.util.Map<Integer, ItemStack> addItem(ItemStack... items); }
