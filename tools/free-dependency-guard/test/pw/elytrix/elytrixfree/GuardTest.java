package pw.elytrix.elytrixfree;
import java.util.*;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
public class GuardTest {
  static final class P implements Player { int messages; public void sendMessage(String s) { if(s==null || s.isEmpty()) throw new AssertionError(); messages++; } }
  public static void main(String[] x) {
    P p=new P();
    Bukkit.pluginManager=name -> false;
    if (!CaseDependencyGuard.canClaim(p,List.of("p give A 5"))) throw new AssertionError("noncase blocked");
    if (CaseDependencyGuard.canClaim(p,List.of(" /BcAsEs give A money 1")) || p.messages!=1) throw new AssertionError("case not blocked");
    if (CaseDependencyGuard.canClaim(p,List.of("bcases:bcases give A money 1"))) throw new AssertionError("namespaced label");
    if (!CaseDependencyGuard.canClaim(p,List.of("bcasesextra do"))) throw new AssertionError("unrelated");
    Bukkit.pluginManager=name -> name.equals("BCases");
    if (!CaseDependencyGuard.canClaim(p, List.of("bcases give A money 1"))) throw new AssertionError("enabled blocked");
    Bukkit.pluginManager=null;
    if (CaseDependencyGuard.canClaim(p,List.of("bcases give A money 1"))) throw new AssertionError("null manager");
    if (CaseDependencyGuard.canClaim(p,null)) throw new AssertionError("null commands");
    System.out.println("CaseDependencyGuard tests passed");
  }
}
