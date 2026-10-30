import java.nio.file.*;
import org.objectweb.asm.*;
/** Insert guard before any side effects in the one exact FreeMenu.claim method. */
public class PatchFree {
  public static void main(String[] a) throws Exception {
    if (a.length!=2) throw new IllegalArgumentException("input.class output.class");
    ClassReader cr=new ClassReader(Files.readAllBytes(Path.of(a[0])));
    if (!cr.getClassName().equals("pw/elytrix/elytrixfree/FreeMenu")) throw new IllegalStateException("wrong class");
    ClassWriter cw=new ClassWriter(cr,ClassWriter.COMPUTE_MAXS); int[] count={0};
    cr.accept(new ClassVisitor(Opcodes.ASM9,cw) {
      @Override public MethodVisitor visitMethod(int access,String name,String desc,String sig,String[] exceptions) {
        MethodVisitor mv=super.visitMethod(access,name,desc,sig,exceptions);
        if (!name.equals("claim") || !desc.equals("(Lorg/bukkit/entity/Player;Lpw/elytrix/elytrixfree/MenuConfig$Reward;)V")) return mv;
        if (++count[0]!=1 || (access & Opcodes.ACC_STATIC)!=0) throw new IllegalStateException("unexpected claim method");
        return new MethodVisitor(Opcodes.ASM9,mv) {
          @Override public void visitCode() {
            super.visitCode();
            super.visitVarInsn(Opcodes.ALOAD,1);
            super.visitVarInsn(Opcodes.ALOAD,2);
            super.visitFieldInsn(Opcodes.GETFIELD,"pw/elytrix/elytrixfree/MenuConfig$Reward","commands","Ljava/util/List;");
            super.visitMethodInsn(Opcodes.INVOKESTATIC,"pw/elytrix/elytrixfree/CaseDependencyGuard","canClaim","(Lorg/bukkit/entity/Player;Ljava/util/List;)Z",false);
            Label ok=new Label(); super.visitJumpInsn(Opcodes.IFNE,ok); super.visitInsn(Opcodes.RETURN); super.visitLabel(ok);
            super.visitFrame(Opcodes.F_SAME,0,null,0,null);
          }
        };
      }
    },0);
    if (count[0]!=1) throw new IllegalStateException("claim method missing");
    Files.write(Path.of(a[1]),cw.toByteArray());
  }
}
