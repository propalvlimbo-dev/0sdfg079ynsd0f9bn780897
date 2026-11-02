import org.objectweb.asm.*;
import java.nio.file.*;

/** Replace just the obsolete reflective title sender, preserving all other methods. */
public class PatchTitle {
  public static void main(String[] args) throws Exception {
    if (args.length != 2) throw new IllegalArgumentException("input.class output.class");
    ClassReader reader = new ClassReader(Files.readAllBytes(Path.of(args[0])));
    ClassWriter writer = new ClassWriter(reader, 0);
    int[] count = {0};
    reader.accept(new ClassVisitor(Opcodes.ASM9, writer) {
      @Override public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
        if (name.equals("sendTitle") && desc.equals("(Lorg/bukkit/entity/Player;Ljava/lang/String;Ljava/lang/String;III)V")) {
          if ((access & Opcodes.ACC_STATIC) == 0 || ++count[0] != 1) throw new IllegalStateException("unexpected method");
          MethodVisitor mv = super.visitMethod(access, name, desc, sig, ex);
          mv.visitCode();
          mv.visitVarInsn(Opcodes.ALOAD, 0); mv.visitVarInsn(Opcodes.ALOAD, 1); mv.visitVarInsn(Opcodes.ALOAD, 2);
          mv.visitVarInsn(Opcodes.ILOAD, 3); mv.visitVarInsn(Opcodes.ILOAD, 4); mv.visitVarInsn(Opcodes.ILOAD, 5);
          mv.visitMethodInsn(Opcodes.INVOKEINTERFACE, "org/bukkit/entity/Player", "sendTitle", "(Ljava/lang/String;Ljava/lang/String;III)V", true);
          mv.visitInsn(Opcodes.RETURN); mv.visitMaxs(6, 6); mv.visitEnd();
          return null;
        }
        return super.visitMethod(access, name, desc, sig, ex);
      }
    }, 0);
    if (count[0] != 1) throw new IllegalStateException("title method not found");
    Files.write(Path.of(args[1]), writer.toByteArray());
  }
}
