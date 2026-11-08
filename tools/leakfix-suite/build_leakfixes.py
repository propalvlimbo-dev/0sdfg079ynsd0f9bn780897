#!/usr/bin/env python3
"""
Reproducible leak-fix & off-thread/chunk-reload fix builder + strict JVM (-Xverify:all) verifier for:
  1. plugins/NEnderChest-1.jar   — Always purge CheckCommand.viewers on InventoryCloseEvent (even unmodified) + PlayerQuitEvent; ConcurrentHashMap viewers
  2. plugins/NPvp-1.0.jar        — Purge quitting players from PvpSelect.pvpPlayers & PvpSelect.continuePvp menu via PlayerQuitEvent
  3. plugins/IRandomTeleport.jar — Purge ChannelManager.teleportingPlayers on PlayerQuitEvent/PlayerDeathEvent/PlayerChangedWorldEvent; replace strong Player capture in Channel$1/$2 with String playerName; strip stray org/bukkit/plugin/Plugin.class
  4. plugins/NFurnace-1.jar      — Guard SmeltStartEvent & BrewStartEvent 5-tick timers with World.isChunkLoaded(cx, cz) BEFORE getInventory()/getHolder(); evict unloaded/broken entries; key state maps by String coord instead of BlockState; remove broken blocks on BlockBreakEvent & re-register on FurnaceBurnEvent/BrewingStandFuelEvent
  5. plugins/NClans-1.jar        — Rewrite GlowListener: ConcurrentHashMap playerArmorMap + O(1) ONLINE_BY_ID + CHEST_BY_RGB cache, fast-return when GlowFunction.clansMap is empty or packet lacks ItemSlot.CHEST, replace CHEST slot via PacketEvent.setPacket without cancelling/re-entering Netty or calling Player.getEquipment() off-thread, gate onChunkUpdate on actual chunk-coord change, purge quitting players on PlayerQuitEvent; ConcurrentHashMap GlowFunction.clansMap; GlowManager.sendArmors(..., false); QuestListener.lastBrewer cleanup on BlockBreakEvent + size cap
"""
import hashlib
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JAVA = os.environ.get("JAVA", "/tmp/pytools/venv/lib/python3.11/site-packages/jdk4py/java-runtime/bin/java")
ECJ = os.environ.get("ECJ", "/tmp/pytools/ecj.jar")
BLIB_JAR = ROOT / "plugins/BLib.jar"
PLIB_JAR = ROOT / "plugins/ProtocolLib.jar"

