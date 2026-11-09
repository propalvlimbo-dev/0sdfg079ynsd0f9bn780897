package cs.cloudstudio.deobf;
import org.bukkit.Bukkit;import org.bukkit.entity.Player;import org.bukkit.plugin.*;import yo.tallen.utils.Data;
public class QuestTest {
 static class Cake implements Plugin { boolean enabled=true; public boolean isEnabled(){return enabled;} }
 static class P implements Player {boolean allowed; public boolean hasPermission(String n){return allowed;} public String getName(){return "Tester";} }
 static void check(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[] args){
  Cake cake=new Cake(); Bukkit.manager=n->cake; P player=new P();
  Data.active=false;check(!CakeSubPermission.check(player,"cloudquests.skipquest"));
  Data.active=true;check(CakeSubPermission.check(player,"cloudquests.skipquest"));
  check(!CakeSubPermission.check(player,"other.permission")); cake.enabled=false;check(!CakeSubPermission.check(player,"cloudquests.skipquest"));
  player.allowed=true;check(CakeSubPermission.check(player,"cloudquests.skipquest"));
  Bukkit.manager=n->null; player.allowed=false;check(!CakeSubPermission.check(player,"cloudquests.skipquest"));
  System.out.println("Quest permission mock tests passed");
 }
}
