package org.bukkit.plugin; public interface PluginManager { Plugin getPlugin(String name); void disablePlugin(Plugin p); void registerEvents(org.bukkit.event.Listener l, Plugin p); }
