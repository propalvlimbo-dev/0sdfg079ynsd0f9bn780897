import org.bxteam.divinemc.config.DivineConfig;
import java.util.concurrent.*;
public class BootstrapTest {
 static class Server {
  final ExecutorService chat=DivineConfig.PerformanceCategory.virtualThreadsEnabled && DivineConfig.PerformanceCategory.virtualChatScheduler
    ? Executors.newVirtualThreadPerTaskExecutor() : Executors.newCachedThreadPool();
 }
 public static void main(String[] args){
  Server server=new Server();
  DivineConfig.PerformanceCategory.loadDisabledConfig(); // DivineMC config is read only after constructor
  try { ((ThreadPoolExecutor)server.chat).setCorePoolSize(0);System.out.println("CHAT BOOTSTRAP OK"); }
  finally {server.chat.shutdownNow();}
 }
}