STUBS = {
    "org/bukkit/Bukkit.java": """
package org.bukkit;
import java.util.Collection;
import java.util.Collections;
import java.util.UUID;
import org.bukkit.entity.Player;
import org.bukkit.plugin.PluginManager;
import org.bukkit.scheduler.BukkitScheduler;
public final class Bukkit {
    public static PluginManager getPluginManager() { return null; }
    public static BukkitScheduler getScheduler() { return null; }
    public static Collection<? extends Player> getOnlinePlayers() { return Collections.emptyList(); }
    public static Player getPlayer(UUID id) { return null; }
    public static Player getPlayerExact(String name) { return null; }
}
""",
    "org/bukkit/Color.java": """
package org.bukkit;
public final class Color {
    private final int rgb;
    private Color(int rgb) { this.rgb = rgb & 0xFFFFFF; }
    public static Color fromRGB(int rgb) { return new Color(rgb); }
    public int asRGB() { return rgb; }
}
""",
    "org/bukkit/Material.java": """
package org.bukkit;
public enum Material {
    AIR, LEATHER_CHESTPLATE, CHAINMAIL_CHESTPLATE, PLAYER_HEAD, DIAMOND_SWORD,
    GRAY_STAINED_GLASS_PANE, ORANGE_STAINED_GLASS_PANE, FURNACE, BLAST_FURNACE, SMOKER, BREWING_STAND
}
""",
    "org/bukkit/NamespacedKey.java": """
package org.bukkit;
public final class NamespacedKey {}
""",
    "org/bukkit/Chunk.java": """
package org.bukkit;
import org.bukkit.entity.Entity;
public interface Chunk {
    Entity[] getEntities();
}
""",
    "org/bukkit/World.java": """
package org.bukkit;
import org.bukkit.block.Block;
public interface World {
    String getName();
    boolean isChunkLoaded(int x, int z);
    Block getBlockAt(int x, int y, int z);
    Chunk getChunkAt(int x, int z);
}
""",
    "org/bukkit/Location.java": """
package org.bukkit;
import org.bukkit.block.Block;
public class Location {
    private World world;
    private double x, y, z;
    public Location() {}
    public Location(World world, double x, double y, double z) {
        this.world = world; this.x = x; this.y = y; this.z = z;
    }
    public World getWorld() { return world; }
    public double getX() { return x; }
    public double getY() { return y; }
    public double getZ() { return z; }
    public int getBlockX() { return (int) Math.floor(x); }
    public int getBlockY() { return (int) Math.floor(y); }
    public int getBlockZ() { return (int) Math.floor(z); }
    public Block getBlock() { return world == null ? null : world.getBlockAt(getBlockX(), getBlockY(), getBlockZ()); }
    public Chunk getChunk() { return world == null ? null : world.getChunkAt(getBlockX() >> 4, getBlockZ() >> 4); }
    public double distanceSquared(Location o) {
        double dx = x - o.x, dy = y - o.y, dz = z - o.z;
        return dx * dx + dy * dy + dz * dz;
    }
}
""",
    "org/bukkit/command/CommandSender.java": """
package org.bukkit.command;
public interface CommandSender {
    void sendMessage(String msg);
    boolean hasPermission(String perm);
}
""",
    "org/bukkit/entity/Entity.java": """
package org.bukkit.entity;
import java.util.UUID;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.command.CommandSender;
public interface Entity extends CommandSender {
    int getEntityId();
    UUID getUniqueId();
    Location getLocation();
    World getWorld();
}
""",
    "org/bukkit/entity/LivingEntity.java": """
package org.bukkit.entity;
import org.bukkit.inventory.EntityEquipment;
public interface LivingEntity extends Entity {
    EntityEquipment getEquipment();
    Player getKiller();
}
""",
    "org/bukkit/entity/HumanEntity.java": """
package org.bukkit.entity;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryView;
public interface HumanEntity extends LivingEntity {
    String getName();
    InventoryView openInventory(Inventory inv);
}
""",
    "org/bukkit/entity/Player.java": """
package org.bukkit.entity;
public interface Player extends HumanEntity {
    Player getPlayer();
    boolean isOnline();
}
""",
    "org/bukkit/entity/EntityType.java": """
package org.bukkit.entity;
public enum EntityType { ZOMBIE }
""",
    "org/bukkit/block/Block.java": """
package org.bukkit.block;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
public interface Block {
    World getWorld();
    int getX();
    int getY();
    int getZ();
    Location getLocation();
    Material getType();
    BlockState getState();
}
""",
    "org/bukkit/block/BlockState.java": """
package org.bukkit.block;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
public interface BlockState {
    World getWorld();
    int getX();
    int getY();
    int getZ();
    Location getLocation();
    Material getType();
    boolean update();
}
""",
    "org/bukkit/block/TileState.java": """
package org.bukkit.block;
import org.bukkit.persistence.PersistentDataHolder;
public interface TileState extends BlockState, PersistentDataHolder {}
""",
    "org/bukkit/block/Container.java": """
package org.bukkit.block;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
public interface Container extends TileState, InventoryHolder {
    Inventory getInventory();
}
""",
    "org/bukkit/block/Furnace.java": """
package org.bukkit.block;
import org.bukkit.inventory.FurnaceInventory;
public interface Furnace extends Container {
    @Override FurnaceInventory getInventory();
    void setCookTime(short cookTime);
    void setBurnTime(short burnTime);
    void setCookTimeTotal(int cookTimeTotal);
}
""",
    "org/bukkit/block/BrewingStand.java": """
package org.bukkit.block;
import org.bukkit.inventory.BrewerInventory;
public interface BrewingStand extends Container {
    @Override BrewerInventory getInventory();
    int getBrewingTime();
    void setBrewingTime(int brewTime);
}
""",
    "org/bukkit/persistence/PersistentDataType.java": """
package org.bukkit.persistence;
public interface PersistentDataType<P, C> {
    PersistentDataType<String, String> STRING = null;
    PersistentDataType<Integer, Integer> INTEGER = null;
}
""",
    "org/bukkit/persistence/PersistentDataContainer.java": """
package org.bukkit.persistence;
import org.bukkit.NamespacedKey;
public interface PersistentDataContainer {
    <P, C> boolean has(NamespacedKey key, PersistentDataType<P, C> type);
    <P, C> C get(NamespacedKey key, PersistentDataType<P, C> type);
    <P, C> void set(NamespacedKey key, PersistentDataType<P, C> type, C value);
}
""",
    "org/bukkit/persistence/PersistentDataHolder.java": """
package org.bukkit.persistence;
public interface PersistentDataHolder {
    PersistentDataContainer getPersistentDataContainer();
}
""",
    "org/bukkit/inventory/InventoryHolder.java": """
package org.bukkit.inventory;
public interface InventoryHolder {
    Inventory getInventory();
}
""",
    "org/bukkit/inventory/Inventory.java": """
package org.bukkit.inventory;
import java.util.HashMap;
import org.bukkit.Location;
import org.bukkit.event.inventory.InventoryType;
public interface Inventory {
    InventoryHolder getHolder();
    ItemStack[] getContents();
    Location getLocation();
    InventoryType getType();
    int getSize();
    ItemStack getItem(int index);
    void setItem(int index, ItemStack item);
    void remove(ItemStack item);
    HashMap<Integer, ItemStack> addItem(ItemStack... items);
}
""",
    "org/bukkit/inventory/InventoryView.java": """
package org.bukkit.inventory;
public abstract class InventoryView {
    public abstract String getTitle();
}
""",
    "org/bukkit/inventory/FurnaceInventory.java": """
package org.bukkit.inventory;
import org.bukkit.block.Furnace;
public interface FurnaceInventory extends Inventory {
    ItemStack getSmelting();
    ItemStack getFuel();
    ItemStack getResult();
    void setFuel(ItemStack stack);
    @Override Furnace getHolder();
}
""",
    "org/bukkit/inventory/BrewerInventory.java": """
package org.bukkit.inventory;
import org.bukkit.block.BrewingStand;
public interface BrewerInventory extends Inventory {
    @Override BrewingStand getHolder();
}
""",
    "org/bukkit/inventory/EntityEquipment.java": """
package org.bukkit.inventory;
public interface EntityEquipment {
    ItemStack getHelmet();
    ItemStack getChestplate();
    ItemStack getLeggings();
    ItemStack getBoots();
}
""",
    "org/bukkit/inventory/ItemStack.java": """
package org.bukkit.inventory;
import org.bukkit.Material;
import org.bukkit.inventory.meta.ItemMeta;
public class ItemStack implements Cloneable {
    private Material type;
    private int amount = 1;
    private ItemMeta meta;
    public ItemStack(Material type) { this.type = type; }
    public Material getType() { return type; }
    public int getAmount() { return amount; }
    public void setAmount(int amount) { this.amount = amount; }
    public ItemMeta getItemMeta() { return meta; }
    public boolean setItemMeta(ItemMeta meta) { this.meta = meta; return true; }
    @Override public ItemStack clone() {
        ItemStack copy = new ItemStack(type);
        copy.amount = amount;
        copy.meta = meta;
        return copy;
    }
}
""",
    "org/bukkit/inventory/meta/ItemMeta.java": """
package org.bukkit.inventory.meta;
import java.util.List;
import org.bukkit.persistence.PersistentDataHolder;
public interface ItemMeta extends PersistentDataHolder {
    String getDisplayName();
    void setDisplayName(String name);
    void setLore(List<String> lore);
}
""",
    "org/bukkit/inventory/meta/LeatherArmorMeta.java": """
package org.bukkit.inventory.meta;
import org.bukkit.Color;
public interface LeatherArmorMeta extends ItemMeta {
    Color getColor();
    void setColor(Color color);
}
""",
    "org/bukkit/inventory/meta/PotionMeta.java": """
package org.bukkit.inventory.meta;
import org.bukkit.potion.PotionType;
public interface PotionMeta extends ItemMeta {
    PotionType getBasePotionType();
}
""",
    "org/bukkit/potion/PotionType.java": """
package org.bukkit.potion;
public enum PotionType { WATER }
""",
    "org/bukkit/enchantments/Enchantment.java": """
package org.bukkit.enchantments;
import org.bukkit.Keyed;
public abstract class Enchantment implements Keyed {}
""",
    "org/bukkit/Keyed.java": """
package org.bukkit;
public interface Keyed {}
""",
    "org/bukkit/configuration/serialization/ConfigurationSerializable.java": """
package org.bukkit.configuration.serialization;
import java.util.Map;
public interface ConfigurationSerializable {
    Map<String, Object> serialize();
}
""",
    "org/bukkit/ChatColor.java": """
package org.bukkit;
public enum ChatColor {
    RED;
    public static String stripColor(String input) { return input; }
    public static String translateAlternateColorCodes(char altColorChar, String textToTranslate) { return textToTranslate; }
}
""",
    "org/bukkit/event/Listener.java": """
package org.bukkit.event;
public interface Listener {}
""",
    "org/bukkit/event/Cancellable.java": """
package org.bukkit.event;
public interface Cancellable {
    boolean isCancelled();
    void setCancelled(boolean cancel);
}
""",
    "org/bukkit/event/EventPriority.java": """
package org.bukkit.event;
public enum EventPriority { LOWEST, LOW, NORMAL, HIGH, HIGHEST, MONITOR }
""",
    "org/bukkit/event/EventHandler.java": """
package org.bukkit.event;
import java.lang.annotation.*;
@Retention(RetentionPolicy.RUNTIME)
@Target(ElementType.METHOD)
public @interface EventHandler {
    EventPriority priority() default EventPriority.NORMAL;
    boolean ignoreCancelled() default false;
}
""",
    "org/bukkit/event/HandlerList.java": """
package org.bukkit.event;
public class HandlerList {}
""",
    "org/bukkit/event/Event.java": """
package org.bukkit.event;
public abstract class Event {
    public abstract HandlerList getHandlers();
}
""",
    "org/bukkit/event/player/PlayerEvent.java": """
package org.bukkit.event.player;
import org.bukkit.entity.Player;
import org.bukkit.event.Event;
public abstract class PlayerEvent extends Event {
    protected Player player;
    public PlayerEvent(Player who) { this.player = who; }
    public final Player getPlayer() { return player; }
}
""",
    "org/bukkit/event/player/PlayerJoinEvent.java": """
package org.bukkit.event.player;
import org.bukkit.entity.Player;
import org.bukkit.event.HandlerList;
public class PlayerJoinEvent extends PlayerEvent {
    public PlayerJoinEvent(Player who) { super(who); }
    @Override public HandlerList getHandlers() { return null; }
}
""",
    "org/bukkit/event/player/PlayerQuitEvent.java": """
package org.bukkit.event.player;
import org.bukkit.entity.Player;
import org.bukkit.event.HandlerList;
public class PlayerQuitEvent extends PlayerEvent {
    public PlayerQuitEvent(Player who) { super(who); }
    @Override public HandlerList getHandlers() { return null; }
}
""",
    "org/bukkit/event/player/PlayerRespawnEvent.java": """
package org.bukkit.event.player;
import org.bukkit.entity.Player;
import org.bukkit.event.HandlerList;
public class PlayerRespawnEvent extends PlayerEvent {
    public PlayerRespawnEvent(Player who) { super(who); }
    @Override public HandlerList getHandlers() { return null; }
}
""",
    "org/bukkit/event/player/PlayerChangedWorldEvent.java": """
package org.bukkit.event.player;
import org.bukkit.entity.Player;
import org.bukkit.event.HandlerList;
public class PlayerChangedWorldEvent extends PlayerEvent {
    public PlayerChangedWorldEvent(Player who) { super(who); }
    @Override public HandlerList getHandlers() { return null; }
}
""",
    "org/bukkit/event/player/PlayerMoveEvent.java": """
package org.bukkit.event.player;
import org.bukkit.Location;
import org.bukkit.entity.Player;
import org.bukkit.event.HandlerList;
public class PlayerMoveEvent extends PlayerEvent {
    private Location from, to;
    public PlayerMoveEvent(Player who, Location from, Location to) {
        super(who); this.from = from; this.to = to;
    }
    public Location getFrom() { return from; }
    public Location getTo() { return to; }
    @Override public HandlerList getHandlers() { return null; }
}
""",
    "org/bukkit/event/entity/EntityEvent.java": """
package org.bukkit.event.entity;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.event.Event;
public abstract class EntityEvent extends Event {
    protected Entity entity;
    public Entity getEntity() { return entity; }
    public EntityType getEntityType() { return EntityType.ZOMBIE; }
}
""",
    "org/bukkit/event/entity/EntityDamageEvent.java": """
package org.bukkit.event.entity;
import org.bukkit.event.Cancellable;
import org.bukkit.event.HandlerList;
public class EntityDamageEvent extends EntityEvent implements Cancellable {
    public enum DamageCause { FALL }
    public DamageCause getCause() { return DamageCause.FALL; }
    @Override public boolean isCancelled() { return false; }
    @Override public void setCancelled(boolean cancel) {}
    @Override public HandlerList getHandlers() { return null; }
}
""",
    "org/bukkit/event/entity/EntityDeathEvent.java": """
package org.bukkit.event.entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.event.HandlerList;
public class EntityDeathEvent extends EntityEvent {
    @Override public LivingEntity getEntity() { return (LivingEntity) entity; }
    @Override public HandlerList getHandlers() { return null; }
}
""",
    "org/bukkit/event/entity/PlayerDeathEvent.java": """
package org.bukkit.event.entity;
import org.bukkit.entity.Player;
public class PlayerDeathEvent extends EntityDeathEvent {
    public PlayerDeathEvent(Player p) { this.entity = p; }
    @Override public Player getEntity() { return (Player) entity; }
}
""",
    "org/bukkit/event/block/BlockEvent.java": """
package org.bukkit.event.block;
import org.bukkit.block.Block;
import org.bukkit.event.Event;
public abstract class BlockEvent extends Event {
    protected Block block;
    public final Block getBlock() { return block; }
}
""",
    "org/bukkit/event/block/BlockBreakEvent.java": """
package org.bukkit.event.block;
import org.bukkit.block.Block;
import org.bukkit.event.HandlerList;
public class BlockBreakEvent extends BlockEvent {
    public BlockBreakEvent(Block b) { this.block = b; }
    @Override public HandlerList getHandlers() { return null; }
}
""",
    "org/bukkit/event/enchantment/EnchantItemEvent.java": """
package org.bukkit.event.enchantment;
import org.bukkit.entity.Player;
import org.bukkit.event.Event;
import org.bukkit.event.HandlerList;
import org.bukkit.inventory.ItemStack;
public class EnchantItemEvent extends Event {
    public Player getEnchanter() { return null; }
    public ItemStack getItem() { return null; }
    @Override public HandlerList getHandlers() { return null; }
}
""",
    "org/bukkit/event/inventory/InventoryType.java": """
package org.bukkit.event.inventory;
public enum InventoryType { CHEST, BREWING }
""",
    "org/bukkit/event/inventory/InventoryEvent.java": """
package org.bukkit.event.inventory;
import org.bukkit.event.Event;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryView;
public class InventoryEvent extends Event {
    protected Inventory inv;
    public Inventory getInventory() { return inv; }
    public InventoryView getView() { return null; }
    @Override public org.bukkit.event.HandlerList getHandlers() { return null; }
}
""",
    "org/bukkit/event/inventory/InventoryOpenEvent.java": """
package org.bukkit.event.inventory;
import org.bukkit.entity.HumanEntity;
public class InventoryOpenEvent extends InventoryEvent {
    private HumanEntity player;
    public HumanEntity getPlayer() { return player; }
}
""",
    "org/bukkit/event/inventory/InventoryCloseEvent.java": """
package org.bukkit.event.inventory;
import org.bukkit.entity.HumanEntity;
import org.bukkit.inventory.Inventory;
public class InventoryCloseEvent extends InventoryEvent {
    private final HumanEntity player;
    public InventoryCloseEvent(HumanEntity player, Inventory inv) {
        this.player = player; this.inv = inv;
    }
    public HumanEntity getPlayer() { return player; }
}
""",
    "org/bukkit/event/inventory/InventoryClickEvent.java": """
package org.bukkit.event.inventory;
import org.bukkit.entity.HumanEntity;
import org.bukkit.event.Cancellable;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
public class InventoryClickEvent extends InventoryEvent implements Cancellable {
    public Inventory getClickedInventory() { return null; }
    public ItemStack getCurrentItem() { return null; }
    public HumanEntity getWhoClicked() { return null; }
    @Override public boolean isCancelled() { return false; }
    @Override public void setCancelled(boolean cancel) {}
}
""",
    "org/bukkit/event/inventory/BrewEvent.java": """
package org.bukkit.event.inventory;
import org.bukkit.event.block.BlockEvent;
import org.bukkit.event.HandlerList;
public class BrewEvent extends BlockEvent {
    @Override public HandlerList getHandlers() { return null; }
}
""",
    "org/bukkit/event/inventory/FurnaceBurnEvent.java": """
package org.bukkit.event.inventory;
import org.bukkit.event.block.BlockEvent;
import org.bukkit.event.HandlerList;
public class FurnaceBurnEvent extends BlockEvent {
    @Override public HandlerList getHandlers() { return null; }
}
""",
    "org/bukkit/event/inventory/BrewingStandFuelEvent.java": """
package org.bukkit.event.inventory;
import org.bukkit.event.block.BlockEvent;
import org.bukkit.event.HandlerList;
public class BrewingStandFuelEvent extends BlockEvent {
    @Override public HandlerList getHandlers() { return null; }
}
""",
    "org/bukkit/configuration/file/FileConfiguration.java": """
package org.bukkit.configuration.file;
import java.util.List;
public class FileConfiguration {
    public List<String> getStringList(String path) { return java.util.Collections.emptyList(); }
}
""",
    "org/bukkit/plugin/Plugin.java": """
package org.bukkit.plugin;
public interface Plugin {}
""",
    "org/bukkit/plugin/PluginManager.java": """
package org.bukkit.plugin;
import org.bukkit.event.Event;
import org.bukkit.event.Listener;
public interface PluginManager {
    void callEvent(Event event);
    void registerEvents(Listener listener, Plugin plugin);
}
""",
    "org/bukkit/plugin/java/JavaPlugin.java": """
package org.bukkit.plugin.java;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.plugin.Plugin;
public abstract class JavaPlugin implements Plugin {
    public static <T extends JavaPlugin> T getPlugin(Class<T> clazz) { return null; }
    public FileConfiguration getConfig() { return null; }
}
""",
    "org/bukkit/scheduler/BukkitTask.java": """
package org.bukkit.scheduler;
public interface BukkitTask {
    void cancel();
}
""",
    "org/bukkit/scheduler/BukkitScheduler.java": """
package org.bukkit.scheduler;
import org.bukkit.plugin.Plugin;
public interface BukkitScheduler {
    BukkitTask runTask(Plugin plugin, Runnable task);
    BukkitTask runTaskTimer(Plugin plugin, Runnable task, long delay, long period);
}
""",
    "org/bukkit/scheduler/BukkitRunnable.java": """
package org.bukkit.scheduler;
public abstract class BukkitRunnable implements Runnable {
    public synchronized void cancel() throws IllegalStateException {}
}
""",
    "org/jetbrains/annotations/NotNull.java": """
package org.jetbrains.annotations;
import java.lang.annotation.*;
@Retention(RetentionPolicy.CLASS)
@Target({ElementType.METHOD, ElementType.PARAMETER, ElementType.FIELD, ElementType.TYPE_USE})
public @interface NotNull {}
""",
}

