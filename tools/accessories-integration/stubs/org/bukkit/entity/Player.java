package org.bukkit.entity;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.PlayerInventory;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.plugin.Plugin;

public interface Player extends HumanEntity, Entity {
    boolean hasPermission(String name);
    boolean performCommand(String command);
    void closeInventory();
    PersistentDataContainer getPersistentDataContainer();
    org.bukkit.inventory.InventoryView openInventory(Inventory inv);
    boolean isOnline();
    default boolean isDead() { return false; }
    default GameMode getGameMode() { return GameMode.SURVIVAL; }
    default float getBodyYaw() { return 0.0F; }
    String getName();
    PlayerInventory getInventory();
    Location getEyeLocation();
    void hideEntity(Plugin plugin, Entity entity);
}
