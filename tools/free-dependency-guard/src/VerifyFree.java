import java.nio.file.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;
import org.objectweb.asm.tree.analysis.*;
/** Check bytecode stack flow and placement before all original instructions. */
public class VerifyFree {
 public static void main(String[] args) throws Exception {
  ClassNode c=new ClassNode(); new ClassReader(Files.readAllBytes(Path.of(args[0]))).accept(c,0); int found=0;
  for(MethodNode m:c.methods) {
   if((m.access & (Opcodes.ACC_ABSTRACT | Opcodes.ACC_NATIVE))==0) new Analyzer<>(new BasicVerifier()).analyze(c.name,m);
   if(!m.name.equals("claim") || !m.desc.equals("(Lorg/bukkit/entity/Player;Lpw/elytrix/elytrixfree/MenuConfig$Reward;)V")) continue;
   found++; AbstractInsnNode p=m.instructions.getFirst(); while(p!=null && p.getOpcode()<0) p=p.getNext();
   if(!(p instanceof VarInsnNode) || p.getOpcode()!=Opcodes.ALOAD || ((VarInsnNode)p).var!=1) throw new AssertionError("guard not first");
   int calls=0, mark=0; boolean checked=false;
   for(AbstractInsnNode n=m.instructions.getFirst();n!=null;n=n.getNext()) if(n instanceof MethodInsnNode) {
    MethodInsnNode x=(MethodInsnNode)n;
    if(x.owner.equals("pw/elytrix/elytrixfree/CaseDependencyGuard") && x.name.equals("canClaim")) { calls++; checked=true; }
    if(x.owner.equals("pw/elytrix/elytrixfree/DataStore") && x.name.equals("claim")) { if(!checked)throw new AssertionError("claim before guard"); mark++; }
   }
   if(calls!=1 || mark!=1) throw new AssertionError("wrong call counts");
  }
  if(found!=1) throw new AssertionError("wrong method count");
  System.out.println("BasicVerifier passed; guard before claim");
 }
}
