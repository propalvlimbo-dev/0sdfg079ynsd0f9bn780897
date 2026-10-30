import java.nio.file.*;
import org.objectweb.asm.*;
/** Injects one backwards-compatible check into the known CloudEnchants manager. */
public final class PatchCompat implements Opcodes {
    public static void main(String[] args) throws Exception {
        Path path=Path.of(args[0]);
        ClassReader r=new ClassReader(Files.readAllBytes(path));
        ClassWriter w=new ClassWriter(r,ClassWriter.COMPUTE_MAXS);
        final int[] count={0};
        r.accept(new ClassVisitor(ASM9,w){
            @Override public MethodVisitor visitMethod(int access,String name,String desc,String sig,String[] exc) {
                MethodVisitor m=super.visitMethod(access,name,desc,sig,exc);
                if(!name.equals("has") || !desc.equals("(Lorg/bukkit/inventory/ItemStack;Lcs/cloudstudio/recovered/cloudenchants/CustomEnchant;)Z")) return m;
                count[0]++;
                return new MethodVisitor(ASM9,m){
                    @Override public void visitCode() {
                        super.visitCode(); Label original=new Label();
                        super.visitVarInsn(ALOAD,1);super.visitVarInsn(ALOAD,2);
                        super.visitMethodInsn(INVOKESTATIC,"cs/cloudstudio/recovered/cloudenchants/LegacyEnchantCompat","has","(Lorg/bukkit/inventory/ItemStack;Lcs/cloudstudio/recovered/cloudenchants/CustomEnchant;)Z",false);
                        super.visitJumpInsn(IFEQ,original);super.visitInsn(ICONST_1);super.visitInsn(IRETURN);
                        super.visitLabel(original);super.visitFrame(F_SAME,0,null,0,null);
                    }
                };
            }
        },0);
        if(count[0]!=1)throw new IllegalStateException("unexpected manager methods: "+count[0]);
        Files.write(path,w.toByteArray());
    }
}