NENDERCHEST_CLOSE_SRC = r"""
package wtf.n1zamu.listener;

import java.util.ArrayList;
import java.util.List;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.ItemStack;
import wtf.n1zamu.NEnderChest;
import wtf.n1zamu.command.impl.CheckCommand;
import wtf.n1zamu.database.items.object.InventoryItem;
import wtf.n1zamu.holder.EnderChestHolder;

public class InventoryCloseListener implements Listener {
    @EventHandler
    public void onCloseInventory(InventoryCloseEvent event) {
        if (!(event.getPlayer() instanceof Player)) {
            return;
        }
        Player player = ((Player) event.getPlayer()).getPlayer();
        if (player == null) {
            player = (Player) event.getPlayer();
        }
        if (!(event.getInventory().getHolder() instanceof EnderChestHolder)) {
            return;
        }
        ItemStack[] contents = event.getInventory().getContents();
        List<InventoryItem> inventoryItemList = new ArrayList<>();
        for (int index = 0; index < contents.length; index++) {
            ItemStack item = contents[index];
            if (item == null || item.getType() == Material.AIR) {
                continue;
            }
            inventoryItemList.add(new InventoryItem(index, item));
        }

        // Always remove from CheckCommand.viewers on close (even when items were not modified!)
        String viewedTarget = CheckCommand.viewers.remove(player);
        if (viewedTarget == null) {
            List<InventoryItem> items = NEnderChest.getINSTANCE().getItemsDataBase().getPlayerItems(player.getName());
            if (inventoryItemList.equals(items)) {
                return;
            }
            NEnderChest.getINSTANCE().getItemsDataBase().updateForPlayer(player.getName(), inventoryItemList);
        } else {
            List<InventoryItem> items = NEnderChest.getINSTANCE().getItemsDataBase().getPlayerItems(viewedTarget);
            if (inventoryItemList.equals(items)) {
                return;
            }
            NEnderChest.getINSTANCE().getItemsDataBase().updateForPlayer(viewedTarget, inventoryItemList);
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuit(PlayerQuitEvent event) {
        Player player = event.getPlayer();
        if (player != null) {
            CheckCommand.viewers.remove(player);
        }
    }
}
"""

NFURNACE_SMELT_SRC = r"""
package wtf.n1zamu.events.impl;

import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockState;
import org.bukkit.block.Furnace;
import org.bukkit.event.Cancellable;
import org.bukkit.event.Event;
import org.bukkit.event.HandlerList;
import org.bukkit.inventory.FurnaceInventory;
import org.bukkit.inventory.ItemStack;
import org.jetbrains.annotations.NotNull;
import wtf.n1zamu.NFurnace;
import wtf.n1zamu.events.ICustomEvent;
import wtf.n1zamu.events.impl.listener.FurnaceInventoryListener;

public class SmeltStartEvent extends Event implements Cancellable, ICustomEvent {
    private final Furnace furnace;
    private final Map<Furnace, List<Integer>> previousContents = new HashMap<>();
    private final Map<String, int[]> previousByKey = new HashMap<>();
    private static final HandlerList handlers = new HandlerList();

    public SmeltStartEvent(Furnace furnace) {
        this.furnace = furnace;
    }

    public void startEventThread() {
        Bukkit.getScheduler().runTaskTimer(NFurnace.getINSTANCE(), this::tickFurnaces, 0L, 5L);
    }

    public void tickFurnaces() {
        List<Furnace> list = FurnaceInventoryListener.furnaces;
        if (list == null || list.isEmpty()) {
            if (!previousByKey.isEmpty()) previousByKey.clear();
            return;
        }
        Set<String> seenInPass = new HashSet<>(list.size() * 2);
        Iterator<Furnace> it = list.iterator();
        while (it.hasNext()) {
            Furnace furn = it.next();
            if (furn == null) {
                it.remove();
                continue;
            }
            World world = furn.getWorld();
            int x = furn.getX();
            int y = furn.getY();
            int z = furn.getZ();
            String key = (world == null ? "" : world.getName()) + ':' + x + ':' + y + ':' + z;
            // Never touch unloaded chunks (prevents synchronous chunk reloads AND releases CraftFurnace -> LevelChunk pin!)
            if (world == null || !world.isChunkLoaded(x >> 4, z >> 4) || !seenInPass.add(key)) {
                it.remove();
                previousByKey.remove(key);
                continue;
            }
            Block block = world.getBlockAt(x, y, z);
            if (block == null) {
                it.remove();
                previousByKey.remove(key);
                continue;
            }
            BlockState liveState = block.getState();
            if (!(liveState instanceof Furnace)) {
                it.remove();
                previousByKey.remove(key);
                continue;
            }
            Furnace live = (Furnace) liveState;
            FurnaceInventory inv = live.getInventory();
            if (inv == null) {
                continue;
            }
            ItemStack smelting = inv.getSmelting();
            ItemStack fuel = inv.getFuel();
            ItemStack result = inv.getResult();
            if (smelting == null || fuel == null || result == null) {
                previousByKey.remove(key);
                continue;
            }
            int sAmt = smelting.getAmount();
            int rAmt = result.getAmount();
            int[] prev = previousByKey.get(key);
            if (prev == null) {
                previousByKey.put(key, new int[]{sAmt, rAmt});
                Furnace holder = inv.getHolder();
                Bukkit.getPluginManager().callEvent(new SmeltStartEvent(holder != null ? holder : live));
            } else if (prev[0] != sAmt || prev[1] != rAmt) {
                prev[0] = sAmt;
                prev[1] = rAmt;
                Furnace holder = inv.getHolder();
                Bukkit.getPluginManager().callEvent(new SmeltStartEvent(holder != null ? holder : live));
            }
        }
        if (previousByKey.size() > seenInPass.size()) {
            previousByKey.keySet().retainAll(seenInPass);
        }
    }

    @Override
    public boolean isCancelled() {
        return false;
    }

    @Override
    public void setCancelled(boolean cancel) {
    }

    public Furnace getFurnace() {
        return this.furnace;
    }

    @Override
    @NotNull
    public HandlerList getHandlers() {
        return handlers;
    }

    public static HandlerList getHandlerList() {
        return handlers;
    }
}
"""

NFURNACE_BREW_SRC = r"""
package wtf.n1zamu.events.impl;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockState;
import org.bukkit.block.BrewingStand;
import org.bukkit.event.Cancellable;
import org.bukkit.event.Event;
import org.bukkit.event.HandlerList;
import org.bukkit.inventory.BrewerInventory;
import org.jetbrains.annotations.NotNull;
import wtf.n1zamu.NFurnace;
import wtf.n1zamu.events.ICustomEvent;
import wtf.n1zamu.events.impl.listener.BrewingStandInventoryListener;

public class BrewStartEvent extends Event implements Cancellable, ICustomEvent {
    public static final Map<BrewingStand, Integer> previousContents = new HashMap<>();
    private static final Map<String, Integer> previousByKey = new HashMap<>();
    private static final HandlerList handlers = new HandlerList();
    private final BrewingStand brewingStand;

    public BrewStartEvent(BrewingStand brewingStand) {
        this.brewingStand = brewingStand;
    }

    @Override
    public boolean isCancelled() {
        return false;
    }

    @Override
    public void setCancelled(boolean cancel) {
    }

    @Override
    @NotNull
    public HandlerList getHandlers() {
        return handlers;
    }

    public static HandlerList getHandlerList() {
        return handlers;
    }

    public BrewingStand getBrewingStand() {
        return this.brewingStand;
    }

    public void startEventThread() {
        Bukkit.getScheduler().runTaskTimer(NFurnace.getINSTANCE(), BrewStartEvent::tickBrewingStands, 0L, 5L);
    }

    public static void tickBrewingStands() {
        List<BrewerInventory> list = BrewingStandInventoryListener.brewingStands;
        if (list == null || list.isEmpty()) {
            if (!previousByKey.isEmpty()) previousByKey.clear();
            if (!previousContents.isEmpty()) previousContents.clear();
            return;
        }
        Set<String> seenInPass = new HashSet<>(list.size() * 2);
        Iterator<BrewerInventory> it = list.iterator();
        while (it.hasNext()) {
            BrewerInventory brewerInventory = it.next();
            if (brewerInventory == null) {
                it.remove();
                continue;
            }
            Location loc = brewerInventory.getLocation();
            if (loc == null) {
                it.remove();
                continue;
            }
            World world = loc.getWorld();
            int bx = loc.getBlockX();
            int by = loc.getBlockY();
            int bz = loc.getBlockZ();
            String key = (world == null ? "" : world.getName()) + ':' + bx + ':' + by + ':' + bz;
            // Guard BEFORE getHolder()/getBlock().getState() so unloaded chunks are NEVER reloaded or pinned in heap!
            if (world == null || !world.isChunkLoaded(bx >> 4, bz >> 4) || !seenInPass.add(key)) {
                it.remove();
                previousByKey.remove(key);
                continue;
            }
            Block block = world.getBlockAt(bx, by, bz);
            if (block == null) {
                it.remove();
                previousByKey.remove(key);
                continue;
            }
            BlockState state = block.getState();
            if (!(state instanceof BrewingStand)) {
                it.remove();
                previousByKey.remove(key);
                continue;
            }
            BrewingStand live = (BrewingStand) state;
            int currentTime = live.getBrewingTime();
            Integer previousTime = previousByKey.get(key);
            if (previousTime != null && previousTime.intValue() == 0 && currentTime != 0) {
                Bukkit.getPluginManager().callEvent(new BrewStartEvent(live));
            }
            previousByKey.put(key, Integer.valueOf(currentTime));
        }
        if (previousByKey.size() > seenInPass.size()) {
            previousByKey.keySet().retainAll(seenInPass);
        }
        if (!previousContents.isEmpty()) {
            previousContents.clear();
        }
    }
}
"""

