package org.bukkit; import org.bukkit.plugin.*; import org.bukkit.inventory.*; import org.bukkit.command.CommandSender;
public class Bukkit {
    public static PluginManager manager; public static Inventory created; public static String title; public static int size;
    public static java.util.Map<Integer,ItemStack> slots; public static final java.util.List<String> dispatched = new java.util.ArrayList<>();
    public static final CommandSender console = message -> {};
    public static PluginManager getPluginManager(){return manager;}
    public static CommandSender getConsoleSender(){return console;}
    public static boolean dispatchCommand(CommandSender sender,String command){if(!dispatchWorks)return false;dispatched.add(command);return true;}
    public static boolean dispatchWorks=true;
    public static Inventory createInventory(InventoryHolder h,int n,String title){Bukkit.title=title;Bukkit.size=n;slots=new java.util.HashMap<>();created=new Inventory(){public void setItem(int slot,ItemStack item){slots.put(slot,item);}public InventoryHolder getHolder(){return h;}};return created;}
}
