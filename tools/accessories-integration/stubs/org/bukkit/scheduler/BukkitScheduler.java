package org.bukkit.scheduler; import org.bukkit.plugin.Plugin;
/** Compile-time stand-in: the mock tests keep the task instead of running it. */
public interface BukkitScheduler { BukkitTask runTaskTimer(Plugin plugin,Runnable task,long delay,long period); }
