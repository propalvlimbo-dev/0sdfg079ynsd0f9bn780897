import java.nio.file.*; import org.objectweb.asm.*; import org.objectweb.asm.tree.*; import org.objectweb.asm.tree.analysis.*;
public class VerifyAccessory {
 public static void main(String[] a)throws Exception {
  ClassNode c=new ClassNode();new ClassReader(Files.readAllBytes(Path.of(a[0]))).accept(c,0); int install=0,halo=0,back=0,old=0;
  for(MethodNode m:c.methods){
   new Analyzer<BasicValue>(new BasicVerifier()).analyze(c.name,m);
   for(AbstractInsnNode i:m.instructions)if(i instanceof MethodInsnNode x){
    if(x.owner.endsWith("/AccessoryController")){if(x.name.equals("install"))install++; if(x.name.equals("halo"))halo++;if(x.name.equals("back"))back++;}
    if(m.name.equals("syncPlayerWornAngelRig") && x.name.equals("resolveWornArmorSpec"))old++;
   }
  }
  if(install!=1||halo!=1||back!=1||old!=0)throw new AssertionError("hook mismatch");
  System.out.println("ASM BasicVerifier and accessory hooks passed");
 }
}
