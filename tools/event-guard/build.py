#!/usr/bin/env python3
"""Builds `plugins/ElytrixEventGuard.jar` and runs its JVM test suite.

The plugin is compiled with ECJ against a tiny hand-written stand-in for the Bukkit
API (no server jar needed), packed together with `plugin.yml` and the default
`config.yml`, and then exercised under `-Xverify:all` by `test/EventGuardTest.java`,
which proves the three rules this plugin exists for:

  1. an exempt player keeps /fly inside an event zone even if something strips it;
  2. an auction command is cancelled for a player in /god or /fly;
  3. an end-crystal explosion loses its block list while a normal one keeps it.

Usage:  JAVA=... ECJ=... python3 tools/event-guard/build.py [output.jar]
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

JAVA = os.environ.get("JAVA", "/tmp/pytools/jdk4py/java-runtime/bin/java")
ECJ = os.environ.get("ECJ", "/tmp/pytools/ecj.jar")

STUBS = {
"org/bukkit/permissions/Permissible.java": """
package org.bukkit.permissions;
public interface Permissible { boolean hasPermission(String name); }
""",
"org/bukkit/entity/Entity.java": """
package org.bukkit.entity;
public interface Entity {}
""",
"org/bukkit/entity/EnderCrystal.java": """
package org.bukkit.entity;
public interface EnderCrystal extends Entity {}
""",
"org/bukkit/entity/Player.java": """
package org.bukkit.entity;
import java.util.UUID;
import org.bukkit.GameMode;
import org.bukkit.Location;
public interface Player extends Entity, org.bukkit.permissions.Permissible {
    String getName();
    UUID getUniqueId();
    boolean getAllowFlight();
    void setAllowFlight(boolean allow);
    boolean isFlying();
    void setFlying(boolean flying);
    void sendMessage(String message);
    GameMode getGameMode();
    Location getLocation();
    Spigot spigot();
    public static class Spigot {
        public void sendMessage(org.bukkit.ChatMessageType type,
                                net.md_5.bungee.api.chat.BaseComponent... parts) {}
    }
}
""",
"org/bukkit/ChatMessageType.java": """
package org.bukkit;
public enum ChatMessageType { CHAT, SYSTEM, ACTION_BAR }
""",
"net/md_5/bungee/api/chat/BaseComponent.java": """
package net.md_5.bungee.api.chat;
public abstract class BaseComponent {}
""",
"net/md_5/bungee/api/chat/TextComponent.java": """
package net.md_5.bungee.api.chat;
public class TextComponent extends BaseComponent {
    public final String text;
    public TextComponent(String text) { this.text = text; }
}
""",
"org/bukkit/command/ConsoleCommandSender.java": """
package org.bukkit.command;
public interface ConsoleCommandSender { String getName(); }
""",
"org/bukkit/event/entity/EntityPickupItemEvent.java": """
package org.bukkit.event.entity;
import org.bukkit.entity.Entity;
public class EntityPickupItemEvent {
    private final Entity entity; private boolean cancelled;
    public EntityPickupItemEvent(Entity entity) { this.entity = entity; }
    public Entity getEntity() { return entity; }
    public void setCancelled(boolean value) { cancelled = value; }
    public boolean isCancelled() { return cancelled; }
}
""",
"org/bukkit/GameMode.java": """
package org.bukkit;
public enum GameMode { CREATIVE, SURVIVAL, ADVENTURE, SPECTATOR }
""",
"org/bukkit/World.java": """
package org.bukkit;
public interface World { String getName(); }
""",
"org/bukkit/Location.java": """
package org.bukkit;
public class Location {
    private final World world; private final double x, y, z;
    public Location(World world, double x, double y, double z) { this.world = world; this.x = x; this.y = y; this.z = z; }
    public World getWorld() { return world; }
    public double getX() { return x; }
    public double getY() { return y; }
    public double getZ() { return z; }
}
""",
"org/bukkit/event/EventPriority.java": """
package org.bukkit.event;
public enum EventPriority { LOWEST, LOW, NORMAL, HIGH, HIGHEST, MONITOR }
""",
"org/bukkit/event/EventHandler.java": """
package org.bukkit.event;
import java.lang.annotation.*;
@Retention(RetentionPolicy.RUNTIME) @Target(ElementType.METHOD)
public @interface EventHandler { EventPriority priority() default EventPriority.NORMAL; boolean ignoreCancelled() default false; }
""",
"org/bukkit/event/Listener.java": """
package org.bukkit.event;
public interface Listener {}
""",
"org/bukkit/event/entity/EntityExplodeEvent.java": """
package org.bukkit.event.entity;
import java.util.ArrayList;
import java.util.List;
import org.bukkit.entity.Entity;
public class EntityExplodeEvent {
    private final Entity entity; private final List<Object> blocks = new ArrayList<Object>(); private boolean cancelled;
    public EntityExplodeEvent(Entity entity, int blockCount) {
        this.entity = entity;
        for (int i = 0; i < blockCount; i++) { blocks.add(new Object()); }
    }
    public Entity getEntity() { return entity; }
    public List<Object> blockList() { return blocks; }
    public void setCancelled(boolean value) { cancelled = value; }
    public boolean isCancelled() { return cancelled; }
}
""",
"org/bukkit/event/player/PlayerCommandPreprocessEvent.java": """
package org.bukkit.event.player;
import org.bukkit.entity.Player;
public class PlayerCommandPreprocessEvent {
    private final Player player; private final String message; private boolean cancelled;
    public PlayerCommandPreprocessEvent(Player player, String message) { this.player = player; this.message = message; }
    public Player getPlayer() { return player; }
    public String getMessage() { return message; }
    public void setCancelled(boolean value) { cancelled = value; }
    public boolean isCancelled() { return cancelled; }
}
""",
"org/bukkit/event/player/PlayerQuitEvent.java": """
package org.bukkit.event.player;
import org.bukkit.entity.Player;
public class PlayerQuitEvent {
    private final Player player;
    public PlayerQuitEvent(Player player) { this.player = player; }
    public Player getPlayer() { return player; }
}
""",
"org/bukkit/plugin/Plugin.java": """
package org.bukkit.plugin;
public interface Plugin { boolean isEnabled(); String getName(); }
""",
"org/bukkit/plugin/PluginManager.java": """
package org.bukkit.plugin;
import org.bukkit.event.Listener;
public interface PluginManager {
    Plugin getPlugin(String name);
    void registerEvents(Listener listener, Plugin plugin);
}
""",
"org/bukkit/configuration/file/FileConfiguration.java": """
package org.bukkit.configuration.file;
import java.util.*;
public class FileConfiguration {
    protected final Map<String, Object> values = new LinkedHashMap<String, Object>();
    public void set(String path, Object value) { values.put(path, value); }
    public Object get(String path) { return values.get(path); }
    public String getString(String path, String fallback) { Object v = values.get(path); return v == null ? fallback : String.valueOf(v); }
    public boolean getBoolean(String path, boolean fallback) {
        Object v = values.get(path);
        if (v == null) return fallback;
        if (v instanceof Boolean) return ((Boolean) v).booleanValue();
        return Boolean.parseBoolean(String.valueOf(v));
    }
    public int getInt(String path, int fallback) {
        Object v = values.get(path);
        if (v == null) return fallback;
        if (v instanceof Number) return ((Number) v).intValue();
        try { return Integer.parseInt(String.valueOf(v).trim()); } catch (Exception e) { return fallback; }
    }
    public double getDouble(String path, double fallback) {
        Object v = values.get(path);
        if (v == null) return fallback;
        if (v instanceof Number) return ((Number) v).doubleValue();
        try { return Double.parseDouble(String.valueOf(v).trim()); } catch (Exception e) { return fallback; }
    }
    @SuppressWarnings("unchecked")
    public List<String> getStringList(String path) {
        Object v = values.get(path);
        if (v == null) return Collections.emptyList();
        if (v instanceof List) return (List<String>) v;
        return Collections.emptyList();
    }
}
""",
"org/bukkit/configuration/file/YamlConfiguration.java": """
package org.bukkit.configuration.file;
import java.io.File;
public class YamlConfiguration extends FileConfiguration {
    public static YamlConfiguration loadConfiguration(File file) { return new YamlConfiguration(); }
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
    BukkitTask runTaskTimer(Plugin plugin, Runnable task, long delay, long period);
    BukkitTask runTaskLater(Plugin plugin, Runnable task, long delay);
}
""",
"org/bukkit/plugin/java/JavaPlugin.java": """
package org.bukkit.plugin.java;
import java.io.File;
import java.util.logging.Logger;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.plugin.Plugin;
public abstract class JavaPlugin implements Plugin {
    private static final Logger LOG = Logger.getLogger("ElytrixEventGuard");
    public FileConfiguration config = new FileConfiguration();
    public File dataFolder = new File(".");
    public boolean isEnabled() { return true; }
    public String getName() { return "ElytrixEventGuard"; }
    public void onEnable() {}
    public void onDisable() {}
    public Logger getLogger() { return LOG; }
    public FileConfiguration getConfig() { return config; }
    public void saveDefaultConfig() {}
    public File getDataFolder() { return dataFolder; }
    public void reloadConfig() {}
}
""",
"org/bukkit/Server.java": """
package org.bukkit;
import java.util.Collection;
import org.bukkit.entity.Player;
import org.bukkit.plugin.PluginManager;
import org.bukkit.scheduler.BukkitScheduler;
public interface Server {
    PluginManager getPluginManager();
    BukkitScheduler getScheduler();
    Collection<? extends Player> getOnlinePlayers();
}
""",
"org/bukkit/Bukkit.java": """
package org.bukkit;
import java.util.Collection;
import java.util.Collections;
import org.bukkit.entity.Player;
import org.bukkit.plugin.PluginManager;
import org.bukkit.scheduler.BukkitScheduler;
public final class Bukkit {
    public static PluginManager manager;
    public static BukkitScheduler scheduler;
    public static Collection<? extends Player> online = Collections.emptyList();
    public static org.bukkit.command.ConsoleCommandSender console;
    public static java.util.List<String> dispatched = new java.util.ArrayList<String>();
    public static PluginManager getPluginManager() { return manager; }
    public static BukkitScheduler getScheduler() { return scheduler; }
    public static Collection<? extends Player> getOnlinePlayers() { return online; }
    public static org.bukkit.command.ConsoleCommandSender getConsoleSender() { return console; }
    public static boolean dispatchCommand(org.bukkit.command.ConsoleCommandSender sender, String cmd) {
        dispatched.add(cmd);
        return true;
    }
}
""",
}


def run(*cmd):
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        sys.stdout.write(proc.stdout.decode("utf-8", "replace"))
        raise SystemExit("command failed: " + " ".join(cmd))
    return proc.stdout.decode("utf-8", "replace")


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "plugins/ElytrixEventGuard.jar"
    with tempfile.TemporaryDirectory() as raw:
        td = Path(raw)
        stub_src = td / "stubs"
        for rel, body in STUBS.items():
            target = stub_src / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body.lstrip(), encoding="utf-8")
        stub_cls = td / "stub_cls"
        stub_cls.mkdir()
        run(JAVA, "-jar", ECJ, "-21", "-encoding", "UTF-8", "-proc:none", "-nowarn",
            "-d", str(stub_cls), *[str(p) for p in sorted(stub_src.rglob("*.java"))])

        src = HERE / "src/pw/elytrix/eventguard/EventGuard.java"
        main_cls = td / "main_cls"
        main_cls.mkdir()
        run(JAVA, "-jar", ECJ, "-21", "-encoding", "UTF-8", "-proc:none", "-nowarn",
            "-cp", str(stub_cls), "-d", str(main_cls), str(src))

        test_cls = td / "test_cls"
        test_cls.mkdir()
        run(JAVA, "-jar", ECJ, "-21", "-encoding", "UTF-8", "-proc:none", "-nowarn",
            "-cp", os.pathsep.join([str(stub_cls), str(main_cls)]),
            "-d", str(test_cls), str(HERE / "test/EventGuardTest.java"))

        out_test = run(JAVA, "-Xverify:all", "-cp",
                       os.pathsep.join([str(test_cls), str(main_cls), str(stub_cls)]),
                       "EventGuardTest")
        sys.stdout.write(out_test)

        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("plugin.yml", (HERE / "plugin.yml").read_bytes())
            z.writestr("config.yml", (HERE / "config.yml").read_bytes())
            for cls in sorted(main_cls.rglob("*.class")):
                z.writestr(cls.relative_to(main_cls).as_posix(), cls.read_bytes())
        print("built %s (%d bytes)" % (out, out.stat().st_size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
