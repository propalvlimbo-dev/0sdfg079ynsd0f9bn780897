package org.bukkit.command; public class PluginCommand extends Command {public CommandExecutor executor;public void setExecutor(CommandExecutor executor){this.executor=executor;}}