NCLANS_GLOW_LISTENER_SRC = r"""
package wtf.n1zamu.function.impl.glow;

import com.comphenix.protocol.PacketType;
import com.comphenix.protocol.ProtocolLibrary;
import com.comphenix.protocol.events.ConnectionSide;
import com.comphenix.protocol.events.PacketAdapter;
import com.comphenix.protocol.events.PacketContainer;
import com.comphenix.protocol.events.PacketEvent;
import com.comphenix.protocol.wrappers.EnumWrappers;
import com.comphenix.protocol.wrappers.Pair;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerMoveEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerRespawnEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.inventory.meta.LeatherArmorMeta;
import wtf.n1zamu.NClans;
import wtf.n1zamu.api.ClanManager;
import wtf.n1zamu.clans.Clan;
import wtf.n1zamu.utils.NBTUtil;

public class GlowListener extends PacketAdapter implements Listener {
    public static Map<Player, List<Player>> playerArmorMap = new ConcurrentHashMap<>();
    private static final ConcurrentHashMap<Integer, Player> ONLINE_BY_ID = new ConcurrentHashMap<>();
    private static final ConcurrentHashMap<Integer, ItemStack> CHEST_BY_RGB = new ConcurrentHashMap<>();

    static {
        try {
            Collection<? extends Player> online = Bukkit.getOnlinePlayers();
            if (online != null) {
                for (Player p : online) {
                    if (p != null) {
                        ONLINE_BY_ID.put(Integer.valueOf(p.getEntityId()), p);
                    }
                }
            }
        } catch (Throwable ignored) {
        }
    }

    public GlowListener() {
        super(NClans.getInstance(), new PacketType[]{PacketType.Play.Server.ENTITY_EQUIPMENT});
        this.connectionSide = ConnectionSide.SERVER_SIDE;
    }

    @Override
    public void onPacketReceiving(PacketEvent event) {
    }

    @Override
    public void onPacketSending(PacketEvent event) {
        if (event == null || event.getPacketType() != PacketType.Play.Server.ENTITY_EQUIPMENT) {
            return;
        }
        Map<Clan, Color> activeGlows = GlowFunction.clansMap;
        if (activeGlows == null || activeGlows.isEmpty()) {
            return;
        }
        PacketContainer packet = event.getPacket();
        if (packet == null) {
            return;
        }
        List<List<Pair<EnumWrappers.ItemSlot, ItemStack>>> values = packet.getSlotStackPairLists().getValues();
        if (values == null || values.isEmpty()) {
            return;
        }
        List<Pair<EnumWrappers.ItemSlot, ItemStack>> pairs = values.get(0);
        if (pairs == null || pairs.isEmpty()) {
            return;
        }

        // Fast-path: 99% of ENTITY_EQUIPMENT packets are MAINHAND/OFFHAND swaps — skip unless CHEST is present!
        int chestIdx = -1;
        for (int i = 0; i < pairs.size(); i++) {
            Pair<EnumWrappers.ItemSlot, ItemStack> pair = pairs.get(i);
            if (pair == null) continue;
            if (pair.getFirst() == EnumWrappers.ItemSlot.CHEST) {
                ItemStack second = pair.getSecond();
                if (second != null && NBTUtil.hasItemNBT(second, "clans_protocol")) {
                    return;
                }
                chestIdx = i;
                break;
            }
        }
        if (chestIdx < 0) {
            return;
        }

        Player receiver = event.getPlayer();
        if (receiver == null) {
            return;
        }
        Integer entityIdBoxed = packet.getIntegers().read(0);
        if (entityIdBoxed == null) {
            return;
        }
        Player target = getById(entityIdBoxed.intValue());
        if (target == null || target == receiver) {
            return;
        }
        NClans plugin = NClans.getInstance();
        if (plugin == null) {
            return;
        }
        ClanManager clanManager = plugin.getClanManager();
        if (clanManager == null) {
            return;
        }
        Clan targetClan = clanManager.getPlayerClan(target);
        if (targetClan == null) {
            return;
        }
        Color glowColor = activeGlows.get(targetClan);
        if (glowColor == null) {
            return;
        }
        Clan receiverClan = clanManager.getPlayerClan(receiver);
        if (receiverClan != targetClan) {
            return;
        }

        ItemStack fakeChest = getOrCreateGlowChestplate(glowColor);
        List<Pair<EnumWrappers.ItemSlot, ItemStack>> updated = new ArrayList<>(pairs.size());
        for (int i = 0; i < pairs.size(); i++) {
            if (i == chestIdx) {
                updated.add(new Pair<>(EnumWrappers.ItemSlot.CHEST, fakeChest));
            } else {
                updated.add(pairs.get(i));
            }
        }

        PacketContainer replacement = ProtocolLibrary.getProtocolManager()
                .createPacket(PacketType.Play.Server.ENTITY_EQUIPMENT);
        replacement.getIntegers().write(0, entityIdBoxed);
        replacement.getSlotStackPairLists().write(0, updated);
        event.setPacket(replacement);
    }

    private static ItemStack getOrCreateGlowChestplate(Color color) {
        int rgb = color.asRGB();
        ItemStack cached = CHEST_BY_RGB.get(Integer.valueOf(rgb));
        if (cached != null) {
            return cached.clone();
        }
        ItemStack chest = new ItemStack(Material.LEATHER_CHESTPLATE);
        ItemMeta rawMeta = chest.getItemMeta();
        if (rawMeta instanceof LeatherArmorMeta) {
            LeatherArmorMeta meta = (LeatherArmorMeta) rawMeta;
            meta.setColor(color);
            chest.setItemMeta(meta);
        }
        NBTUtil.addItemNBT(chest, "clans_protocol", "");
        if (CHEST_BY_RGB.size() > 256) {
            CHEST_BY_RGB.clear();
        }
        CHEST_BY_RGB.put(Integer.valueOf(rgb), chest);
        return chest.clone();
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent event) {
        Player player = event.getPlayer();
        if (player != null) {
            ONLINE_BY_ID.put(Integer.valueOf(player.getEntityId()), player);
        }
    }

    @EventHandler
    public void onRespawn(PlayerRespawnEvent event) {
        Player player = event.getPlayer();
        if (player != null) {
            ONLINE_BY_ID.put(Integer.valueOf(player.getEntityId()), player);
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuit(PlayerQuitEvent event) {
        Player player = event.getPlayer();
        if (player == null) {
            return;
        }
        ONLINE_BY_ID.remove(Integer.valueOf(player.getEntityId()));
        ONLINE_BY_ID.values().removeIf(p -> p == player);
        playerArmorMap.remove(player);
        for (List<Player> seen : playerArmorMap.values()) {
            if (seen != null) {
                seen.remove(player);
            }
        }
    }

    @EventHandler
    public void onChunkUpdate(PlayerMoveEvent event) {
        Map<Clan, Color> activeGlows = GlowFunction.clansMap;
        if (activeGlows == null || activeGlows.isEmpty()) {
            return;
        }
        Location from = event.getFrom();
        Location to = event.getTo();
        if (from == null || to == null) {
            return;
        }
        // Only run when chunk coordinates or world actually change (never on mouse movement or sub-chunk steps!)
        if (from.getWorld() == to.getWorld()
                && (from.getBlockX() >> 4) == (to.getBlockX() >> 4)
                && (from.getBlockZ() >> 4) == (to.getBlockZ() >> 4)) {
            return;
        }
        Player player = event.getPlayer();
        if (player == null) {
            return;
        }
        ONLINE_BY_ID.put(Integer.valueOf(player.getEntityId()), player);
        playerArmorMap.remove(player);

        NClans plugin = NClans.getInstance();
        if (plugin == null) return;
        ClanManager clanManager = plugin.getClanManager();
        if (clanManager == null) return;
        Clan clan = clanManager.getPlayerClan(player);
        if (clan == null || activeGlows.get(clan) == null) {
            return;
        }
        if (to.getWorld() == null || !to.getWorld().isChunkLoaded(to.getBlockX() >> 4, to.getBlockZ() >> 4)) {
            return;
        }

        List<Player> seen = playerArmorMap.get(player);
        for (Entity entity : to.getChunk().getEntities()) {
            if (!(entity instanceof Player)) continue;
            Player other = (Player) entity;
            if (other == player) continue;
            if (clanManager.getPlayerClan(other) != clan) continue;
            if (seen != null && seen.contains(other)) continue;
            GlowManager.sendArmors(other, player, GlowManager.getItems(player));
            GlowManager.sendArmors(player, other, GlowManager.getItems(other));
            if (seen == null) {
                seen = new CopyOnWriteArrayList<>();
                playerArmorMap.put(player, seen);
            }
            seen.add(other);
        }
    }

    public static void removeGlow(Player player, Clan clan) {
        if (player != null) {
            playerArmorMap.remove(player);
        }
        GlowManager.removeArmorsForPlayer(player, clan);
    }

    public Player getById(int entityId) {
        Player cached = ONLINE_BY_ID.get(Integer.valueOf(entityId));
        if (cached != null) {
            if (cached.isOnline() && cached.getEntityId() == entityId) {
                return cached;
            }
            ONLINE_BY_ID.remove(Integer.valueOf(entityId), cached);
        }
        Collection<? extends Player> online = Bukkit.getOnlinePlayers();
        if (online != null) {
            for (Player p : online) {
                if (p != null && p.getEntityId() == entityId) {
                    ONLINE_BY_ID.put(Integer.valueOf(entityId), p);
                    return p;
                }
            }
        }
        return null;
    }
}
"""

