package org.bukkit.entity; import org.bukkit.inventory.ItemStack;
/** Compile-time stand-in for the display entity ModelEngine spawns per bone. */
public interface ItemDisplay extends Entity { ItemStack getItem(); }
