#!/usr/bin/env python3
"""
Reproducible build + strict JVM (-Xverify:all) verification suite for Elytrix 5-point bugfix batch:
  1. plugins/hJobs.jar          — SQLite WAL, thread-safe lock, PlayerJoin preload, sync lazy-load fallback, monotonic MAX(sold_total) UPSERT, GUI-sale autosave
  3. plugins/NClans-1.jar       — Forbid manual color/HEX codes in clan names, sanitize legacy clans.yml names, enforce level-only colors, O(1) LevelConfiguration cache
  4. plugins/ElytrixGodPickup.jar (v2.0.0) — Complete /god (/egod, /godmode, /tgm, /ungod, API) action lockdown + 5,000 ms post-god cooldown + anti-bypass
  5. plugins/GreatCombat-1.9.jar — Non-disabling ItemUtils.decodeWithFallback + default:false bypass permissions + fair OP/* PvP item cooldowns
"""
import base64
import gzip
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
GOD_DIR = ROOT / "tools/god-fix"

JAVA = os.environ.get("JAVA", "/tmp/pytools/jdk4py/java-runtime/bin/java")
ECJ = os.environ.get("ECJ", "/tmp/pytools/ecj-3.46.100.jar")

STUBS = {
    "org/bukkit/Bukkit.java": """
package org.bukkit;
import java.util.Collection;
import java.util.Collections;
import java.util.UUID;
import org.bukkit.entity.Player;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.plugin.PluginManager;
import org.bukkit.scheduler.BukkitScheduler;
public final class Bukkit {
    private static final Server SERVER = new Server() {};
    public static Server getServer() { return SERVER; }
    public static PluginManager getPluginManager() { return null; }
    public static BukkitScheduler getScheduler() { return null; }
    public static Collection<? extends Player> getOnlinePlayers() { return Collections.emptyList(); }
    public static Player getPlayer(String name) { return null; }
    public static Player getPlayer(UUID id) { return null; }
    public static World getWorld(String name) { return null; }
    public static org.bukkit.command.PluginCommand getPluginCommand(String name) { return null; }
    public static Inventory createInventory(InventoryHolder owner, int size, String title) { return null; }
}
""",
    "org/bukkit/GameMode.java": """
package org.bukkit;
public enum GameMode { CREATIVE, SURVIVAL, ADVENTURE, SPECTATOR }
""",
    "org/bukkit/Chunk.java": """
package org.bukkit;
import org.bukkit.plugin.Plugin;
public interface Chunk {
    boolean addPluginChunkTicket(Plugin plugin);
    boolean removePluginChunkTicket(Plugin plugin);
}
""",
    "org/bukkit/Server.java": """
package org.bukkit;
import org.bukkit.plugin.PluginManager;
import org.bukkit.plugin.ServicesManager;
public interface Server {
    default boolean isPrimaryThread() { return true; }
    default PluginManager getPluginManager() { return null; }
    default ServicesManager getServicesManager() { return null; }
}
""",
    "org/bukkit/World.java": """
package org.bukkit;
import java.util.concurrent.CompletableFuture;
import org.bukkit.entity.Item;
import org.bukkit.metadata.Metadatable;
import org.bukkit.inventory.ItemStack;
public interface World extends Metadatable {
    String getName();
    Item dropItemNaturally(Location loc, ItemStack item);
    boolean isChunkLoaded(int x, int z);
    Chunk getChunkAt(int x, int z);
    CompletableFuture<Chunk> getChunkAtAsync(int x, int z);
}
""",
    "org/bukkit/Location.java": """
package org.bukkit;
public class Location implements Cloneable {
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
    public double distanceSquared(Location o) {
        double dx = x - o.x, dy = y - o.y, dz = z - o.z;
        return dx * dx + dy * dy + dz * dz;
    }
    @Override public Location clone() { return new Location(world, x, y, z); }
}
""",
    "org/bukkit/Material.java": """
package org.bukkit;
public enum Material {
    AIR, STONE, COBBLESTONE, IRON_ORE, IRON_INGOT, GOLD_ORE, GOLD_INGOT, REDSTONE_ORE, REDSTONE,
    EMERALD_ORE, EMERALD, DIAMOND_ORE, DIAMOND, LAPIS_ORE, LAPIS_LAZULI, COAL_ORE, COAL,
    WHEAT, CARROT, POTATO, BEETROOT, MELON, MELON_SLICE, PUMPKIN, COD, SALMON, PUFFERFISH,
    TROPICAL_FISH, SNOW_BLOCK, SNOW, SNOWBALL, PLAYER_HEAD, GOLDEN_APPLE, ENCHANTED_GOLDEN_APPLE,
    ENDER_PEARL, ENDER_EYE, CHORUS_FRUIT, FIREWORK_ROCKET, END_CRYSTAL, EXPERIENCE_BOTTLE,
    POTION, SPLASH_POTION, LINGERING_POTION, WIND_CHARGE, EGG, TRIDENT, SHIELD, ELYTRA,
    ENCHANTED_BOOK, FISHING_ROD, NETHERITE_PICKAXE, NETHERITE_AXE, NETHERITE_SWORD,
    CHEST, TRAPPED_CHEST, BARREL, SHULKER_BOX, FURNACE, BLAST_FURNACE, SMOKER, HOPPER,
    DISPENSER, DROPPER, BREWING_STAND, LECTERN, CHISELED_BOOKSHELF, DECORATED_POT, CRAFTER,
    ENDER_CHEST, CRAFTING_TABLE, ANVIL, CHIPPED_ANVIL, DAMAGED_ANVIL, ENCHANTING_TABLE,
    TRIAL_KEY, OMINOUS_TRIAL_KEY, VAULT;
    public boolean isItem() { return true; }
    public boolean isEdible() { return this == GOLDEN_APPLE || this == ENCHANTED_GOLDEN_APPLE || this == CHORUS_FRUIT; }
    public static Material matchMaterial(String name) {
        if (name == null) return null;
        try { return valueOf(name.trim().toUpperCase()); } catch (IllegalArgumentException e) { return null; }
    }
}
""",
    "org/bukkit/ChatColor.java": """
package org.bukkit;
public enum ChatColor {
    GOLD;
    public static String translateAlternateColorCodes(char alt, String text) {
        return text == null ? "" : text.replace(alt, '\\u00a7');
    }
    public static String stripColor(String input) { return input; }
}
""",
    "org/bukkit/NamespacedKey.java": """
package org.bukkit;
import org.bukkit.plugin.Plugin;
public final class NamespacedKey {
    public NamespacedKey(Plugin plugin, String key) {}
}
""",
    "org/bukkit/OfflinePlayer.java": """
package org.bukkit;
import java.util.UUID;
public interface OfflinePlayer {
    UUID getUniqueId();
    String getName();
    boolean isOnline();
}
""",
    "org/bukkit/command/CommandSender.java": """
package org.bukkit.command;
import org.bukkit.permissions.Permissible;
public interface CommandSender extends Permissible {
    void sendMessage(String message);
    String getName();
}
""",
    "org/bukkit/command/Command.java": """
package org.bukkit.command;
public abstract class Command {
    public String getName() { return ""; }
}
""",
    "org/bukkit/command/PluginCommand.java": """
package org.bukkit.command;
public final class PluginCommand extends Command {
    public void setExecutor(CommandExecutor executor) {}
    public void setTabCompleter(TabCompleter completer) {}
}
""",
    "org/bukkit/command/CommandExecutor.java": """
package org.bukkit.command;
public interface CommandExecutor {
    boolean onCommand(CommandSender sender, Command command, String label, String[] args);
}
""",
    "org/bukkit/command/TabCompleter.java": """
package org.bukkit.command;
import java.util.List;
public interface TabCompleter {
    List<String> onTabComplete(CommandSender sender, Command command, String label, String[] args);
}
""",
    "org/bukkit/command/TabExecutor.java": """
package org.bukkit.command;
public interface TabExecutor extends TabCompleter, CommandExecutor {}
""",
    "org/bukkit/permissions/ServerOperator.java": """
package org.bukkit.permissions;
public interface ServerOperator {
    default boolean isOp() { return false; }
}
""",
    "org/bukkit/permissions/Permissible.java": """
package org.bukkit.permissions;
public interface Permissible extends ServerOperator {
    boolean hasPermission(String name);
}
""",
    "org/bukkit/projectiles/ProjectileSource.java": """
package org.bukkit.projectiles;
public interface ProjectileSource {}
""",
    "org/bukkit/entity/AnimalTamer.java": """
package org.bukkit.entity;
public interface AnimalTamer {}
""",
    "org/bukkit/metadata/Metadatable.java": """
package org.bukkit.metadata;
import java.util.List;
import org.bukkit.plugin.Plugin;
public interface Metadatable {
    void setMetadata(String metadataKey, MetadataValue newMetadataValue);
    List<MetadataValue> getMetadata(String metadataKey);
    boolean hasMetadata(String metadataKey);
    void removeMetadata(String metadataKey, Plugin owningPlugin);
}
""",
    "org/bukkit/entity/Entity.java": """
package org.bukkit.entity;
import java.util.UUID;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.command.CommandSender;
import org.bukkit.metadata.Metadatable;
public interface Entity extends CommandSender, Metadatable {
    UUID getUniqueId();
    Location getLocation();
    World getWorld();
    boolean isDead();
    boolean isInsideVehicle();
    boolean leaveVehicle();
    boolean eject();
    boolean teleport(Location location);
}
""",
    "org/bukkit/entity/LivingEntity.java": """
package org.bukkit.entity;
import org.bukkit.inventory.EntityEquipment;
import org.bukkit.projectiles.ProjectileSource;
public interface LivingEntity extends Entity, ProjectileSource {
    EntityEquipment getEquipment();
    double getHealth();
    double getMaxHealth();
    void setHealth(double h);
    void setCanPickupItems(boolean pickup);
    boolean getCanPickupItems();
    boolean isGliding();
    void setGliding(boolean gliding);
    boolean isSleeping();
}
""",
    "org/bukkit/entity/Mob.java": """
package org.bukkit.entity;
public interface Mob extends LivingEntity {}
""",
    "org/bukkit/entity/Slime.java": """
package org.bukkit.entity;
public interface Slime extends Mob {}
""",
    "org/bukkit/entity/ThrownPotion.java": """
package org.bukkit.entity;
public interface ThrownPotion extends Projectile {}
""",
    "org/bukkit/entity/ArmorStand.java": """
package org.bukkit.entity;
public interface ArmorStand extends LivingEntity {}
""",
    "org/bukkit/entity/Hanging.java": """
package org.bukkit.entity;
public interface Hanging extends Entity {}
""",
    "org/bukkit/entity/HumanEntity.java": """
package org.bukkit.entity;
import org.bukkit.GameMode;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryView;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;
public interface HumanEntity extends LivingEntity, AnimalTamer {
    PlayerInventory getInventory();
    InventoryView getOpenInventory();
    InventoryView openInventory(Inventory inv);
    void closeInventory();
    ItemStack getItemInHand();
    void setFoodLevel(int level);
    GameMode getGameMode();
    void wakeup(boolean setSpawnLocation);
}
""",
    "org/bukkit/entity/Player.java": """
package org.bukkit.entity;
import org.bukkit.OfflinePlayer;
public interface Player extends HumanEntity, OfflinePlayer {
    void setCooldown(org.bukkit.Material material, int ticks);
    boolean isFlying();
    void setFlying(boolean value);
    boolean getAllowFlight();
    void setAllowFlight(boolean flight);
    boolean isSneaking();
    void sendActionBar(String message);
}
""",
    "org/bukkit/entity/Item.java": """
package org.bukkit.entity;
public interface Item extends Entity {}
""",
    "org/bukkit/entity/Projectile.java": """
package org.bukkit.entity;
import org.bukkit.projectiles.ProjectileSource;
public interface Projectile extends Entity {
    ProjectileSource getShooter();
}
""",
    "org/bukkit/entity/TNTPrimed.java": """
package org.bukkit.entity;
public interface TNTPrimed extends Entity {
    Entity getSource();
}
""",
    "org/bukkit/entity/AreaEffectCloud.java": """
package org.bukkit.entity;
import org.bukkit.projectiles.ProjectileSource;
public interface AreaEffectCloud extends Entity {
    ProjectileSource getSource();
}
""",
    "org/bukkit/entity/Tameable.java": """
package org.bukkit.entity;
public interface Tameable extends LivingEntity {
    AnimalTamer getOwner();
}
""",
    "org/bukkit/block/Block.java": """
package org.bukkit.block;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.metadata.Metadatable;
public interface Block extends Metadatable {
    Material getType();
    Location getLocation();
    BlockState getState();
}
""",
    "org/bukkit/block/BlockState.java": """
package org.bukkit.block;
import org.bukkit.Location;
import org.bukkit.metadata.Metadatable;
public interface BlockState extends Metadatable {
    Location getLocation();
}
""",
    "org/bukkit/block/Container.java": """
package org.bukkit.block;
import org.bukkit.inventory.InventoryHolder;
public interface Container extends BlockState, InventoryHolder {}
""",
    "org/bukkit/block/DoubleChest.java": """
package org.bukkit.block;
import org.bukkit.Location;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
public class DoubleChest implements InventoryHolder {
    @Override public Inventory getInventory() { return null; }
    public InventoryHolder getLeftSide() { return null; }
    public InventoryHolder getRightSide() { return null; }
    public Location getLocation() { return null; }
}
""",
    "org/bukkit/block/ShulkerBox.java": """
package org.bukkit.block;
import org.bukkit.inventory.InventoryHolder;
public interface ShulkerBox extends BlockState, InventoryHolder {}
""",
    "org/bukkit/inventory/InventoryHolder.java": """
package org.bukkit.inventory;
public interface InventoryHolder {
    Inventory getInventory();
}
""",
    "org/bukkit/inventory/Inventory.java": """
package org.bukkit.inventory;
import org.bukkit.Location;
import org.bukkit.event.inventory.InventoryType;
public interface Inventory {
    int getSize();
    ItemStack getItem(int index);
    void setItem(int index, ItemStack item);
    InventoryHolder getHolder();
    InventoryType getType();
    Location getLocation();
}
""",
    "org/bukkit/inventory/PlayerInventory.java": """
package org.bukkit.inventory;
import java.util.HashMap;
public interface PlayerInventory extends Inventory {
    HashMap<Integer, ItemStack> addItem(ItemStack... items);
}
""",
    "org/bukkit/inventory/EntityEquipment.java": """
package org.bukkit.inventory;
public interface EntityEquipment {
    ItemStack getItemInMainHand();
    ItemStack getItemInOffHand();
}
""",
    "org/bukkit/inventory/InventoryView.java": """
package org.bukkit.inventory;
import org.bukkit.event.inventory.InventoryType;
public abstract class InventoryView {
    public Inventory getTopInventory() { return null; }
    public InventoryType getType() { return InventoryType.CHEST; }
}
""",
    "org/bukkit/enchantments/Enchantment.java": """
package org.bukkit.enchantments;
public abstract class Enchantment {
    public static final Enchantment PROTECTION = new Enchantment() {};
    public static final Enchantment THORNS = new Enchantment() {};
    public static final Enchantment VANISHING_CURSE = new Enchantment() {};
    public static final Enchantment EFFICIENCY = new Enchantment() {};
    public static final Enchantment FORTUNE = new Enchantment() {};
    public static final Enchantment UNBREAKING = new Enchantment() {};
    public static final Enchantment MENDING = new Enchantment() {};
    public static final Enchantment LUCK_OF_THE_SEA = new Enchantment() {};
    public static final Enchantment LURE = new Enchantment() {};
    public static final Enchantment SHARPNESS = new Enchantment() {};
    public static final Enchantment FIRE_ASPECT = new Enchantment() {};
    public static final Enchantment LOOTING = new Enchantment() {};
    public static final Enchantment SWEEPING_EDGE = new Enchantment() {};
    public static final Enchantment IMPALING = new Enchantment() {};
    public static final Enchantment RIPTIDE = new Enchantment() {};
    public static final Enchantment LOYALTY = new Enchantment() {};
    public static final Enchantment CHANNELING = new Enchantment() {};
}
""",
    "org/bukkit/potion/PotionType.java": """
package org.bukkit.potion;
public enum PotionType {
    STRENGTH, SWIFTNESS, STRONG_STRENGTH, STRONG_SWIFTNESS, HEALING, INSTANT_HEAL
}
""",
    "org/bukkit/inventory/meta/ItemMeta.java": """
package org.bukkit.inventory.meta;
import java.util.List;
import org.bukkit.enchantments.Enchantment;
public interface ItemMeta {
    boolean hasDisplayName();
    String getDisplayName();
    void setDisplayName(String name);
    void setLore(List<String> lore);
    void setCustomModelData(Integer data);
    boolean hasEnchants();
    boolean addEnchant(Enchantment ench, int level, boolean ignoreLevelRestriction);
    void setUnbreakable(boolean unbreakable);
}
""",
    "org/bukkit/inventory/meta/BlockStateMeta.java": """
package org.bukkit.inventory.meta;
import org.bukkit.block.BlockState;
public interface BlockStateMeta extends ItemMeta {
    BlockState getBlockState();
    void setBlockState(BlockState blockState);
}
""",
    "org/bukkit/inventory/meta/EnchantmentStorageMeta.java": """
package org.bukkit.inventory.meta;
import org.bukkit.enchantments.Enchantment;
public interface EnchantmentStorageMeta extends ItemMeta {
    boolean hasStoredEnchants();
    boolean addStoredEnchant(Enchantment ench, int level, boolean ignoreLevelRestriction);
}
""",
    "org/bukkit/inventory/meta/PotionMeta.java": """
package org.bukkit.inventory.meta;
import org.bukkit.potion.PotionType;
public interface PotionMeta extends ItemMeta {
    PotionType getBasePotionType();
    void setBasePotionType(PotionType type);
    boolean hasCustomEffects();
}
""",
    "org/bukkit/inventory/ItemStack.java": """
package org.bukkit.inventory;
import org.bukkit.Material;
import org.bukkit.inventory.meta.ItemMeta;
public class ItemStack implements Cloneable {
    private final Material type;
    private ItemMeta meta;
    public ItemStack(Material type) { this.type = type; }
    public Material getType() { return type; }
    public ItemMeta getItemMeta() { return meta; }
    public boolean setItemMeta(ItemMeta meta) { this.meta = meta; return true; }
    public byte[] serializeAsBytes() { return new byte[0]; }
    public static ItemStack deserializeBytes(byte[] bytes) { return new ItemStack(Material.STONE); }
    @Override public ItemStack clone() {
        ItemStack copy = new ItemStack(type);
        copy.meta = this.meta;
        return copy;
    }
}
""",
    "org/bukkit/potion/PotionEffectType.java": """
package org.bukkit.potion;
public abstract class PotionEffectType {}
""",
    "org/bukkit/configuration/ConfigurationSection.java": """
package org.bukkit.configuration;
import java.util.Collections;
import java.util.List;
import java.util.Set;
public interface ConfigurationSection {
    default String getString(String path) { return ""; }
    default String getString(String path, String def) { return def; }
    default int getInt(String path) { return 0; }
    default int getInt(String path, int def) { return def; }
    default boolean getBoolean(String path) { return false; }
    default List<?> getList(String path) { return Collections.emptyList(); }
    default List<String> getStringList(String path) { return Collections.emptyList(); }
    default ConfigurationSection getConfigurationSection(String path) { return null; }
    default Set<String> getKeys(boolean deep) { return Collections.emptySet(); }
}
""",
    "org/bukkit/configuration/file/FileConfiguration.java": """
package org.bukkit.configuration.file;
import org.bukkit.configuration.ConfigurationSection;
public abstract class FileConfiguration implements ConfigurationSection {}
""",
    "org/bukkit/configuration/file/YamlConfiguration.java": """
package org.bukkit.configuration.file;
import java.io.File;
public class YamlConfiguration extends FileConfiguration {
    public static YamlConfiguration loadConfiguration(File file) { return new YamlConfiguration(); }
}
""",
    "org/bukkit/plugin/PluginDescriptionFile.java": """
package org.bukkit.plugin;
public final class PluginDescriptionFile {
    public String getVersion() { return "1.0"; }
}
""",
    "org/bukkit/plugin/Plugin.java": """
package org.bukkit.plugin;
import java.io.File;
import java.util.logging.Logger;
import org.bukkit.Server;
import org.bukkit.command.TabExecutor;
import org.bukkit.configuration.file.FileConfiguration;
public interface Plugin extends TabExecutor {
    String getName();
    File getDataFolder();
    Logger getLogger();
    boolean isEnabled();
    Server getServer();
    FileConfiguration getConfig();
    PluginDescriptionFile getDescription();
}
""",
    "org/bukkit/plugin/PluginBase.java": """
package org.bukkit.plugin;
public abstract class PluginBase implements Plugin {}
""",
    "org/bukkit/plugin/java/JavaPlugin.java": """
package org.bukkit.plugin.java;
import java.io.File;
import java.util.logging.Logger;
import org.bukkit.Server;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.plugin.PluginBase;
import org.bukkit.plugin.PluginDescriptionFile;
import java.util.List;
public abstract class JavaPlugin extends PluginBase {
    private final Logger logger = Logger.getLogger("Plugin");
    public void onEnable() {}
    public void onDisable() {}
    public void saveDefaultConfig() {}
    @Override public String getName() { return getClass().getSimpleName(); }
    @Override public File getDataFolder() { return new File("/tmp"); }
    @Override public Logger getLogger() { return logger; }
    @Override public boolean isEnabled() { return false; }
    @Override public Server getServer() { return null; }
    @Override public FileConfiguration getConfig() { return null; }
    @Override public PluginDescriptionFile getDescription() { return new PluginDescriptionFile(); }
    @Override public boolean onCommand(CommandSender s, Command c, String l, String[] a) { return false; }
    @Override public List<String> onTabComplete(CommandSender s, Command c, String l, String[] a) { return null; }
}
""",
    "org/bukkit/event/EventException.java": """
package org.bukkit.event;
public class EventException extends Exception {
    private static final long serialVersionUID = 1L;
    public EventException() {}
    public EventException(Throwable t) { super(t); }
}
""",
    "org/bukkit/event/server/ServerEvent.java": """
package org.bukkit.event.server;
import org.bukkit.event.Event;
public abstract class ServerEvent extends Event {}
""",
    "org/bukkit/event/server/PluginEvent.java": """
package org.bukkit.event.server;
import org.bukkit.plugin.Plugin;
public abstract class PluginEvent extends ServerEvent {
    public Plugin getPlugin() { return null; }
}
""",
    "org/bukkit/event/server/PluginEnableEvent.java": """
package org.bukkit.event.server;
public class PluginEnableEvent extends PluginEvent {}
""",
    "org/bukkit/plugin/EventExecutor.java": """
package org.bukkit.plugin;
import org.bukkit.event.Event;
import org.bukkit.event.EventException;
import org.bukkit.event.Listener;
public interface EventExecutor {
    void execute(Listener listener, Event event) throws EventException;
}
""",
    "org/bukkit/plugin/PluginManager.java": """
package org.bukkit.plugin;
import org.bukkit.event.Event;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
public interface PluginManager {
    Plugin getPlugin(String name);
    void disablePlugin(Plugin plugin);
    void registerEvents(Listener listener, Plugin plugin);
    void registerEvent(Class<? extends Event> event, Listener listener, EventPriority priority, EventExecutor executor, Plugin plugin, boolean ignoreCancelled);
    void callEvent(Event event);
}
""",
    "org/bukkit/plugin/RegisteredServiceProvider.java": """
package org.bukkit.plugin;
public class RegisteredServiceProvider<T> {
    public T getProvider() { return null; }
}
""",
    "org/bukkit/plugin/ServicesManager.java": """
package org.bukkit.plugin;
public interface ServicesManager {
    <T> RegisteredServiceProvider<T> getRegistration(Class<T> service);
}
""",
    "org/bukkit/scheduler/BukkitTask.java": """
package org.bukkit.scheduler;
public interface BukkitTask { void cancel(); }
""",
    "org/bukkit/scheduler/BukkitScheduler.java": """
package org.bukkit.scheduler;
import org.bukkit.plugin.Plugin;
public interface BukkitScheduler {
    BukkitTask runTask(Plugin plugin, Runnable task);
    BukkitTask runTaskLater(Plugin plugin, Runnable task, long delay);
    BukkitTask runTaskTimer(Plugin plugin, Runnable task, long delay, long period);
}
""",
    "org/bukkit/scheduler/BukkitRunnable.java": """
package org.bukkit.scheduler;
import org.bukkit.plugin.Plugin;
public abstract class BukkitRunnable implements Runnable {
    public synchronized BukkitTask runTaskLater(Plugin plugin, long delay) { run(); return null; }
    public synchronized BukkitTask runTaskAsynchronously(Plugin plugin) { run(); return null; }
    public synchronized BukkitTask runTaskTimerAsynchronously(Plugin plugin, long delay, long period) { return null; }
}
""",
    "org/bukkit/event/HandlerList.java": """
package org.bukkit.event;
public class HandlerList {}
""",
    "org/bukkit/event/Event.java": """
package org.bukkit.event;
public abstract class Event {
    public enum Result { DENY, DEFAULT, ALLOW }
    public Event() {}
    public Event(boolean isAsync) {}
    public HandlerList getHandlers() { return new HandlerList(); }
}
""",
    "org/bukkit/event/Cancellable.java": """
package org.bukkit.event;
public interface Cancellable {
    boolean isCancelled();
    void setCancelled(boolean cancel);
}
""",
    "org/bukkit/event/Listener.java": """
package org.bukkit.event;
public interface Listener {}
""",
    "org/bukkit/event/EventPriority.java": """
package org.bukkit.event;
public enum EventPriority { LOWEST, LOW, NORMAL, HIGH, HIGHEST, MONITOR }
""",
    "org/bukkit/event/EventHandler.java": """
package org.bukkit.event;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface EventHandler {
    EventPriority priority() default EventPriority.NORMAL;
    boolean ignoreCancelled() default false;
}
""",
    "org/bukkit/event/block/Action.java": """
package org.bukkit.event.block;
public enum Action { LEFT_CLICK_BLOCK, RIGHT_CLICK_BLOCK, LEFT_CLICK_AIR, RIGHT_CLICK_AIR, PHYSICAL }
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
import org.bukkit.entity.Player;
import org.bukkit.event.Cancellable;
public class BlockBreakEvent extends BlockEvent implements Cancellable {
    private final Player player; private boolean c;
    public BlockBreakEvent(Player p) { this.player = p; }
    public Player getPlayer() { return player; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/block/BlockPlaceEvent.java": """
package org.bukkit.event.block;
import org.bukkit.entity.Player;
import org.bukkit.event.Cancellable;
public class BlockPlaceEvent extends BlockEvent implements Cancellable {
    private final Player player; private boolean c;
    public BlockPlaceEvent(Player p) { this.player = p; }
    public Player getPlayer() { return player; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/block/BlockMultiPlaceEvent.java": """
package org.bukkit.event.block;
import org.bukkit.entity.Player;
public class BlockMultiPlaceEvent extends BlockPlaceEvent {
    public BlockMultiPlaceEvent(Player p) { super(p); }
}
""",
    "org/bukkit/event/block/BlockDamageEvent.java": """
package org.bukkit.event.block;
import org.bukkit.entity.Player;
import org.bukkit.event.Cancellable;
public class BlockDamageEvent extends BlockEvent implements Cancellable {
    private final Player player; private boolean c;
    public BlockDamageEvent(Player p) { this.player = p; }
    public Player getPlayer() { return player; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/block/SignChangeEvent.java": """
package org.bukkit.event.block;
import org.bukkit.entity.Player;
import org.bukkit.event.Cancellable;
public class SignChangeEvent extends BlockEvent implements Cancellable {
    private final Player player; private boolean c;
    public SignChangeEvent(Player p) { this.player = p; }
    public Player getPlayer() { return player; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/block/BlockIgniteEvent.java": """
package org.bukkit.event.block;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.Cancellable;
public class BlockIgniteEvent extends BlockEvent implements Cancellable {
    private final Player player; private final Entity igniter; private boolean c;
    public BlockIgniteEvent(Player p, Entity e) { this.player = p; this.igniter = e; }
    public Player getPlayer() { return player; }
    public Entity getIgnitingEntity() { return igniter; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/block/BlockFadeEvent.java": """
package org.bukkit.event.block;
public class BlockFadeEvent extends BlockEvent {}
""",
    "org/bukkit/event/entity/EntityEvent.java": """
package org.bukkit.event.entity;
import org.bukkit.entity.Entity;
import org.bukkit.event.Event;
public abstract class EntityEvent extends Event {
    protected Entity entity;
    public Entity getEntity() { return entity; }
}
""",
    "org/bukkit/event/entity/EntityDamageEvent.java": """
package org.bukkit.event.entity;
import org.bukkit.event.Cancellable;
public class EntityDamageEvent extends EntityEvent implements Cancellable {
    private boolean c;
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/entity/EntityDamageByEntityEvent.java": """
package org.bukkit.event.entity;
import org.bukkit.entity.Entity;
public class EntityDamageByEntityEvent extends EntityDamageEvent {
    private final Entity damager;
    public EntityDamageByEntityEvent(Entity damager, Entity victim) { this.damager = damager; this.entity = victim; }
    public Entity getDamager() { return damager; }
}
""",
    "org/bukkit/event/entity/EntityPickupItemEvent.java": """
package org.bukkit.event.entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.event.Cancellable;
public class EntityPickupItemEvent extends EntityEvent implements Cancellable {
    private boolean c;
    public EntityPickupItemEvent(LivingEntity e) { this.entity = e; }
    @Override public LivingEntity getEntity() { return (LivingEntity) entity; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/entity/EntityShootBowEvent.java": """
package org.bukkit.event.entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.event.Cancellable;
import org.bukkit.inventory.ItemStack;
public class EntityShootBowEvent extends EntityEvent implements Cancellable {
    private boolean c;
    @Override public LivingEntity getEntity() { return (LivingEntity) entity; }
    public ItemStack getBow() { return null; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/entity/ProjectileLaunchEvent.java": """
package org.bukkit.event.entity;
import org.bukkit.entity.Projectile;
import org.bukkit.event.Cancellable;
public class ProjectileLaunchEvent extends EntityEvent implements Cancellable {
    private boolean c;
    @Override public Projectile getEntity() { return (Projectile) entity; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/entity/EntityChangeBlockEvent.java": """
package org.bukkit.event.entity;
import org.bukkit.block.Block;
import org.bukkit.event.Cancellable;
public class EntityChangeBlockEvent extends EntityEvent implements Cancellable {
    private Block block; private boolean c;
    public Block getBlock() { return block; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/entity/EntityUnleashEvent.java": """
package org.bukkit.event.entity;
public class EntityUnleashEvent extends EntityEvent {}
""",
    "org/bukkit/event/entity/EntityResurrectEvent.java": """
package org.bukkit.event.entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.event.Cancellable;
public class EntityResurrectEvent extends EntityEvent implements Cancellable {
    private boolean c;
    @Override public LivingEntity getEntity() { return (LivingEntity) entity; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/entity/PlayerDeathEvent.java": """
package org.bukkit.event.entity;
import org.bukkit.entity.Player;
public class PlayerDeathEvent extends EntityEvent {
    @Override public Player getEntity() { return (Player) entity; }
}
""",
    "org/bukkit/event/entity/PotionSplashEvent.java": """
package org.bukkit.event.entity;
import java.util.Collection;
import java.util.Collections;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.ThrownPotion;
import org.bukkit.event.Cancellable;
public class PotionSplashEvent extends EntityEvent implements Cancellable {
    private boolean c;
    public ThrownPotion getPotion() { return (ThrownPotion) entity; }
    public Collection<LivingEntity> getAffectedEntities() { return Collections.emptyList(); }
    public void setIntensity(LivingEntity entity, double intensity) {}
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/entity/AreaEffectCloudApplyEvent.java": """
package org.bukkit.event.entity;
import java.util.Collections;
import java.util.List;
import org.bukkit.entity.AreaEffectCloud;
import org.bukkit.entity.LivingEntity;
import org.bukkit.event.Cancellable;
public class AreaEffectCloudApplyEvent extends EntityEvent implements Cancellable {
    private boolean c;
    @Override public AreaEffectCloud getEntity() { return (AreaEffectCloud) entity; }
    public List<LivingEntity> getAffectedEntities() { return Collections.emptyList(); }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/hanging/HangingEvent.java": """
package org.bukkit.event.hanging;
import org.bukkit.entity.Hanging;
import org.bukkit.event.Event;
public abstract class HangingEvent extends Event {
    protected Hanging hanging;
    public Hanging getEntity() { return hanging; }
}
""",
    "org/bukkit/event/hanging/HangingBreakByEntityEvent.java": """
package org.bukkit.event.hanging;
import org.bukkit.entity.Entity;
import org.bukkit.event.Cancellable;
public class HangingBreakByEntityEvent extends HangingEvent implements Cancellable {
    private Entity remover; private boolean c;
    public Entity getRemover() { return remover; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/hanging/HangingPlaceEvent.java": """
package org.bukkit.event.hanging;
import org.bukkit.entity.Player;
import org.bukkit.event.Cancellable;
public class HangingPlaceEvent extends HangingEvent implements Cancellable {
    private Player player; private boolean c;
    public Player getPlayer() { return player; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/inventory/InventoryType.java": """
package org.bukkit.event.inventory;
public enum InventoryType {
    CHEST, ENDER_CHEST, WORKBENCH, ANVIL, ENCHANTING, CRAFTING, CREATIVE, PLAYER, MERCHANT
}
""",
    "org/bukkit/event/inventory/InventoryAction.java": """
package org.bukkit.event.inventory;
public enum InventoryAction {
    NOTHING, PICKUP_ALL, COLLECT_TO_CURSOR, MOVE_TO_OTHER_INVENTORY
}
""",
    "org/bukkit/event/inventory/InventoryEvent.java": """
package org.bukkit.event.inventory;
import org.bukkit.event.Event;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryView;
public class InventoryEvent extends Event {
    protected Inventory inv;
    protected InventoryView view;
    public Inventory getInventory() { return inv; }
    public InventoryView getView() { return view; }
}
""",
    "org/bukkit/event/inventory/InventoryOpenEvent.java": """
package org.bukkit.event.inventory;
import org.bukkit.entity.HumanEntity;
import org.bukkit.event.Cancellable;
import org.bukkit.inventory.Inventory;
public class InventoryOpenEvent extends InventoryEvent implements Cancellable {
    private final HumanEntity player; private boolean c;
    public InventoryOpenEvent(HumanEntity p) { this.player = p; }
    public InventoryOpenEvent(HumanEntity p, Inventory inv) { this.player = p; this.inv = inv; }
    public HumanEntity getPlayer() { return player; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/inventory/InventoryInteractEvent.java": """
package org.bukkit.event.inventory;
import org.bukkit.entity.HumanEntity;
import org.bukkit.event.Cancellable;
public abstract class InventoryInteractEvent extends InventoryEvent implements Cancellable {
    private HumanEntity who; private boolean c;
    public HumanEntity getWhoClicked() { return who; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/inventory/InventoryClickEvent.java": """
package org.bukkit.event.inventory;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
public class InventoryClickEvent extends InventoryInteractEvent {
    public Inventory getClickedInventory() { return null; }
    public ItemStack getCurrentItem() { return null; }
    public boolean isShiftClick() { return false; }
    public InventoryAction getAction() { return InventoryAction.NOTHING; }
}
""",
    "org/bukkit/event/inventory/InventoryDragEvent.java": """
package org.bukkit.event.inventory;
import java.util.Collections;
import java.util.Set;
public class InventoryDragEvent extends InventoryInteractEvent {
    public Set<Integer> getRawSlots() { return Collections.emptySet(); }
}
""",
    "org/bukkit/event/player/PlayerEvent.java": """
package org.bukkit.event.player;
import org.bukkit.entity.Player;
import org.bukkit.event.Event;
public abstract class PlayerEvent extends Event {
    protected Player player;
    public PlayerEvent() {}
    public PlayerEvent(Player who) { this.player = who; }
    public final Player getPlayer() { return player; }
}
""",
    "org/bukkit/event/player/PlayerJoinEvent.java": """
package org.bukkit.event.player;
import org.bukkit.entity.Player;
public class PlayerJoinEvent extends PlayerEvent {
    public PlayerJoinEvent(Player p) { super(p); }
}
""",
    "org/bukkit/event/player/PlayerQuitEvent.java": """
package org.bukkit.event.player;
import org.bukkit.entity.Player;
public class PlayerQuitEvent extends PlayerEvent {
    public PlayerQuitEvent(Player p) { super(p); }
}
""",
    "org/bukkit/event/player/PlayerKickEvent.java": """
package org.bukkit.event.player;
public class PlayerKickEvent extends PlayerEvent {
    public String getReason() { return ""; }
}
""",
    "org/bukkit/event/player/PlayerMoveEvent.java": """
package org.bukkit.event.player;
import org.bukkit.Location;
public class PlayerMoveEvent extends PlayerEvent {
    public Location getFrom() { return null; }
    public Location getTo() { return null; }
}
""",
    "org/bukkit/event/player/PlayerTeleportEvent.java": """
package org.bukkit.event.player;
public class PlayerTeleportEvent extends PlayerMoveEvent {}
""",
    "org/bukkit/event/player/PlayerCommandPreprocessEvent.java": """
package org.bukkit.event.player;
import org.bukkit.entity.Player;
import org.bukkit.event.Cancellable;
public class PlayerCommandPreprocessEvent extends PlayerEvent implements Cancellable {
    private String message; private boolean c;
    public PlayerCommandPreprocessEvent(Player p, String msg) { super(p); this.message = msg; }
    public String getMessage() { return message; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/player/PlayerCommandSendEvent.java": """
package org.bukkit.event.player;
import java.util.Collection;
public class PlayerCommandSendEvent extends PlayerEvent {
    public Collection<String> getCommands() { return null; }
}
""",
    "org/bukkit/event/player/PlayerInteractEvent.java": """
package org.bukkit.event.player;
import org.bukkit.block.Block;
import org.bukkit.entity.Player;
import org.bukkit.event.Cancellable;
import org.bukkit.event.block.Action;
import org.bukkit.inventory.ItemStack;
public class PlayerInteractEvent extends PlayerEvent implements Cancellable {
    private final Action action;
    private Result useBlock = Result.DEFAULT;
    private Result useItem = Result.DEFAULT;
    public PlayerInteractEvent(Player p, Action a) { super(p); this.action = a; }
    public Action getAction() { return action; }
    public ItemStack getItem() { return null; }
    public Block getClickedBlock() { return null; }
    public Result useInteractedBlock() { return useBlock; }
    public Result useItemInHand() { return useItem; }
    public void setUseInteractedBlock(Result r) { this.useBlock = r; }
    public void setUseItemInHand(Result r) { this.useItem = r; }
    @Override public boolean isCancelled() { return useBlock == Result.DENY; }
    @Override public void setCancelled(boolean b) {
        useBlock = b ? Result.DENY : Result.ALLOW;
        useItem = b ? Result.DENY : Result.ALLOW;
    }
}
""",
    "org/bukkit/event/player/PlayerInteractEntityEvent.java": """
package org.bukkit.event.player;
import org.bukkit.entity.Entity;
import org.bukkit.event.Cancellable;
public class PlayerInteractEntityEvent extends PlayerEvent implements Cancellable {
    private Entity clicked; private boolean c;
    public Entity getRightClicked() { return clicked; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/player/PlayerInteractAtEntityEvent.java": """
package org.bukkit.event.player;
public class PlayerInteractAtEntityEvent extends PlayerInteractEntityEvent {}
""",
    "org/bukkit/event/player/PlayerArmorStandManipulateEvent.java": """
package org.bukkit.event.player;
public class PlayerArmorStandManipulateEvent extends PlayerInteractEntityEvent {}
""",
    "org/bukkit/event/player/PlayerAttemptPickupItemEvent.java": """
package org.bukkit.event.player;
import org.bukkit.event.Cancellable;
public class PlayerAttemptPickupItemEvent extends PlayerEvent implements Cancellable {
    private boolean c;
    public void setFlyAtPlayer(boolean f) {}
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/block/data/BlockData.java": """
package org.bukkit.block.data;
public interface BlockData {}
""",
    "org/bukkit/block/data/Ageable.java": """
package org.bukkit.block.data;
public interface Ageable extends BlockData {}
""",
    "org/bukkit/block/data/type/Farmland.java": """
package org.bukkit.block.data.type;
import org.bukkit.block.data.BlockData;
public interface Farmland extends BlockData {}
""",
    "org/bukkit/Sound.java": """
package org.bukkit;
public enum Sound { UI_BUTTON_CLICK }
""",
    "org/bukkit/entity/EntityType.java": """
package org.bukkit.entity;
public enum EntityType { PLAYER }
""",
    "org/bukkit/entity/EnderCrystal.java": """
package org.bukkit.entity;
public interface EnderCrystal extends Entity {}
""",
    "org/bukkit/inventory/meta/SkullMeta.java": """
package org.bukkit.inventory.meta;
public interface SkullMeta extends ItemMeta {}
""",
    "org/bukkit/metadata/MetadataValue.java": """
package org.bukkit.metadata;
import org.bukkit.plugin.Plugin;
public interface MetadataValue {
    default Object value() { return null; }
    default Plugin getOwningPlugin() { return null; }
}
""",
    "org/bukkit/metadata/FixedMetadataValue.java": """
package org.bukkit.metadata;
import org.bukkit.plugin.Plugin;
public class FixedMetadataValue implements MetadataValue {
    private final Plugin plugin;
    private final Object val;
    public FixedMetadataValue(Plugin owningPlugin, Object value) {
        this.plugin = owningPlugin; this.val = value;
    }
    @Override public Object value() { return val; }
    @Override public Plugin getOwningPlugin() { return plugin; }
}
""",
    "org/bukkit/persistence/PersistentDataType.java": """
package org.bukkit.persistence;
public interface PersistentDataType<P, C> {
    PersistentDataType<String, String> STRING = null;
}
""",
    "org/bukkit/persistence/PersistentDataContainer.java": """
package org.bukkit.persistence;
public interface PersistentDataContainer {}
""",
    "org/bukkit/configuration/serialization/SerializableAs.java": """
package org.bukkit.configuration.serialization;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
@Retention(RetentionPolicy.RUNTIME)
public @interface SerializableAs { String value(); }
""",
    "org/bukkit/configuration/serialization/ConfigurationSerializable.java": """
package org.bukkit.configuration.serialization;
import java.util.Map;
public interface ConfigurationSerializable {
    Map<String, Object> serialize();
}
""",
    "com/google/common/collect/UnmodifiableIterator.java": """
package com.google.common.collect;
import java.util.Iterator;
public abstract class UnmodifiableIterator<E> implements Iterator<E> {}
""",
    "com/google/common/collect/ImmutableSet.java": """
package com.google.common.collect;
import java.util.Set;
public abstract class ImmutableSet<E> implements Set<E> {
    @Override public abstract UnmodifiableIterator<E> iterator();
}
""",
    "com/google/common/collect/ImmutableMap.java": """
package com.google.common.collect;
import java.util.Map;
public abstract class ImmutableMap<K, V> implements Map<K, V> {
    @Override public abstract ImmutableSet<K> keySet();
    public static <K, V> ImmutableMap<K, V> copyOf(Map<? extends K, ? extends V> map) { return null; }
}
""",
    "com/github/benmanes/caffeine/cache/RemovalCause.java": """
package com.github.benmanes.caffeine.cache;
public enum RemovalCause { EXPLICIT, REPLACED, COLLECTED, EXPIRED, SIZE }
""",
    "com/github/benmanes/caffeine/cache/RemovalListener.java": """
package com.github.benmanes.caffeine.cache;
public interface RemovalListener<K, V> {
    void onRemoval(K key, V value, RemovalCause cause);
}
""",
    "com/github/benmanes/caffeine/cache/Scheduler.java": """
package com.github.benmanes.caffeine.cache;
public interface Scheduler {
    static Scheduler systemScheduler() { return null; }
}
""",
    "com/github/benmanes/caffeine/cache/Cache.java": """
package com.github.benmanes.caffeine.cache;
public interface Cache<K, V> {
    V getIfPresent(Object key);
}
""",
    "com/github/benmanes/caffeine/cache/Caffeine.java": """
package com.github.benmanes.caffeine.cache;
import java.util.concurrent.TimeUnit;
public final class Caffeine<K, V> {
    public static Caffeine<Object, Object> newBuilder() { return new Caffeine<>(); }
    public Caffeine<K, V> expireAfterWrite(long duration, TimeUnit unit) { return this; }
    public Caffeine<K, V> scheduler(Scheduler s) { return this; }
    public <K1 extends K, V1 extends V> Caffeine<K1, V1> removalListener(RemovalListener<? super K1, ? super V1> l) { return null; }
    public <K1 extends K, V1 extends V> Cache<K1, V1> build() { return null; }
}
""",
    "org/bukkit/event/player/PlayerPickupItemEvent.java": """
package org.bukkit.event.player;
import org.bukkit.event.Cancellable;
public class PlayerPickupItemEvent extends PlayerEvent implements Cancellable {
    private boolean c;
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/player/PlayerPickupArrowEvent.java": """
package org.bukkit.event.player;
public class PlayerPickupArrowEvent extends PlayerPickupItemEvent {}
""",
    "org/bukkit/event/player/PlayerDropItemEvent.java": """
package org.bukkit.event.player;
import org.bukkit.event.Cancellable;
public class PlayerDropItemEvent extends PlayerEvent implements Cancellable {
    private boolean c;
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/player/PlayerSwapHandItemsEvent.java": """
package org.bukkit.event.player;
import org.bukkit.event.Cancellable;
public class PlayerSwapHandItemsEvent extends PlayerEvent implements Cancellable {
    private boolean c;
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/player/PlayerItemConsumeEvent.java": """
package org.bukkit.event.player;
import org.bukkit.event.Cancellable;
import org.bukkit.inventory.ItemStack;
public class PlayerItemConsumeEvent extends PlayerEvent implements Cancellable {
    private boolean c;
    public ItemStack getItem() { return null; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/player/PlayerItemHeldEvent.java": """
package org.bukkit.event.player;
public class PlayerItemHeldEvent extends PlayerEvent {
    public int getNewSlot() { return 0; }
}
""",
    "org/bukkit/event/player/PlayerFishEvent.java": """
package org.bukkit.event.player;
import org.bukkit.entity.Entity;
import org.bukkit.event.Cancellable;
public class PlayerFishEvent extends PlayerEvent implements Cancellable {
    private Entity caught; private boolean c;
    public Entity getCaught() { return caught; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/player/PlayerToggleFlightEvent.java": """
package org.bukkit.event.player;
import org.bukkit.entity.Player;
import org.bukkit.event.Cancellable;
public class PlayerToggleFlightEvent extends PlayerEvent implements Cancellable {
    private final boolean flying; private boolean c;
    public PlayerToggleFlightEvent(Player p, boolean flying) { super(p); this.flying = flying; }
    public boolean isFlying() { return flying; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/player/PlayerBucketEvent.java": """
package org.bukkit.event.player;
import org.bukkit.block.Block;
import org.bukkit.event.Cancellable;
public abstract class PlayerBucketEvent extends PlayerEvent implements Cancellable {
    private Block block; private boolean c;
    public final Block getBlock() { return block; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/player/PlayerBucketEmptyEvent.java": """
package org.bukkit.event.player;
public class PlayerBucketEmptyEvent extends PlayerBucketEvent {}
""",
    "org/bukkit/event/player/PlayerBucketFillEvent.java": """
package org.bukkit.event.player;
public class PlayerBucketFillEvent extends PlayerBucketEvent {}
""",
    "org/bukkit/event/player/PlayerBucketEntityEvent.java": """
package org.bukkit.event.player;
import org.bukkit.entity.Entity;
import org.bukkit.event.Cancellable;
public class PlayerBucketEntityEvent extends PlayerEvent implements Cancellable {
    private Entity entity; private boolean c;
    public Entity getEntity() { return entity; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/player/PlayerShearEntityEvent.java": """
package org.bukkit.event.player;
import org.bukkit.entity.Entity;
import org.bukkit.event.Cancellable;
public class PlayerShearEntityEvent extends PlayerEvent implements Cancellable {
    private Entity what; private boolean c;
    public Entity getEntity() { return what; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/entity/PlayerLeashEntityEvent.java": """
package org.bukkit.event.entity;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.Cancellable;
import org.bukkit.event.Event;
public class PlayerLeashEntityEvent extends Event implements Cancellable {
    private Entity entity; private Player player; private boolean c;
    public Entity getEntity() { return entity; }
    public Player getPlayer() { return player; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/player/PlayerUnleashEntityEvent.java": """
package org.bukkit.event.player;
import org.bukkit.entity.Player;
import org.bukkit.event.Cancellable;
import org.bukkit.event.entity.EntityUnleashEvent;
public class PlayerUnleashEntityEvent extends EntityUnleashEvent implements Cancellable {
    private Player player; private boolean c;
    public Player getPlayer() { return player; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/player/PlayerBedEnterEvent.java": """
package org.bukkit.event.player;
import org.bukkit.event.Cancellable;
public class PlayerBedEnterEvent extends PlayerEvent implements Cancellable {
    private boolean c;
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/vehicle/VehicleEvent.java": """
package org.bukkit.event.vehicle;
import org.bukkit.event.Event;
public abstract class VehicleEvent extends Event {}
""",
    "org/bukkit/event/vehicle/VehicleEnterEvent.java": """
package org.bukkit.event.vehicle;
import org.bukkit.entity.Entity;
import org.bukkit.event.Cancellable;
public class VehicleEnterEvent extends VehicleEvent implements Cancellable {
    private Entity entered; private boolean c;
    public Entity getEntered() { return entered; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/vehicle/VehicleDamageEvent.java": """
package org.bukkit.event.vehicle;
import org.bukkit.entity.Entity;
import org.bukkit.event.Cancellable;
public class VehicleDamageEvent extends VehicleEvent implements Cancellable {
    private Entity attacker; private boolean c;
    public Entity getAttacker() { return attacker; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "org/bukkit/event/vehicle/VehicleDestroyEvent.java": """
package org.bukkit.event.vehicle;
import org.bukkit.entity.Entity;
import org.bukkit.event.Cancellable;
public class VehicleDestroyEvent extends VehicleEvent implements Cancellable {
    private Entity attacker; private boolean c;
    public Entity getAttacker() { return attacker; }
    @Override public boolean isCancelled() { return c; }
    @Override public void setCancelled(boolean b) { c = b; }
}
""",
    "me/clip/placeholderapi/expansion/PlaceholderExpansion.java": """
package me.clip.placeholderapi.expansion;
import org.bukkit.entity.Player;
public abstract class PlaceholderExpansion {
    public abstract String getIdentifier();
    public abstract String getAuthor();
    public abstract String getVersion();
    public boolean persist() { return false; }
    public String onPlaceholderRequest(Player p, String params) { return ""; }
}
""",
    "net/md_5/bungee/api/ChatColor.java": """
package net.md_5.bungee.api;
public final class ChatColor {
    public static String stripColor(String s) { return s; }
}
""",
    "net/milkbowl/vault/economy/Economy.java": """
package net.milkbowl.vault.economy;
public interface Economy {}
""",
}


def run(*cmd):
    subprocess.run(cmd, check=True)


def verify_greatcombat_config_b64():
    cfg_text = (ROOT / "plugins/GreatCombat/config.yml").read_text(encoding="utf-8")
    b64_lines = re.findall(r"^\s*base64:\s*(\S+)\s*$", cfg_text, flags=re.M)
    assert len(b64_lines) == 5, f"Expected 5 base64 entries in GreatCombat/config.yml, got {len(b64_lines)}"
    for idx, b64 in enumerate(b64_lines):
        raw_gz = base64.b64decode(b64, validate=True)
        nbt = gzip.decompress(raw_gz)
        dv_marker = b"\x03\x00\x0bDataVersion"
        pos = nbt.find(dv_marker)
        assert pos >= 0, f"Entry #{idx} missing DataVersion"
        dv = int.from_bytes(nbt[pos + len(dv_marker):pos + len(dv_marker) + 4], "big")
        assert dv == 4671, f"Entry #{idx} has DataVersion {dv}, expected 4671 (1.21.11)"
    print("[OK] All 5 GreatCombat/config.yml Base64 item entries verified as DataVersion 4671 (1.21.11).")


def parse_constant_pool_classes(data: bytes) -> set:
    pos = 8
    cp_count = struct.unpack_from(">H", data, pos)[0]
    pos += 2
    cp = [None] * cp_count
    i = 1
    while i < cp_count:
        tag = data[pos]
        pos += 1
        if tag == 1:
            ln = struct.unpack_from(">H", data, pos)[0]
            pos += 2
            cp[i] = ("utf8", data[pos:pos + ln].decode("utf-8", "replace"))
            pos += ln
        elif tag in (3, 4):
            pos += 4
        elif tag in (5, 6):
            pos += 8
            i += 1
        elif tag in (7, 8, 16, 19, 20):
            idx = struct.unpack_from(">H", data, pos)[0]
            pos += 2
            cp[i] = (tag, idx)
        elif tag in (9, 10, 11, 12, 17, 18):
            a, b = struct.unpack_from(">HH", data, pos)
            pos += 4
            cp[i] = (tag, a, b)
        elif tag == 15:
            pos += 3
        i += 1
    out = set()
    for item in cp:
        if item and item[0] == 7:
            out.add(cp[item[1]][1])
    return out


def verify_constant_pool_against_live_plugins(*cands: Path):
    newly_compiled_entries = {
        "pw/elytrix/godpickup/GodPickup.class",
        "com/hokokrtet/hjobs/manager/DatabaseManager.class",
        "wtf/n1zamu/utils/ValidatorUtil.class",
        "me/realized/duels/util/ElytrixDuelTeleportFix.class",
        "topka/simbay/rwitems/utils/ElytrixAirTrapGuard.class",
        "ru/Travka/util/ElytrixMascotGuard.class",
        "ru/penatov/itemkeep/data/ElytrixItemKeepFix.class",
    }
    known = set()
    skip = {"ElytrixGodPickup.jar"}
    for jar in sorted((ROOT / "plugins").glob("*.jar")):
        if jar.name in skip:
            continue
        try:
            with zipfile.ZipFile(jar, "r") as z:
                for n in z.namelist():
                    if n.endswith(".class") and n not in newly_compiled_entries:
                        known.add(n[:-6])
                        try:
                            known |= parse_constant_pool_classes(z.read(n))
                        except Exception:
                            pass
        except Exception:
            pass

    for cand in cands:
        with zipfile.ZipFile(cand, "r") as z:
            own = {n[:-6] for n in z.namelist() if n.endswith(".class")}
            for n in z.namelist():
                if not n.endswith(".class"):
                    continue
                for ref in sorted(parse_constant_pool_classes(z.read(n))):
                    if ref.startswith("org/bukkit/") and ref not in own and ref not in known:
                        raise RuntimeError(
                            f"FATAL: {cand.name}:{n} references unknown Bukkit class '{ref}' "
                            f"not present in any live server plugin!"
                        )
    print(f"[OK] Constant-pool gate passed: 100% of org.bukkit.* classes verified across {len(cands)} JARs.")


def build_zip_replacing(src_jar: Path, out_jar: Path, replacements: dict, removals: set = None):
    removals = removals or set()
    written = set()
    with zipfile.ZipFile(src_jar, "r") as zin, zipfile.ZipFile(out_jar, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            name = info.filename
            if name in removals or name in written:
                continue
            if name in replacements:
                zout.writestr(name, replacements[name])
            else:
                zout.writestr(info, zin.read(name))
            written.add(name)
        for name, data in sorted(replacements.items()):
            if name not in written:
                zout.writestr(name, data)
                written.add(name)
    with zipfile.ZipFile(out_jar, "r") as check:
        bad = check.testzip()
        if bad is not None:
            raise RuntimeError(f"Corrupt ZIP entry {bad} in {out_jar}")


def main():
    verify_greatcombat_config_b64()

    with tempfile.TemporaryDirectory() as td_raw:
        td = Path(td_raw)
        stub_src = td / "stubs_src"
        stub_cls = td / "stubs_cls"
        patch_cls = td / "patch_cls"
        god_cls = td / "god_cls"
        hjobs_cls = td / "hjobs_cls"
        nclans_cls = td / "nclans_cls"
        duels_cls = td / "duels_cls"
        eitems_cls = td / "eitems_cls"
        nmascot_cls = td / "nmascot_cls"
        itemkeep_cls = td / "itemkeep_cls"
        test_cls = td / "test_cls"
        for d in (stub_src, stub_cls, patch_cls, god_cls, hjobs_cls, nclans_cls,
                  duels_cls, eitems_cls, nmascot_cls, itemkeep_cls, test_cls):
            d.mkdir(parents=True, exist_ok=True)

        # 1. Write & compile stubs + PatchAllPlugins
        stub_files = []
        for rel, code in STUBS.items():
            p = stub_src / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(code.strip() + "\n", encoding="utf-8")
            stub_files.append(str(p))

        blib = str(ROOT / "plugins/BLib.jar")
        ess_jar = str(next((ROOT / "plugins").glob("EssentialsX-*.jar")))
        vault_jar = str(ROOT / "plugins/Vault.jar")
        wg_jar = str(next((ROOT / "plugins").glob("worldguard-bukkit-*.jar")))
        we_jar = str(next((ROOT / "plugins").glob("FastAsyncWorldEdit-Paper-*.jar")))

        run(JAVA, "-jar", ECJ, "-21", "-encoding", "UTF-8", "-proc:none",
            "-cp", blib, "-d", str(stub_cls), *stub_files)
        run(JAVA, "-jar", ECJ, "-21", "-encoding", "UTF-8", "-proc:none",
            "-cp", blib, "-d", str(patch_cls), str(HERE / "src/PatchAllPlugins.java"))

        patch_cp = f"{patch_cls}{os.pathsep}{blib}"

        # 2. Build ElytrixGodPickup.jar (v2.1.0 — /god + /fly + WG own-region chests + mob combat + Talisman)
        run(JAVA, "-jar", ECJ, "-21", "-encoding", "UTF-8", "-proc:none",
            "-cp", str(stub_cls),
            "-d", str(god_cls),
            str(GOD_DIR / "src/pw/elytrix/godpickup/GodPickup.java"))

        cand_god = td / "ElytrixGodPickup.jar"
        with zipfile.ZipFile(cand_god, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            zout.writestr("plugin.yml", (GOD_DIR / "plugin.yml").read_bytes())
            for cls_file in sorted(god_cls.rglob("*.class")):
                zout.writestr(cls_file.relative_to(god_cls).as_posix(), cls_file.read_bytes())

        # 3. Patch & compile hJobs.jar (Fix 1)
        src_hjobs = ROOT / "plugins/hJobs.jar"
        with zipfile.ZipFile(src_hjobs, "r") as z:
            (td / "jm_in.class").write_bytes(z.read("com/hokokrtet/hjobs/manager/JobManager.class"))
            (td / "pl_in.class").write_bytes(z.read("com/hokokrtet/hjobs/listener/PlayerListener.class"))
            (td / "gl_in.class").write_bytes(z.read("com/hokokrtet/hjobs/listener/GuiListener.class"))

        run(JAVA, "-cp", patch_cp, "PatchAllPlugins", "hjobs-jobmanager",
            str(td / "jm_in.class"), str(td / "jm_out.class"))
        run(JAVA, "-cp", patch_cp, "PatchAllPlugins", "hjobs-playerlistener",
            str(td / "pl_in.class"), str(td / "pl_out.class"))
        run(JAVA, "-cp", patch_cp, "PatchAllPlugins", "hjobs-guilistener",
            str(td / "gl_in.class"), str(td / "gl_out.class"))

        # Stage patched JobManager so DatabaseManager.java compiles cleanly against peekPlayerStats(UUID)
        jm_pkg = hjobs_cls / "com/hokokrtet/hjobs/manager"
        jm_pkg.mkdir(parents=True, exist_ok=True)
        shutil.copy2(td / "jm_out.class", jm_pkg / "JobManager.class")

        run(JAVA, "-jar", ECJ, "-21", "-encoding", "UTF-8", "-proc:none",
            "-cp", f"{hjobs_cls}{os.pathsep}{stub_cls}{os.pathsep}{src_hjobs}{os.pathsep}{vault_jar}",
            "-d", str(hjobs_cls),
            str(HERE / "src/com/hokokrtet/hjobs/manager/DatabaseManager.java"))

        hjobs_replacements = {
            "com/hokokrtet/hjobs/manager/JobManager.class": (td / "jm_out.class").read_bytes(),
            "com/hokokrtet/hjobs/listener/PlayerListener.class": (td / "pl_out.class").read_bytes(),
            "com/hokokrtet/hjobs/listener/GuiListener.class": (td / "gl_out.class").read_bytes(),
        }
        for cls_file in sorted((hjobs_cls / "com/hokokrtet/hjobs/manager").glob("DatabaseManager*.class")):
            hjobs_replacements[f"com/hokokrtet/hjobs/manager/{cls_file.name}"] = cls_file.read_bytes()

        hjobs_removals = {
            k for k in ("com/hokokrtet/hjobs/manager/DatabaseManager$1.class",
                        "com/hokokrtet/hjobs/manager/DatabaseManager$2.class",
                        "com/hokokrtet/hjobs/manager/DatabaseManager$3.class")
            if k not in hjobs_replacements
        }
        cand_hjobs = td / "hJobs.jar"
        build_zip_replacing(src_hjobs, cand_hjobs, hjobs_replacements, hjobs_removals)

        # 4. Patch & compile NClans-1.jar (Fix 3)
        src_nclans = ROOT / "plugins/NClans-1.jar"
        run(JAVA, "-jar", ECJ, "-21", "-encoding", "UTF-8", "-proc:none",
            "-cp", f"{stub_cls}{os.pathsep}{src_nclans}",
            "-d", str(nclans_cls),
            str(HERE / "src/wtf/n1zamu/utils/ValidatorUtil.java"))

        with zipfile.ZipFile(src_nclans, "r") as z:
            (td / "nc_clan_in.class").write_bytes(z.read("wtf/n1zamu/clans/Clan.class"))
            (td / "nc_ph_in.class").write_bytes(z.read("wtf/n1zamu/placeholder/ClanPlaceholder.class"))
            (td / "nc_info_in.class").write_bytes(z.read("wtf/n1zamu/function/impl/info/InfoFunction.class"))
            (td / "nc_lvl_in.class").write_bytes(z.read("wtf/n1zamu/level/config/LevelConfiguration.class"))

        run(JAVA, "-cp", patch_cp, "PatchAllPlugins", "nclans-clan",
            str(td / "nc_clan_in.class"), str(td / "nc_clan_out.class"))
        run(JAVA, "-cp", patch_cp, "PatchAllPlugins", "nclans-placeholder",
            str(td / "nc_ph_in.class"), str(td / "nc_ph_out.class"))
        run(JAVA, "-cp", patch_cp, "PatchAllPlugins", "nclans-info",
            str(td / "nc_info_in.class"), str(td / "nc_info_out.class"))
        run(JAVA, "-cp", patch_cp, "PatchAllPlugins", "nclans-levelconfig",
            str(td / "nc_lvl_in.class"), str(td / "nc_lvl_out.class"))

        nclans_replacements = {
            "wtf/n1zamu/utils/ValidatorUtil.class": (nclans_cls / "wtf/n1zamu/utils/ValidatorUtil.class").read_bytes(),
            "wtf/n1zamu/clans/Clan.class": (td / "nc_clan_out.class").read_bytes(),
            "wtf/n1zamu/placeholder/ClanPlaceholder.class": (td / "nc_ph_out.class").read_bytes(),
            "wtf/n1zamu/function/impl/info/InfoFunction.class": (td / "nc_info_out.class").read_bytes(),
            "wtf/n1zamu/level/config/LevelConfiguration.class": (td / "nc_lvl_out.class").read_bytes(),
        }
        cand_nclans = td / "NClans-1.jar"
        build_zip_replacing(src_nclans, cand_nclans, nclans_replacements)

        # 5. Patch GreatCombat-1.9.jar (Fix 5 hardening)
        src_gc = ROOT / "plugins/GreatCombat-1.9.jar"
        with zipfile.ZipFile(src_gc, "r") as z:
            (td / "gc_iu_in.class").write_bytes(z.read("dev/enco/greatcombat/utils/ItemUtils.class"))
            (td / "gc_cm_in.class").write_bytes(z.read("dev/enco/greatcombat/restrictions/cooldowns/CooldownManager.class"))
            (td / "gc_pl_in.class").write_bytes(z.read("dev/enco/greatcombat/listeners/PlayerListener.class"))
            gc_plugin_yml = z.read("plugin.yml").decode("utf-8")

        run(JAVA, "-cp", patch_cp, "PatchAllPlugins", "gc-itemutils",
            str(td / "gc_iu_in.class"), str(td / "gc_iu_out.class"))
        run(JAVA, "-cp", patch_cp, "PatchAllPlugins", "gc-cooldownmanager",
            str(td / "gc_cm_in.class"), str(td / "gc_cm_out.class"))
        run(JAVA, "-cp", patch_cp, "PatchAllPlugins", "gc-playerlistener",
            str(td / "gc_pl_in.class"), str(td / "gc_pl_out.class"))

        if "permissions:" not in gc_plugin_yml:
            gc_plugin_yml = gc_plugin_yml.rstrip() + "\n" + (
                "permissions:\n"
                "  greatcombat.teleports.bypass:\n"
                "    default: false\n"
                "  greatcombat.powerups.bypass:\n"
                "    default: false\n"
                "  greatcombat.commands.bypass:\n"
                "    default: false\n"
                "  greatcombat.cooldowns.bypass:\n"
                "    default: false\n"
                "  greatcombat.kill.bypass:\n"
                "    default: false\n"
                "  greatcombat.prevention.bypass:\n"
                "    default: false\n"
            )

        gc_replacements = {
            "dev/enco/greatcombat/utils/ItemUtils.class": (td / "gc_iu_out.class").read_bytes(),
            "dev/enco/greatcombat/restrictions/cooldowns/CooldownManager.class": (td / "gc_cm_out.class").read_bytes(),
            "dev/enco/greatcombat/listeners/PlayerListener.class": (td / "gc_pl_out.class").read_bytes(),
            "plugin.yml": gc_plugin_yml.encode("utf-8"),
        }
        cand_gc = td / "GreatCombat-1.9.jar"
        build_zip_replacing(src_gc, cand_gc, gc_replacements)

        # 6. Patch Duels-3.5.3.jar (Fix #4 — duel teleport race + Metadata guard + watchdog retry)
        src_duels = ROOT / "plugins/Duels-3.5.3.jar"
        run(JAVA, "-jar", ECJ, "-21", "-encoding", "UTF-8", "-proc:none",
            "-cp", f"{stub_cls}{os.pathsep}{src_duels}",
            "-d", str(duels_cls),
            str(HERE / "src/me/realized/duels/util/ElytrixDuelTeleportFix.java"))

        with zipfile.ZipFile(src_duels, "r") as z:
            (td / "duels_perf_in.class").write_bytes(z.read("me/realized/duels/util/ElytrixDuelPerf.class"))
            (td / "duels_lst_in.class").write_bytes(z.read("me/realized/duels/duel/DuelManager$DuelListener.class"))

        run(JAVA, "-cp", patch_cp, "PatchAllPlugins", "duels-perf",
            str(td / "duels_perf_in.class"), str(td / "duels_perf_out.class"))
        run(JAVA, "-cp", patch_cp, "PatchAllPlugins", "duels-listener",
            str(td / "duels_lst_in.class"), str(td / "duels_lst_out.class"))

        duels_replacements = {
            "me/realized/duels/util/ElytrixDuelPerf.class": (td / "duels_perf_out.class").read_bytes(),
            "me/realized/duels/duel/DuelManager$DuelListener.class": (td / "duels_lst_out.class").read_bytes(),
        }
        for cls_file in sorted(duels_cls.rglob("*.class")):
            duels_replacements[cls_file.relative_to(duels_cls).as_posix()] = cls_file.read_bytes()
        cand_duels = td / "Duels-3.5.3.jar"
        build_zip_replacing(src_duels, cand_duels, duels_replacements)

        # 7. Patch ElytrixItems.jar (Fix #5 — forbid TrapItem / EnderTrapItem near active AirDrop)
        src_eitems = ROOT / "plugins/ElytrixItems.jar"
        run(JAVA, "-jar", ECJ, "-21", "-encoding", "UTF-8", "-proc:none",
            "-cp", f"{stub_cls}{os.pathsep}{src_eitems}",
            "-d", str(eitems_cls),
            str(HERE / "src/topka/simbay/rwitems/utils/ElytrixAirTrapGuard.java"))

        with zipfile.ZipFile(src_eitems, "r") as z:
            (td / "eitems_trap_in.class").write_bytes(z.read("topka/simbay/rwitems/items/ItemEffects$TrapItem.class"))
            eitems_plugin_yml = z.read("plugin.yml").decode("utf-8")

        run(JAVA, "-cp", patch_cp, "PatchAllPlugins", "elytrixitems-trap",
            str(td / "eitems_trap_in.class"), str(td / "eitems_trap_out.class"))

        if "ElytrixAir" not in eitems_plugin_yml:
            eitems_plugin_yml = eitems_plugin_yml.replace(
                "softdepend:\n- WorldGuard\n- WorldEdit",
                "softdepend:\n- WorldGuard\n- WorldEdit\n- ElytrixAir"
            )

        eitems_replacements = {
            "topka/simbay/rwitems/items/ItemEffects$TrapItem.class": (td / "eitems_trap_out.class").read_bytes(),
            "plugin.yml": eitems_plugin_yml.encode("utf-8"),
        }
        for cls_file in sorted(eitems_cls.rglob("*.class")):
            eitems_replacements[cls_file.relative_to(eitems_cls).as_posix()] = cls_file.read_bytes()
        cand_eitems = td / "ElytrixItems.jar"
        build_zip_replacing(src_eitems, cand_eitems, eitems_replacements)

        # 8. Patch NMascot-1.0.jar (Fix #6 — disable /fly and /god in active Talisman region)
        src_nmascot = ROOT / "plugins/NMascot-1.0.jar"
        run(JAVA, "-jar", ECJ, "-21", "-encoding", "UTF-8", "-proc:none",
            "-cp", f"{stub_cls}{os.pathsep}{src_nmascot}",
            "-d", str(nmascot_cls),
            str(HERE / "src/ru/Travka/util/ElytrixMascotGuard.java"))

        with zipfile.ZipFile(src_nmascot, "r") as z:
            (td / "nmascot_move_in.class").write_bytes(z.read("ru/Travka/listener/PlayerMoveListener.class"))

        run(JAVA, "-cp", patch_cp, "PatchAllPlugins", "nmascot-move",
            str(td / "nmascot_move_in.class"), str(td / "nmascot_move_out.class"))

        nmascot_replacements = {
            "ru/Travka/listener/PlayerMoveListener.class": (td / "nmascot_move_out.class").read_bytes(),
        }
        for cls_file in sorted(nmascot_cls.rglob("*.class")):
            nmascot_replacements[cls_file.relative_to(nmascot_cls).as_posix()] = cls_file.read_bytes()
        cand_nmascot = td / "NMascot-1.0.jar"
        build_zip_replacing(src_nmascot, cand_nmascot, nmascot_replacements)

        # 9. Patch ItemKeep-1.0-SNAPSHOT.jar (Fixes #1 & #8 — clone items, guarantee enchants, drop overflow)
        src_itemkeep = ROOT / "plugins/ItemKeep-1.0-SNAPSHOT.jar"
        run(JAVA, "-jar", ECJ, "-21", "-encoding", "UTF-8", "-proc:none",
            "-cp", f"{stub_cls}{os.pathsep}{src_itemkeep}",
            "-d", str(itemkeep_cls),
            str(HERE / "src/ru/penatov/itemkeep/data/ElytrixItemKeepFix.java"))

        with zipfile.ZipFile(src_itemkeep, "r") as z:
            (td / "ik_dm_in.class").write_bytes(z.read("ru/penatov/itemkeep/data/DataManager.class"))

        run(JAVA, "-cp", patch_cp, "PatchAllPlugins", "itemkeep-datamanager",
            str(td / "ik_dm_in.class"), str(td / "ik_dm_out.class"))

        itemkeep_replacements = {
            "ru/penatov/itemkeep/data/DataManager.class": (td / "ik_dm_out.class").read_bytes(),
        }
        for cls_file in sorted(itemkeep_cls.rglob("*.class")):
            itemkeep_replacements[cls_file.relative_to(itemkeep_cls).as_posix()] = cls_file.read_bytes()
        cand_itemkeep = td / "ItemKeep-1.0-SNAPSHOT.jar"
        build_zip_replacing(src_itemkeep, cand_itemkeep, itemkeep_replacements)

        # 10. Compile & execute BugfixVerificationSuite under strict JVM -Xverify:all!
        verify_cp = os.pathsep.join([
            str(test_cls),
            str(cand_god),
            str(cand_hjobs),
            str(cand_nclans),
            str(cand_gc),
            str(cand_duels),
            str(cand_eitems),
            str(cand_nmascot),
            str(cand_itemkeep),
            str(stub_cls),
            ess_jar,
            blib,
            vault_jar,
            wg_jar,
            we_jar,
            str(ROOT / "plugins/ProtocolLib.jar"),
            str(ROOT / "plugins/PlaceholderAPI-2.11.7.jar"),
        ])
        run(JAVA, "-jar", ECJ, "-21", "-encoding", "UTF-8", "-proc:none",
            "-cp", verify_cp,
            "-d", str(test_cls),
            str(HERE / "test/BugfixVerificationSuite.java"))

        run(JAVA, "-Xverify:all", "-cp", verify_cp,
            "BugfixVerificationSuite",
            str(cand_god), str(cand_hjobs), str(cand_nclans), str(cand_gc),
            str(cand_duels), str(cand_eitems), str(cand_nmascot), str(cand_itemkeep))

        verify_constant_pool_against_live_plugins(
            cand_god, cand_hjobs, cand_nclans, cand_gc,
            cand_duels, cand_eitems, cand_nmascot, cand_itemkeep
        )

        # 11. Atomically install verified JARs into plugins/
        targets = [
            (cand_god, ROOT / "plugins/ElytrixGodPickup.jar"),
            (cand_hjobs, ROOT / "plugins/hJobs.jar"),
            (cand_nclans, ROOT / "plugins/NClans-1.jar"),
            (cand_gc, ROOT / "plugins/GreatCombat-1.9.jar"),
            (cand_duels, ROOT / "plugins/Duels-3.5.3.jar"),
            (cand_eitems, ROOT / "plugins/ElytrixItems.jar"),
            (cand_nmascot, ROOT / "plugins/NMascot-1.0.jar"),
            (cand_itemkeep, ROOT / "plugins/ItemKeep-1.0-SNAPSHOT.jar"),
        ]
        for src_cand, dst_jar in targets:
            tmp_dst = dst_jar.with_suffix(".jar.tmp")
            shutil.copy2(src_cand, tmp_dst)
            os.replace(tmp_dst, dst_jar)
            sha = hashlib.sha256(dst_jar.read_bytes()).hexdigest()
            print(f"[INSTALLED] {dst_jar.relative_to(ROOT)} ({dst_jar.stat().st_size} bytes, sha256={sha[:16]}...)")


if __name__ == "__main__":
    main()