ASM_PATCHER_JAVA = r"""
import java.nio.file.*;
import java.util.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;
import org.objectweb.asm.tree.analysis.*;
import org.objectweb.asm.util.*;

public class PatchLeakFixes {
    public static void main(String[] args) throws Exception {
        String mode = args[0];
        switch (mode) {
            case "nenderchest" -> patchNEnderChest(Path.of(args[1]));
            case "npvp" -> patchNPvp(Path.of(args[1]));
            case "irtp" -> patchIRandomTeleport(Path.of(args[1]), Path.of(args[2]), Path.of(args[3]));
            case "nfurnace" -> patchNFurnace(Path.of(args[1]), Path.of(args[2]));
            case "nclans" -> patchNClans(Path.of(args[1]), Path.of(args[2]), Path.of(args[3]));
            case "verify" -> {
                for (int i = 1; i < args.length; i++) {
                    verifyBytes(Files.readAllBytes(Path.of(args[i])));
                }
            }
            default -> throw new IllegalArgumentException("Unknown mode: " + mode);
        }
    }

    // 1. NEnderChest CheckCommand.<clinit>: HashMap -> ConcurrentHashMap
    private static void patchNEnderChest(Path checkCmdPath) throws Exception {
        ClassNode cn = readClass(checkCmdPath);
        replaceNewMapWithConcurrent(cn, "<clinit>");
        writeVerified(checkCmdPath, cn);
    }

    // 2. NPvp PvpSelect: add @EventHandler(MONITOR) onQuit(PlayerQuitEvent) + CopyOnWriteArrayList pvpPlayers
    private static void patchNPvp(Path pvpSelectPath) throws Exception {
        ClassNode cn = readClass(pvpSelectPath);
        for (MethodNode mn : cn.methods) {
            if ("<clinit>".equals(mn.name)) {
                for (AbstractInsnNode insn = mn.instructions.getFirst(); insn != null; insn = insn.getNext()) {
                    if (insn instanceof TypeInsnNode ti && ti.getOpcode() == Opcodes.NEW && "java/util/ArrayList".equals(ti.desc)) {
                        ti.desc = "java/util/concurrent/CopyOnWriteArrayList";
                    } else if (insn instanceof MethodInsnNode mi && mi.getOpcode() == Opcodes.INVOKESPECIAL
                            && "java/util/ArrayList".equals(mi.owner) && "<init>".equals(mi.name)) {
                        mi.owner = "java/util/concurrent/CopyOnWriteArrayList";
                    }
                }
            }
        }
        cn.methods.removeIf(m -> "onQuit".equals(m.name));
        MethodNode m = new MethodNode(Opcodes.ACC_PUBLIC, "onQuit", "(Lorg/bukkit/event/player/PlayerQuitEvent;)V", null, null);
        addMonitorEventHandler(m);
        LabelNode end = new LabelNode();
        m.instructions.add(new VarInsnNode(Opcodes.ALOAD, 1));
        m.instructions.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "org/bukkit/event/player/PlayerQuitEvent", "getPlayer", "()Lorg/bukkit/entity/Player;", false));
        m.instructions.add(new VarInsnNode(Opcodes.ASTORE, 2));
        m.instructions.add(new VarInsnNode(Opcodes.ALOAD, 2));
        m.instructions.add(new JumpInsnNode(Opcodes.IFNULL, end));
        m.instructions.add(new VarInsnNode(Opcodes.ALOAD, 0));
        m.instructions.add(new FieldInsnNode(Opcodes.GETFIELD, "wtf/n1zamu/pvp/event/PvpSelect", "headUtil", "Lwtf/n1zamu/pvp/util/PlayerHeadUtil;"));
        m.instructions.add(new VarInsnNode(Opcodes.ALOAD, 2));
        m.instructions.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "wtf/n1zamu/pvp/util/PlayerHeadUtil", "removeFromInventory", "(Lorg/bukkit/entity/Player;)V", false));
        m.instructions.add(end);
        m.instructions.add(new FrameNode(Opcodes.F_APPEND, 1, new Object[]{"org/bukkit/entity/Player"}, 0, null));
        m.instructions.add(new InsnNode(Opcodes.RETURN));
        m.maxStack = 2;
        m.maxLocals = 3;
        cn.methods.add(m);
        writeVerified(pvpSelectPath, cn);
    }

    // 3. IRandomTeleport: ChannelManager$1 quit/death/world-change cleanup + Channel$1/$2 String playerName instead of Player
    private static void patchIRandomTeleport(Path cm1Path, Path ch1Path, Path ch2Path) throws Exception {
        ClassNode cm1 = readClass(cm1Path);
        cm1.methods.removeIf(m -> "onQuit".equals(m.name) || "onDeath".equals(m.name) || "onWorldChange".equals(m.name));
        cm1.methods.add(makeChannelRemoveHandler("onQuit", "org/bukkit/event/player/PlayerQuitEvent", "getPlayer", "()Lorg/bukkit/entity/Player;"));
        cm1.methods.add(makeChannelRemoveHandler("onDeath", "org/bukkit/event/entity/PlayerDeathEvent", "getEntity", "()Lorg/bukkit/entity/Player;"));
        cm1.methods.add(makeChannelRemoveHandler("onWorldChange", "org/bukkit/event/player/PlayerChangedWorldEvent", "getPlayer", "()Lorg/bukkit/entity/Player;"));
        writeVerified(cm1Path, cm1);

        rewriteChannelCooldownTask(ch1Path, "com/ilyapurtov/channel/Channel$1");
        rewriteChannelCooldownTask(ch2Path, "com/ilyapurtov/channel/Channel$2");
    }

    private static MethodNode makeChannelRemoveHandler(String name, String eventInternal, String getterName, String getterDesc) {
        MethodNode m = new MethodNode(Opcodes.ACC_PUBLIC, name, "(L" + eventInternal + ";)V", null, null);
        addMonitorEventHandler(m);
        m.instructions.add(new VarInsnNode(Opcodes.ALOAD, 0));
        m.instructions.add(new FieldInsnNode(Opcodes.GETFIELD, "com/ilyapurtov/channel/ChannelManager$1", "this$0", "Lcom/ilyapurtov/channel/ChannelManager;"));
        m.instructions.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "com/ilyapurtov/channel/ChannelManager", "getTeleportingPlayers", "()Ljava/util/List;", false));
        m.instructions.add(new VarInsnNode(Opcodes.ALOAD, 1));
        m.instructions.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, eventInternal, getterName, getterDesc, false));
        m.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "java/util/List", "remove", "(Ljava/lang/Object;)Z", true));
        m.instructions.add(new InsnNode(Opcodes.POP));
        m.instructions.add(new InsnNode(Opcodes.RETURN));
        m.maxStack = 2;
        m.maxLocals = 2;
        return m;
    }

    private static void rewriteChannelCooldownTask(Path clsPath, String internalName) throws Exception {
        ClassNode cn = readClass(clsPath);
        cn.fields.clear();
        cn.fields.add(new FieldNode(Opcodes.ACC_FINAL | Opcodes.ACC_SYNTHETIC, "this$0", "Lcom/ilyapurtov/channel/Channel;", null, null));
        cn.fields.add(new FieldNode(Opcodes.ACC_FINAL | Opcodes.ACC_SYNTHETIC, "val$playerName", "Ljava/lang/String;", null, null));

        cn.methods.clear();
        // <init>(Channel, Player)V -> stores player.getName() as String (zero CraftPlayer strong ref!)
        MethodNode init = new MethodNode(0, "<init>", "(Lcom/ilyapurtov/channel/Channel;Lorg/bukkit/entity/Player;)V", null, null);
        init.instructions.add(new VarInsnNode(Opcodes.ALOAD, 0));
        init.instructions.add(new VarInsnNode(Opcodes.ALOAD, 1));
        init.instructions.add(new FieldInsnNode(Opcodes.PUTFIELD, internalName, "this$0", "Lcom/ilyapurtov/channel/Channel;"));
        init.instructions.add(new VarInsnNode(Opcodes.ALOAD, 0));
        init.instructions.add(new VarInsnNode(Opcodes.ALOAD, 2));
        init.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "org/bukkit/entity/Player", "getName", "()Ljava/lang/String;", true));
        init.instructions.add(new FieldInsnNode(Opcodes.PUTFIELD, internalName, "val$playerName", "Ljava/lang/String;"));
        init.instructions.add(new VarInsnNode(Opcodes.ALOAD, 0));
        init.instructions.add(new MethodInsnNode(Opcodes.INVOKESPECIAL, "org/bukkit/scheduler/BukkitRunnable", "<init>", "()V", false));
        init.instructions.add(new InsnNode(Opcodes.RETURN));
        init.maxStack = 2;
        init.maxLocals = 3;
        cn.methods.add(init);

        // run()V -> safe null/<=1 decrement + remove + cancel()
        MethodNode run = new MethodNode(Opcodes.ACC_PUBLIC, "run", "()V", null, null);
        LabelNode removeAndCancel = new LabelNode();
        LabelNode done = new LabelNode();

        run.instructions.add(new VarInsnNode(Opcodes.ALOAD, 0));
        run.instructions.add(new FieldInsnNode(Opcodes.GETFIELD, internalName, "this$0", "Lcom/ilyapurtov/channel/Channel;"));
        run.instructions.add(new MethodInsnNode(Opcodes.INVOKESTATIC, "com/ilyapurtov/channel/Channel", "access$000", "(Lcom/ilyapurtov/channel/Channel;)Ljava/util/Map;", false));
        run.instructions.add(new VarInsnNode(Opcodes.ASTORE, 1));

        run.instructions.add(new VarInsnNode(Opcodes.ALOAD, 1));
        run.instructions.add(new VarInsnNode(Opcodes.ALOAD, 0));
        run.instructions.add(new FieldInsnNode(Opcodes.GETFIELD, internalName, "val$playerName", "Ljava/lang/String;"));
        run.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "java/util/Map", "get", "(Ljava/lang/Object;)Ljava/lang/Object;", true));
        run.instructions.add(new TypeInsnNode(Opcodes.CHECKCAST, "java/lang/Integer"));
        run.instructions.add(new VarInsnNode(Opcodes.ASTORE, 2));

        run.instructions.add(new VarInsnNode(Opcodes.ALOAD, 2));
        run.instructions.add(new JumpInsnNode(Opcodes.IFNULL, removeAndCancel));
        run.instructions.add(new VarInsnNode(Opcodes.ALOAD, 2));
        run.instructions.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "java/lang/Integer", "intValue", "()I", false));
        run.instructions.add(new InsnNode(Opcodes.ICONST_1));
        run.instructions.add(new InsnNode(Opcodes.ISUB));
        run.instructions.add(new VarInsnNode(Opcodes.ISTORE, 3));
        run.instructions.add(new VarInsnNode(Opcodes.ILOAD, 3));
        run.instructions.add(new JumpInsnNode(Opcodes.IFLE, removeAndCancel));

        run.instructions.add(new VarInsnNode(Opcodes.ALOAD, 1));
        run.instructions.add(new VarInsnNode(Opcodes.ALOAD, 0));
        run.instructions.add(new FieldInsnNode(Opcodes.GETFIELD, internalName, "val$playerName", "Ljava/lang/String;"));
        run.instructions.add(new VarInsnNode(Opcodes.ILOAD, 3));
        run.instructions.add(new MethodInsnNode(Opcodes.INVOKESTATIC, "java/lang/Integer", "valueOf", "(I)Ljava/lang/Integer;", false));
        run.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "java/util/Map", "put", "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;", true));
        run.instructions.add(new InsnNode(Opcodes.POP));
        run.instructions.add(new JumpInsnNode(Opcodes.GOTO, done));

        run.instructions.add(removeAndCancel);
        run.instructions.add(new FrameNode(Opcodes.F_APPEND, 2, new Object[]{"java/util/Map", "java/lang/Integer"}, 0, null));
        run.instructions.add(new VarInsnNode(Opcodes.ALOAD, 1));
        run.instructions.add(new VarInsnNode(Opcodes.ALOAD, 0));
        run.instructions.add(new FieldInsnNode(Opcodes.GETFIELD, internalName, "val$playerName", "Ljava/lang/String;"));
        run.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "java/util/Map", "remove", "(Ljava/lang/Object;)Ljava/lang/Object;", true));
        run.instructions.add(new InsnNode(Opcodes.POP));
        run.instructions.add(new VarInsnNode(Opcodes.ALOAD, 0));
        run.instructions.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, internalName, "cancel", "()V", false));

        run.instructions.add(done);
        run.instructions.add(new FrameNode(Opcodes.F_SAME, 0, null, 0, null));
        run.instructions.add(new InsnNode(Opcodes.RETURN));
        run.maxStack = 3;
        run.maxLocals = 4;
        cn.methods.add(run);

        writeVerified(clsPath, cn);
    }

    // 4. NFurnace: add BlockBreakEvent cleanup + FurnaceBurnEvent / BrewingStandFuelEvent re-registration
    private static void patchNFurnace(Path furnInvPath, Path brewInvPath) throws Exception {
        ClassNode fn = readClass(furnInvPath);
        fn.methods.removeIf(m -> "onBreak".equals(m.name) || "onBurnRegister".equals(m.name));

        // onBreak(BlockBreakEvent): remove matching coordinates from FurnaceInventoryListener.furnaces
        MethodNode fBreak = new MethodNode(Opcodes.ACC_PUBLIC, "onBreak", "(Lorg/bukkit/event/block/BlockBreakEvent;)V", null, null);
        addMonitorEventHandler(fBreak);
        LabelNode fLoop = new LabelNode();
        LabelNode fDone = new LabelNode();
        LabelNode fRemove = new LabelNode();
        LabelNode fNext = new LabelNode();
        fBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 1));
        fBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "org/bukkit/event/block/BlockBreakEvent", "getBlock", "()Lorg/bukkit/block/Block;", false));
        fBreak.instructions.add(new VarInsnNode(Opcodes.ASTORE, 2));
        fBreak.instructions.add(new FieldInsnNode(Opcodes.GETSTATIC, "wtf/n1zamu/events/impl/listener/FurnaceInventoryListener", "furnaces", "Ljava/util/List;"));
        fBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "java/util/List", "iterator", "()Ljava/util/Iterator;", true));
        fBreak.instructions.add(new VarInsnNode(Opcodes.ASTORE, 3));
        fBreak.instructions.add(fLoop);
        fBreak.instructions.add(new FrameNode(Opcodes.F_APPEND, 2, new Object[]{"org/bukkit/block/Block", "java/util/Iterator"}, 0, null));
        fBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 3));
        fBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "java/util/Iterator", "hasNext", "()Z", true));
        fBreak.instructions.add(new JumpInsnNode(Opcodes.IFEQ, fDone));
        fBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 3));
        fBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "java/util/Iterator", "next", "()Ljava/lang/Object;", true));
        fBreak.instructions.add(new TypeInsnNode(Opcodes.CHECKCAST, "org/bukkit/block/Furnace"));
        fBreak.instructions.add(new VarInsnNode(Opcodes.ASTORE, 4));
        fBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 4));
        fBreak.instructions.add(new JumpInsnNode(Opcodes.IFNULL, fRemove));
        fBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 4));
        fBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "org/bukkit/block/Furnace", "getX", "()I", true));
        fBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 2));
        fBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "org/bukkit/block/Block", "getX", "()I", true));
        fBreak.instructions.add(new JumpInsnNode(Opcodes.IF_ICMPNE, fNext));
        fBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 4));
        fBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "org/bukkit/block/Furnace", "getY", "()I", true));
        fBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 2));
        fBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "org/bukkit/block/Block", "getY", "()I", true));
        fBreak.instructions.add(new JumpInsnNode(Opcodes.IF_ICMPNE, fNext));
        fBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 4));
        fBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "org/bukkit/block/Furnace", "getZ", "()I", true));
        fBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 2));
        fBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "org/bukkit/block/Block", "getZ", "()I", true));
        fBreak.instructions.add(new JumpInsnNode(Opcodes.IF_ICMPNE, fNext));
        fBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 4));
        fBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "org/bukkit/block/Furnace", "getWorld", "()Lorg/bukkit/World;", true));
        fBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 2));
        fBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "org/bukkit/block/Block", "getWorld", "()Lorg/bukkit/World;", true));
        fBreak.instructions.add(new JumpInsnNode(Opcodes.IF_ACMPNE, fNext));
        fBreak.instructions.add(fRemove);
        fBreak.instructions.add(new FrameNode(Opcodes.F_APPEND, 1, new Object[]{"org/bukkit/block/Furnace"}, 0, null));
        fBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 3));
        fBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "java/util/Iterator", "remove", "()V", true));
        fBreak.instructions.add(fNext);
        fBreak.instructions.add(new FrameNode(Opcodes.F_CHOP, 1, null, 0, null));
        fBreak.instructions.add(new JumpInsnNode(Opcodes.GOTO, fLoop));
        fBreak.instructions.add(fDone);
        fBreak.instructions.add(new FrameNode(Opcodes.F_CHOP, 2, null, 0, null));
        fBreak.instructions.add(new InsnNode(Opcodes.RETURN));
        fBreak.maxStack = 2;
        fBreak.maxLocals = 5;
        fn.methods.add(fBreak);
        writeVerified(furnInvPath, fn);

        ClassNode bn = readClass(brewInvPath);
        bn.methods.removeIf(m -> "onBreak".equals(m.name));
        MethodNode bBreak = new MethodNode(Opcodes.ACC_PUBLIC, "onBreak", "(Lorg/bukkit/event/block/BlockBreakEvent;)V", null, null);
        addMonitorEventHandler(bBreak);
        LabelNode bLoop = new LabelNode();
        LabelNode bDone = new LabelNode();
        LabelNode bRemove = new LabelNode();
        LabelNode bNext = new LabelNode();
        bBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 1));
        bBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "org/bukkit/event/block/BlockBreakEvent", "getBlock", "()Lorg/bukkit/block/Block;", false));
        bBreak.instructions.add(new VarInsnNode(Opcodes.ASTORE, 2));
        bBreak.instructions.add(new FieldInsnNode(Opcodes.GETSTATIC, "wtf/n1zamu/events/impl/listener/BrewingStandInventoryListener", "brewingStands", "Ljava/util/List;"));
        bBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "java/util/List", "iterator", "()Ljava/util/Iterator;", true));
        bBreak.instructions.add(new VarInsnNode(Opcodes.ASTORE, 3));
        bBreak.instructions.add(bLoop);
        bBreak.instructions.add(new FrameNode(Opcodes.F_APPEND, 2, new Object[]{"org/bukkit/block/Block", "java/util/Iterator"}, 0, null));
        bBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 3));
        bBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "java/util/Iterator", "hasNext", "()Z", true));
        bBreak.instructions.add(new JumpInsnNode(Opcodes.IFEQ, bDone));
        bBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 3));
        bBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "java/util/Iterator", "next", "()Ljava/lang/Object;", true));
        bBreak.instructions.add(new TypeInsnNode(Opcodes.CHECKCAST, "org/bukkit/inventory/BrewerInventory"));
        bBreak.instructions.add(new VarInsnNode(Opcodes.ASTORE, 4));
        bBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 4));
        bBreak.instructions.add(new JumpInsnNode(Opcodes.IFNULL, bRemove));
        bBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 4));
        bBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "org/bukkit/inventory/BrewerInventory", "getLocation", "()Lorg/bukkit/Location;", true));
        bBreak.instructions.add(new VarInsnNode(Opcodes.ASTORE, 5));
        bBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 5));
        bBreak.instructions.add(new JumpInsnNode(Opcodes.IFNULL, bRemove));
        bBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 5));
        bBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "org/bukkit/Location", "getBlockX", "()I", false));
        bBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 2));
        bBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "org/bukkit/block/Block", "getX", "()I", true));
        bBreak.instructions.add(new JumpInsnNode(Opcodes.IF_ICMPNE, bNext));
        bBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 5));
        bBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "org/bukkit/Location", "getBlockY", "()I", false));
        bBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 2));
        bBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "org/bukkit/block/Block", "getY", "()I", true));
        bBreak.instructions.add(new JumpInsnNode(Opcodes.IF_ICMPNE, bNext));
        bBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 5));
        bBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "org/bukkit/Location", "getBlockZ", "()I", false));
        bBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 2));
        bBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "org/bukkit/block/Block", "getZ", "()I", true));
        bBreak.instructions.add(new JumpInsnNode(Opcodes.IF_ICMPNE, bNext));
        bBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 5));
        bBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "org/bukkit/Location", "getWorld", "()Lorg/bukkit/World;", false));
        bBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 2));
        bBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "org/bukkit/block/Block", "getWorld", "()Lorg/bukkit/World;", true));
        bBreak.instructions.add(new JumpInsnNode(Opcodes.IF_ACMPNE, bNext));
        bBreak.instructions.add(bRemove);
        bBreak.instructions.add(new FrameNode(Opcodes.F_APPEND, 1, new Object[]{"org/bukkit/inventory/BrewerInventory"}, 0, null));
        bBreak.instructions.add(new VarInsnNode(Opcodes.ALOAD, 3));
        bBreak.instructions.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "java/util/Iterator", "remove", "()V", true));
        bBreak.instructions.add(bNext);
        bBreak.instructions.add(new FrameNode(Opcodes.F_CHOP, 1, null, 0, null));
        bBreak.instructions.add(new JumpInsnNode(Opcodes.GOTO, bLoop));
        bBreak.instructions.add(bDone);
        bBreak.instructions.add(new FrameNode(Opcodes.F_CHOP, 2, null, 0, null));
        bBreak.instructions.add(new InsnNode(Opcodes.RETURN));
        bBreak.maxStack = 2;
        bBreak.maxLocals = 6;
        bn.methods.add(bBreak);
        writeVerified(brewInvPath, bn);
    }

    // 5. NClans: GlowFunction.<clinit> ConcurrentHashMap, GlowManager.sendArmors(..., false), QuestListener.lastBrewer cleanup
    private static void patchNClans(Path glowFnPath, Path glowMgrPath, Path questListenerPath) throws Exception {
        ClassNode gf = readClass(glowFnPath);
        replaceNewMapWithConcurrent(gf, "<clinit>");
        writeVerified(glowFnPath, gf);

        ClassNode gm = readClass(glowMgrPath);
        int sendPatched = 0;
        for (MethodNode mn : gm.methods) {
            if ("sendArmors".equals(mn.name) && "(Lorg/bukkit/entity/Player;Lorg/bukkit/entity/Player;Ljava/util/List;)V".equals(mn.desc)) {
                for (AbstractInsnNode insn = mn.instructions.getFirst(); insn != null; insn = insn.getNext()) {
                    if (insn instanceof MethodInsnNode mi
                            && "com/comphenix/protocol/ProtocolManager".equals(mi.owner)
                            && "sendServerPacket".equals(mi.name)) {
                        if ("(Lorg/bukkit/entity/Player;Lcom/comphenix/protocol/events/PacketContainer;)V".equals(mi.desc)) {
                            mn.instructions.insertBefore(mi, new InsnNode(Opcodes.ICONST_0));
                            mi.desc = "(Lorg/bukkit/entity/Player;Lcom/comphenix/protocol/events/PacketContainer;Z)V";
                            mn.maxStack = Math.max(mn.maxStack, 4);
                        }
                        sendPatched++;
                    }
                }
            }
        }
        if (sendPatched != 1) throw new IllegalStateException("Expected 1 sendServerPacket in GlowManager, got " + sendPatched);
        writeVerified(glowMgrPath, gm);

        ClassNode ql = readClass(questListenerPath);
        boolean patchedBreak = false;
        boolean patchedOpen = false;
        for (MethodNode mn : ql.methods) {
            if ("onBreak".equals(mn.name) && "(Lorg/bukkit/event/block/BlockBreakEvent;)V".equals(mn.desc)) {
                // Idempotency check
                boolean already = false;
                for (AbstractInsnNode i = mn.instructions.getFirst(); i != null; i = i.getNext()) {
                    if (i instanceof FieldInsnNode fi && "lastBrewer".equals(fi.name)) { already = true; break; }
                }
                if (!already) {
                    InsnList pre = new InsnList();
                    pre.add(new VarInsnNode(Opcodes.ALOAD, 0));
                    pre.add(new FieldInsnNode(Opcodes.GETFIELD, "wtf/n1zamu/quest/QuestListener", "lastBrewer", "Ljava/util/Map;"));
                    pre.add(new VarInsnNode(Opcodes.ALOAD, 1));
                    pre.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "org/bukkit/event/block/BlockBreakEvent", "getBlock", "()Lorg/bukkit/block/Block;", false));
                    pre.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "org/bukkit/block/Block", "getLocation", "()Lorg/bukkit/Location;", true));
                    pre.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "java/util/Map", "remove", "(Ljava/lang/Object;)Ljava/lang/Object;", true));
                    pre.add(new InsnNode(Opcodes.POP));
                    mn.instructions.insert(pre);
                    mn.maxStack = Math.max(mn.maxStack, 4);
                }
                patchedBreak = true;
            } else if ("onBrewingOpen".equals(mn.name) && "(Lorg/bukkit/event/inventory/InventoryOpenEvent;)V".equals(mn.desc)) {
                boolean already = false;
                for (AbstractInsnNode i = mn.instructions.getFirst(); i != null; i = i.getNext()) {
                    if (i instanceof IntInsnNode ii && ii.operand == 512) { already = true; break; }
                }
                if (!already) {
                    // Insert right before Map.put in onBrewingOpen: if (this.lastBrewer.size() > 512) this.lastBrewer.clear();
                    for (AbstractInsnNode i = mn.instructions.getFirst(); i != null; i = i.getNext()) {
                        if (i instanceof FieldInsnNode fi && "lastBrewer".equals(fi.name)) {
                            LabelNode skipClear = new LabelNode();
                            InsnList cap = new InsnList();
                            cap.add(new VarInsnNode(Opcodes.ALOAD, 0));
                            cap.add(new FieldInsnNode(Opcodes.GETFIELD, "wtf/n1zamu/quest/QuestListener", "lastBrewer", "Ljava/util/Map;"));
                            cap.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "java/util/Map", "size", "()I", true));
                            cap.add(new IntInsnNode(Opcodes.SIPUSH, 512));
                            cap.add(new JumpInsnNode(Opcodes.IF_ICMPLE, skipClear));
                            cap.add(new VarInsnNode(Opcodes.ALOAD, 0));
                            cap.add(new FieldInsnNode(Opcodes.GETFIELD, "wtf/n1zamu/quest/QuestListener", "lastBrewer", "Ljava/util/Map;"));
                            cap.add(new MethodInsnNode(Opcodes.INVOKEINTERFACE, "java/util/Map", "clear", "()V", true));
                            cap.add(skipClear);
                            // Frame at fi.getPrevious() (ALOAD 0 before GETFIELD lastBrewer): [this, event, brewerInventory, brewingStand]
                            cap.add(new FrameNode(Opcodes.F_APPEND, 2, new Object[]{
                                    "org/bukkit/inventory/BrewerInventory", "org/bukkit/block/BrewingStand"}, 0, null));
                            mn.instructions.insertBefore(fi.getPrevious(), cap);
                            // Update downstream L1 frame from F_SAME to F_CHOP 2 since we introduced a frame inside the if block!
                            for (AbstractInsnNode j = fi; j != null; j = j.getNext()) {
                                if (j instanceof FrameNode fn && fn.type == Opcodes.F_SAME) {
                                    fn.type = Opcodes.F_CHOP;
                                    fn.local = Arrays.asList(new Object[2]);
                                    fn.local = null;
                                    // In ASM Tree API, F_CHOP uses fn.local = null? Wait: in ASM FrameNode, F_CHOP takes count in `numLocal` constructor!
                                    mn.instructions.set(j, new FrameNode(Opcodes.F_CHOP, 2, null, 0, null));
                                    break;
                                }
                            }
                            mn.maxStack = Math.max(mn.maxStack, 4);
                            break;
                        }
                    }
                }
                patchedOpen = true;
            }
        }
        if (!patchedBreak || !patchedOpen) {
            throw new IllegalStateException("QuestListener patch missing handler: break=" + patchedBreak + " open=" + patchedOpen);
        }
        writeVerified(questListenerPath, ql);
    }

    private static void addMonitorEventHandler(MethodNode m) {
        AnnotationNode ann = new AnnotationNode("Lorg/bukkit/event/EventHandler;");
        ann.values = new ArrayList<>();
        ann.values.add("priority");
        ann.values.add(new String[]{"Lorg/bukkit/event/EventPriority;", "MONITOR"});
        ann.values.add("ignoreCancelled");
        ann.values.add(Boolean.TRUE);
        m.visibleAnnotations = new ArrayList<>();
        m.visibleAnnotations.add(ann);
    }

    private static void replaceNewMapWithConcurrent(ClassNode cn, String methodName) {
        int count = 0;
        for (MethodNode mn : cn.methods) {
            if (!methodName.equals(mn.name)) continue;
            for (AbstractInsnNode insn = mn.instructions.getFirst(); insn != null; insn = insn.getNext()) {
                if (insn instanceof TypeInsnNode ti && ti.getOpcode() == Opcodes.NEW
                        && ("java/util/HashMap".equals(ti.desc) || "java/util/concurrent/ConcurrentHashMap".equals(ti.desc))) {
                    ti.desc = "java/util/concurrent/ConcurrentHashMap";
                    count++;
                } else if (insn instanceof MethodInsnNode mi && mi.getOpcode() == Opcodes.INVOKESPECIAL
                        && ("java/util/HashMap".equals(mi.owner) || "java/util/concurrent/ConcurrentHashMap".equals(mi.owner))
                        && "<init>".equals(mi.name)) {
                    mi.owner = "java/util/concurrent/ConcurrentHashMap";
                }
            }
        }
        if (count < 1) throw new IllegalStateException("Expected HashMap/ConcurrentHashMap in " + cn.name + "." + methodName);
    }

    private static ClassNode readClass(Path p) throws Exception {
        ClassReader cr = new ClassReader(Files.readAllBytes(p));
        ClassNode cn = new ClassNode();
        cr.accept(cn, 0);
        return cn;
    }

    private static void writeVerified(Path p, ClassNode cn) throws Exception {
        ClassWriter cw = new ClassWriter(0);
        cn.accept(cw);
        byte[] bytes = cw.toByteArray();
        verifyBytes(bytes);
        Files.write(p, bytes);
    }

    private static void verifyBytes(byte[] bytes) throws Exception {
        ClassReader cr = new ClassReader(bytes);
        cr.accept(new CheckClassAdapter(new ClassWriter(0), true), ClassReader.EXPAND_FRAMES);
        ClassNode cn = new ClassNode();
        cr.accept(cn, 0);
        Analyzer<BasicValue> analyzer = new Analyzer<>(new BasicVerifier());
        for (MethodNode mn : cn.methods) {
            analyzer.analyze(cn.name, mn);
        }
    }
}
"""

