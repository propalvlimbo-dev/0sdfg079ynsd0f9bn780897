import org.objectweb.asm.*; import java.nio.file.*;
public class PatchTMath {
 public static void main(String[] a)throws Exception {
  ClassReader cr=new ClassReader(Files.readAllBytes(Path.of(a[0]))); ClassWriter cw=new ClassWriter(cr,0);
  cr.accept(new ClassVisitor(Opcodes.ASM9,cw){public MethodVisitor visitMethod(int x,String n,String d,String s,String[]e){
   MethodVisitor m=super.visitMethod(x,n,d,s,e); if(!n.equals("<clinit>"))return m;
   m.visitCode();m.visitInsn(Opcodes.FCONST_0);m.visitFieldInsn(Opcodes.PUTSTATIC,"com/ticxo/modelengine/api/utils/math/TMath","LOWER_SCALE_LIMIT","F");m.visitLdcInsn(.001d);m.visitFieldInsn(Opcodes.PUTSTATIC,"com/ticxo/modelengine/api/utils/math/TMath","MOVEMENT_RESOLUTION","D");m.visitInsn(Opcodes.RETURN);m.visitMaxs(2,0);m.visitEnd();return null;
  }},0);Path p=Path.of(a[1]);Files.createDirectories(p.getParent());Files.write(p,cw.toByteArray());
 }
}
