package org.bukkit.inventory.meta.components; import org.bukkit.NamespacedKey; import org.bukkit.inventory.EquipmentSlot;
public interface EquippableComponent { EquipmentSlot getSlot(); void setSlot(EquipmentSlot slot); NamespacedKey getModel(); void setModel(NamespacedKey model); }
