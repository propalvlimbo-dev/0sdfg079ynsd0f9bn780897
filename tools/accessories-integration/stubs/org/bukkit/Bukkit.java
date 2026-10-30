package org.bukkit; import org.bukkit.plugin.*; import org.bukkit.inventory.*; import org.bukkit.command.CommandSender; import org.bukkit.entity.Player; import org.bukkit.scheduler.BukkitScheduler; import org.bukkit.scheduler.BukkitTask;
public class Bukkit {
    public static PluginManager manager; public static Inventory created; public static String title; public static int size;
    public static java.util.Map<Integer,ItemStack> slots; public static final java.util.List<String> dispatched = new java.util.ArrayList<>();
    public static final CommandSender console = message -> {};
    public static java.util.List<Player> online = new java.util.ArrayList<>();
    public static final java.util.List<Runnable> tasks = new java.util.ArrayList<>();
    public static final BukkitScheduler scheduler = (plugin,task,delay,period) -> {tasks.add(task);return new BukkitTask(){public void cancel(){}public int getTaskId(){return tasks.size();}};};
    public static BukkitScheduler getScheduler(){return scheduler;}
    public static java.util.Collection<? extends Player> getOnlinePlayers(){return online;}
    public static PluginManager getPluginManager(){return manager;}
    public static CommandSender getConsoleSender(){return console;}
    public static boolean dispatchCommand(CommandSender sender,String command){if(!dispatchWorks)return false;dispatched.add(command);return true;}
    public static boolean dispatchWorks=true;
    public static Inventory createInventory(InventoryHolder h,int n,String title){Bukkit.title=title;Bukkit.size=n;slots=new java.util.HashMap<>();created=new Inventory(){public void setItem(int slot,ItemStack item){slots.put(slot,item);}public InventoryHolder getHolder(){return h;}};return created;}
}
