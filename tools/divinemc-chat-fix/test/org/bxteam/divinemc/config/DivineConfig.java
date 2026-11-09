package org.bxteam.divinemc.config;
public class DivineConfig {
 public static class PerformanceCategory {
  public static boolean virtualThreadsEnabled=true;
  public static boolean virtualBukkitScheduler=true;
  public static boolean virtualChatScheduler=true;
  public static void loadDisabledConfig(){virtualThreadsEnabled=false;}
 }
}