VERIFY_LOADER_JAVA = r"""
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Path;

public class VerifyStrictLoad {
    public static void main(String[] args) throws Exception {
        String[] cpEntries = args[0].split(java.io.File.pathSeparator);
        URL[] urls = new URL[cpEntries.length];
        for (int i = 0; i < cpEntries.length; i++) {
            urls[i] = Path.of(cpEntries[i]).toUri().toURL();
        }
        try (URLClassLoader loader = new URLClassLoader(urls, ClassLoader.getPlatformClassLoader())) {
            for (int i = 1; i < args.length; i++) {
                Class<?> cls = Class.forName(args[i], false, loader);
                Method[] methods = cls.getDeclaredMethods();
                Field[] fields = cls.getDeclaredFields();
                System.out.println("  [OK -Xverify:all] " + cls.getName() + " (methods=" + methods.length + ", fields=" + fields.length + ")");
            }
        }
    }
}
"""


def replace_jar_entries(jar_path: Path, replacements: dict[str, bytes], strip_pred=None):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jar") as tf:
        out_path = Path(tf.name)
    try:
        written = set()
        with zipfile.ZipFile(jar_path, "r") as src, zipfile.ZipFile(out_path, "w") as dst:
            for info in src.infolist():
                if strip_pred and strip_pred(info.filename):
                    continue
                if info.filename in replacements:
                    zinfo = zipfile.ZipInfo(info.filename, info.date_time)
                    zinfo.compress_type = zipfile.ZIP_DEFLATED
                    dst.writestr(zinfo, replacements[info.filename])
                    written.add(info.filename)
                else:
                    dst.writestr(info, src.read(info.filename))
            for name, data in replacements.items():
                if name not in written:
                    zinfo = zipfile.ZipInfo(name, (2026, 10, 27, 0, 0, 0))
                    zinfo.compress_type = zipfile.ZIP_DEFLATED
                    dst.writestr(zinfo, data)
        with zipfile.ZipFile(out_path, "r") as check_zf:
            assert check_zf.testzip() is None
        shutil.move(str(out_path), str(jar_path))
        print(f"Updated {jar_path.relative_to(ROOT)}: {hashlib.sha256(jar_path.read_bytes()).hexdigest()}")
    finally:
        out_path.unlink(missing_ok=True)


