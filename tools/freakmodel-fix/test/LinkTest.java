import java.nio.file.*;
import java.util.*;
import org.objectweb.asm.*;
/** Checks all plugin method references to either replaced class against the actual jar. */
public class LinkTest implements Opcodes {
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]); String prefix="pw/elytrix/freakmodel/";
        Map<String, Set<String>> methods=new HashMap<>();
        for(String type: List.of("PlayerBodyTracker", "WornAngelRig")) {
            String owner=prefix+type; Set<String> entries=new HashSet<>(); methods.put(owner,entries);
            new ClassReader(Files.readAllBytes(root.resolve(owner+".class"))).accept(new ClassVisitor(ASM9) {
                @Override public MethodVisitor visitMethod(int access, String name, String desc, String signature, String[] exceptions) {
                    if ((access & ACC_PUBLIC)!=0) entries.add(name+desc); return null;
                }
            }, ClassReader.SKIP_CODE);
        }
        Set<String> refs=new HashSet<>();
        try (var files=Files.list(root.resolve(prefix))) {
            for (Path file: files.filter(p -> p.toString().endsWith(".class")).toList()) {
                String className=prefix+file.getFileName().toString().replaceFirst("\\.class$", "");
                if (methods.containsKey(className)) continue;
                new ClassReader(Files.readAllBytes(file)).accept(new ClassVisitor(ASM9) {
                    @Override public MethodVisitor visitMethod(int access, String name, String desc, String signature, String[] exceptions) {
                        return new MethodVisitor(ASM9) {
                            @Override public void visitMethodInsn(int opcode, String owner, String name, String desc, boolean itf) {
                                if(methods.containsKey(owner)) {
                                    refs.add(owner+"."+name+desc);
                                    if(!methods.get(owner).contains(name+desc)) throw new AssertionError("Missing "+owner+"."+name+desc);
                                }
                            }
                        };
                    }
                }, 0);
            }
        }
        for(String expected: List.of(prefix+"PlayerBodyTracker.resetToPlayer(Lorg/bukkit/entity/Player;)V", prefix+"WornAngelRig.<init>(Ljava/util/UUID;Lorg/bukkit/World;)V", prefix+"WornAngelRig.requestPassengerResync()V"))
            if(!refs.contains(expected)) throw new AssertionError("Expected reference not checked: "+expected);
        System.out.println("Plugin linkage checks passed ("+refs.size()+" method references)");
    }
}
