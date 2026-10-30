import java.nio.file.*;
import org.objectweb.asm.*;

/** Adds the two ABI entry points expected by the older plugin main class. */
public class PatchRig implements Opcodes {
    public static void main(String[] args) throws Exception {
        Path path = Path.of(args[0]);
        ClassReader reader = new ClassReader(Files.readAllBytes(path));
        ClassWriter writer = new ClassWriter(reader, ClassWriter.COMPUTE_MAXS);
        reader.accept(new ClassVisitor(ASM9, writer) {
            boolean constructor, resync;
            @Override public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] exceptions) {
                if (name.equals("<init>") && desc.equals("(Ljava/util/UUID;Lorg/bukkit/World;)V")) constructor = true;
                if (name.equals("requestPassengerResync") && desc.equals("()V")) resync = true;
                return super.visitMethod(access, name, desc, sig, exceptions);
            }
            @Override public void visitEnd() {
                if (constructor || resync) throw new IllegalStateException("Already patched or unexpected input");
                String owner = "pw/elytrix/freakmodel/WornAngelRig";
                MethodVisitor m = super.visitMethod(ACC_PUBLIC, "<init>", "(Ljava/util/UUID;Lorg/bukkit/World;)V", null, null);
                m.visitCode(); m.visitVarInsn(ALOAD, 0); m.visitVarInsn(ALOAD, 1);
                m.visitMethodInsn(INVOKESTATIC, "org/bukkit/Bukkit", "getPlayer", "(Ljava/util/UUID;)Lorg/bukkit/entity/Player;", false);
                m.visitMethodInsn(INVOKESPECIAL, owner, "<init>", "(Lorg/bukkit/entity/Player;)V", false);
                m.visitInsn(RETURN); m.visitMaxs(0, 0); m.visitEnd();
                m = super.visitMethod(ACC_PUBLIC, "requestPassengerResync", "()V", null, null);
                m.visitCode(); m.visitVarInsn(ALOAD, 0); m.visitIntInsn(BIPUSH, 40);
                m.visitFieldInsn(PUTFIELD, owner, "warmupSyncTicks", "I");
                m.visitVarInsn(ALOAD, 0); m.visitLdcInsn(Integer.MIN_VALUE);
                m.visitFieldInsn(PUTFIELD, owner, "lastMountedVehicleId", "I");
                m.visitInsn(RETURN); m.visitMaxs(0, 0); m.visitEnd();
                super.visitEnd();
            }
        }, 0);
        Files.write(path, writer.toByteArray());
    }
}