def compile_java(ecj_target: str, classpath: list[Path], out_dir: Path, src_files: list[Path]):
    out_dir.mkdir(parents=True, exist_ok=True)
    cp = os.pathsep.join(str(p) for p in classpath)
    subprocess.run(
        [JAVA, "-jar", ECJ, ecj_target, "-encoding", "UTF-8", "-proc:none", "-cp", cp, "-d", str(out_dir), *[str(s) for s in src_files]],
        check=True,
    )


def main():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # 0. Compile Bukkit API stubs + ASM patcher + strict -Xverify:all classloader verifier
        stubs_src = tmp / "stubs_src"
        stubs_cls = tmp / "stubs_cls"
        stub_files = []
        for rel, code in STUBS.items():
            p = stubs_src / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(code.strip() + "\n", encoding="utf-8")
            stub_files.append(p)
        compile_java("-17", [BLIB_JAR], stubs_cls, stub_files)

        tools_cls = tmp / "tools_cls"
        (tmp / "PatchLeakFixes.java").write_text(ASM_PATCHER_JAVA, encoding="utf-8")
        (tmp / "VerifyStrictLoad.java").write_text(VERIFY_LOADER_JAVA, encoding="utf-8")
        compile_java("-21", [BLIB_JAR], tools_cls, [tmp / "PatchLeakFixes.java", tmp / "VerifyStrictLoad.java"])
        patcher_cp = f"{tools_cls}:{BLIB_JAR}"

        # 1. NEnderChest-1.jar
        nec_jar = ROOT / "plugins/NEnderChest-1.jar"
        nec_src = tmp / "nec_src/wtf/n1zamu/listener/InventoryCloseListener.java"
        nec_src.parent.mkdir(parents=True, exist_ok=True)
        nec_src.write_text(NENDERCHEST_CLOSE_SRC.strip() + "\n", encoding="utf-8")
        nec_cls = tmp / "nec_cls"
        compile_java("-8", [stubs_cls, nec_jar], nec_cls, [nec_src])

        check_cmd_cls = tmp / "CheckCommand.class"
        with zipfile.ZipFile(nec_jar, "r") as zf:
            check_cmd_cls.write_bytes(zf.read("wtf/n1zamu/command/impl/CheckCommand.class"))
        subprocess.run([JAVA, "-Xverify:all", "-cp", patcher_cp, "PatchLeakFixes", "nenderchest", str(check_cmd_cls)], check=True)
        subprocess.run([JAVA, "-Xverify:all", "-cp", patcher_cp, "PatchLeakFixes", "verify",
                        str(nec_cls / "wtf/n1zamu/listener/InventoryCloseListener.class")], check=True)
        replace_jar_entries(nec_jar, {
            "wtf/n1zamu/listener/InventoryCloseListener.class": (nec_cls / "wtf/n1zamu/listener/InventoryCloseListener.class").read_bytes(),
            "wtf/n1zamu/command/impl/CheckCommand.class": check_cmd_cls.read_bytes(),
        })
        subprocess.run([JAVA, "-Xverify:all", "-cp", str(tools_cls), "VerifyStrictLoad",
                        f"{nec_jar}:{stubs_cls}",
                        "wtf.n1zamu.listener.InventoryCloseListener",
                        "wtf.n1zamu.command.impl.CheckCommand"], check=True)

        # 2. NPvp-1.0.jar
        npvp_jar = ROOT / "plugins/NPvp-1.0.jar"
        pvp_select_cls = tmp / "PvpSelect.class"
        with zipfile.ZipFile(npvp_jar, "r") as zf:
            pvp_select_cls.write_bytes(zf.read("wtf/n1zamu/pvp/event/PvpSelect.class"))
        subprocess.run([JAVA, "-Xverify:all", "-cp", patcher_cp, "PatchLeakFixes", "npvp", str(pvp_select_cls)], check=True)
        replace_jar_entries(npvp_jar, {
            "wtf/n1zamu/pvp/event/PvpSelect.class": pvp_select_cls.read_bytes(),
        })
        subprocess.run([JAVA, "-Xverify:all", "-cp", str(tools_cls), "VerifyStrictLoad",
                        f"{npvp_jar}:{stubs_cls}",
                        "wtf.n1zamu.pvp.event.PvpSelect"], check=True)

        # 3. IRandomTeleport.jar
        irtp_jar = ROOT / "plugins/IRandomTeleport.jar"
        cm1_cls = tmp / "ChannelManager$1.class"
        ch1_cls = tmp / "Channel$1.class"
        ch2_cls = tmp / "Channel$2.class"
        with zipfile.ZipFile(irtp_jar, "r") as zf:
            cm1_cls.write_bytes(zf.read("com/ilyapurtov/channel/ChannelManager$1.class"))
            ch1_cls.write_bytes(zf.read("com/ilyapurtov/channel/Channel$1.class"))
            ch2_cls.write_bytes(zf.read("com/ilyapurtov/channel/Channel$2.class"))
        subprocess.run([JAVA, "-Xverify:all", "-cp", patcher_cp, "PatchLeakFixes", "irtp",
                        str(cm1_cls), str(ch1_cls), str(ch2_cls)], check=True)
        replace_jar_entries(
            irtp_jar,
            {
                "com/ilyapurtov/channel/ChannelManager$1.class": cm1_cls.read_bytes(),
                "com/ilyapurtov/channel/Channel$1.class": ch1_cls.read_bytes(),
                "com/ilyapurtov/channel/Channel$2.class": ch2_cls.read_bytes(),
            },
            strip_pred=lambda name: name.startswith("org/bukkit/"),
        )
        subprocess.run([JAVA, "-Xverify:all", "-cp", str(tools_cls), "VerifyStrictLoad",
                        f"{irtp_jar}:{stubs_cls}",
                        "com.ilyapurtov.channel.ChannelManager$1",
                        "com.ilyapurtov.channel.Channel$1",
                        "com.ilyapurtov.channel.Channel$2"], check=True)

        # 4. NFurnace-1.jar
        nf_jar = ROOT / "plugins/NFurnace-1.jar"
        nf_src_dir = tmp / "nf_src/wtf/n1zamu/events/impl"
        nf_src_dir.mkdir(parents=True, exist_ok=True)
        (nf_src_dir / "SmeltStartEvent.java").write_text(NFURNACE_SMELT_SRC.strip() + "\n", encoding="utf-8")
        (nf_src_dir / "BrewStartEvent.java").write_text(NFURNACE_BREW_SRC.strip() + "\n", encoding="utf-8")
        nf_cls = tmp / "nf_cls"
        compile_java("-8", [stubs_cls, nf_jar], nf_cls, [nf_src_dir / "SmeltStartEvent.java", nf_src_dir / "BrewStartEvent.java"])

        furn_inv_cls = tmp / "FurnaceInventoryListener.class"
        brew_inv_cls = tmp / "BrewingStandInventoryListener.class"
        with zipfile.ZipFile(nf_jar, "r") as zf:
            furn_inv_cls.write_bytes(zf.read("wtf/n1zamu/events/impl/listener/FurnaceInventoryListener.class"))
            brew_inv_cls.write_bytes(zf.read("wtf/n1zamu/events/impl/listener/BrewingStandInventoryListener.class"))
        subprocess.run([JAVA, "-Xverify:all", "-cp", patcher_cp, "PatchLeakFixes", "nfurnace",
                        str(furn_inv_cls), str(brew_inv_cls)], check=True)
        nf_replacements = {
            "wtf/n1zamu/events/impl/listener/FurnaceInventoryListener.class": furn_inv_cls.read_bytes(),
            "wtf/n1zamu/events/impl/listener/BrewingStandInventoryListener.class": brew_inv_cls.read_bytes(),
        }
        for p in (nf_cls / "wtf/n1zamu/events/impl").glob("*.class"):
            subprocess.run([JAVA, "-Xverify:all", "-cp", patcher_cp, "PatchLeakFixes", "verify", str(p)], check=True)
            nf_replacements[f"wtf/n1zamu/events/impl/{p.name}"] = p.read_bytes()
        replace_jar_entries(nf_jar, nf_replacements)
        subprocess.run([JAVA, "-Xverify:all", "-cp", str(tools_cls), "VerifyStrictLoad",
                        f"{nf_jar}:{stubs_cls}",
                        "wtf.n1zamu.events.impl.SmeltStartEvent",
                        "wtf.n1zamu.events.impl.BrewStartEvent",
                        "wtf.n1zamu.events.impl.listener.FurnaceInventoryListener",
                        "wtf.n1zamu.events.impl.listener.BrewingStandInventoryListener"], check=True)

        # 5. NClans-1.jar
        nc_jar = ROOT / "plugins/NClans-1.jar"
        nc_src = tmp / "nc_src/wtf/n1zamu/function/impl/glow/GlowListener.java"
        nc_src.parent.mkdir(parents=True, exist_ok=True)
        nc_src.write_text(NCLANS_GLOW_LISTENER_SRC.strip() + "\n", encoding="utf-8")
        nc_cls = tmp / "nc_cls"
        compile_java("-21", [stubs_cls, PLIB_JAR, nc_jar], nc_cls, [nc_src])

        glow_fn_cls = tmp / "GlowFunction.class"
        glow_mgr_cls = tmp / "GlowManager.class"
        quest_cls = tmp / "QuestListener.class"
        with zipfile.ZipFile(nc_jar, "r") as zf:
            glow_fn_cls.write_bytes(zf.read("wtf/n1zamu/function/impl/glow/GlowFunction.class"))
            glow_mgr_cls.write_bytes(zf.read("wtf/n1zamu/function/impl/glow/GlowManager.class"))
            quest_cls.write_bytes(zf.read("wtf/n1zamu/quest/QuestListener.class"))
        subprocess.run([JAVA, "-Xverify:all", "-cp", patcher_cp, "PatchLeakFixes", "nclans",
                        str(glow_fn_cls), str(glow_mgr_cls), str(quest_cls)], check=True)

        nc_replacements = {
            "wtf/n1zamu/function/impl/glow/GlowFunction.class": glow_fn_cls.read_bytes(),
            "wtf/n1zamu/function/impl/glow/GlowManager.class": glow_mgr_cls.read_bytes(),
            "wtf/n1zamu/quest/QuestListener.class": quest_cls.read_bytes(),
        }
        for p in (nc_cls / "wtf/n1zamu/function/impl/glow").glob("GlowListener*.class"):
            subprocess.run([JAVA, "-Xverify:all", "-cp", patcher_cp, "PatchLeakFixes", "verify", str(p)], check=True)
            nc_replacements[f"wtf/n1zamu/function/impl/glow/{p.name}"] = p.read_bytes()
        replace_jar_entries(nc_jar, nc_replacements)
        subprocess.run([JAVA, "-Xverify:all", "-cp", str(tools_cls), "VerifyStrictLoad",
                        f"{nc_jar}:{PLIB_JAR}:{stubs_cls}",
                        "wtf.n1zamu.function.impl.glow.GlowListener",
                        "wtf.n1zamu.function.impl.glow.GlowFunction",
                        "wtf.n1zamu.function.impl.glow.GlowManager",
                        "wtf.n1zamu.quest.QuestListener"], check=True)

        print("ALL 5 PLUGIN JARS PATCHED & STRICTLY VERIFIED (-Xverify:all)!")


if __name__ == "__main__":
    main()
