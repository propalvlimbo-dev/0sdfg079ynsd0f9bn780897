package org.bukkit.plugin.java;
import org.bukkit.plugin.Plugin;
import org.bukkit.command.PluginCommand;
import java.util.logging.Logger;
public class JavaPlugin implements Plugin {
    public final PluginCommand mockCommand = new PluginCommand();
    public boolean returnNullCommand;
    public java.io.File mockDataFolder = new java.io.File(System.getProperty("java.io.tmpdir"), "elytrix-acc-test");
    public final java.util.List<String> warnings = new java.util.ArrayList<>();
    public final java.io.File getDataFolder() { return mockDataFolder; }
    public PluginCommand getCommand(String command) { return returnNullCommand ? null : mockCommand; }
    public Logger getLogger() {
        return new Logger("ElytrixFreakModel", null) {
            @Override public void warning(String message) { warnings.add(message); }
        };
    }
}
