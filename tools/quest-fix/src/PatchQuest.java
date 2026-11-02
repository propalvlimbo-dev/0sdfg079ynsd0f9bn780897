import java.nio.file.*;
import org.objectweb.asm.*;
/** Replace the single permission check in the skip command, preserving old semantics. */
public final class PatchQuest implements Opcodes {
 public static void main(String[] args) throws Exception {
  Path path=Path.of(args[0]);ClassReader r=new ClassReader(Files.readAllBytes(path));ClassWriter w=new ClassWriter(r,0);final int[] count={0};
  r.accept(new ClassVisitor(ASM9,w){
   @Override public MethodVisitor visitMethod(int access,String name,String desc,String sig,String[] exc) {
    MethodVisitor m=super.visitMethod(access,name,desc,sig,exc);
    if(!name.equals("method_0019") || !desc.equals("(Lorg/bukkit/command/CommandSender;Lorg/bukkit/command/Command;Ljava/lang/String;[Ljava/lang/String;)Z")) return m;
    return new MethodVisitor(ASM9,m){
     @Override public void visitMethodInsn(int op,String owner,String n,String d,boolean itf){
      if(op==INVOKEINTERFACE && owner.equals("org/bukkit/entity/Player") && n.equals("hasPermission") && d.equals("(Ljava/lang/String;)Z")) {
       count[0]++;super.visitMethodInsn(INVOKESTATIC,"cs/cloudstudio/deobf/CakeSubPermission","check","(Lorg/bukkit/entity/Player;Ljava/lang/String;)Z",false);
      } else super.visitMethodInsn(op,owner,n,d,itf);
     }
    };
   }
  },0);
  if(count[0]!=1) throw new IllegalStateException("unexpected permission check count: "+count[0]);
  Files.write(path,w.toByteArray());
 }
}
