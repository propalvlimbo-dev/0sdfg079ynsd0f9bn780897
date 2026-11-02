package org.bukkit.inventory.meta;
public interface ItemMeta {
 void displayName(net.kyori.adventure.text.Component c);
 void lore(java.util.List<? extends net.kyori.adventure.text.Component> l);
 org.bukkit.persistence.PersistentDataContainer getPersistentDataContainer();
}
