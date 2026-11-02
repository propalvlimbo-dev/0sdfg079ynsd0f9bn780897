package org.bukkit.plugin.java;
import org.bukkit.plugin.Plugin;
import org.bukkit.command.PluginCommand;
import java.util.logging.Logger;
public class JavaPlugin implements Plugin {
    public final PluginCommand mockCommand = new PluginCommand();
    public boolean returnNullCommand;
    public final java.util.List<String> warnings = new java.util.ArrayList<>();
    public PluginCommand getCommand(String command) { return returnNullCommand ? null : mockCommand; }
    public Logger getLogger() {
        return new Logger("ElytrixFreakModel", null) {
            @Override public void warning(String message) { warnings.add(message); }
        };
    }
}
