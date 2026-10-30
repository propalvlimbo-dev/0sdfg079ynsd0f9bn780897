import java.nio.file.*;
import org.objectweb.asm.*;
/**
 * Exact bytecode integration: register the accessories menu, override the two
 * armor-derived selections, tick the eyepatch, and run the worn rig every tick
 * (the stock build only syncs it every fourth tick, which made the kagune lag
 * behind the back and stutter while walking).
 */
public class PatchAccessory implements Opcodes {
 public static void main(String[] args) throws Exception {
  ClassReader reader=new ClassReader(Files.readAllBytes(Path.of(args[0])));
  String owner="pw/elytrix/freakmodel/ElytrixFreakModelPlugin";
  if(!reader.getClassName().equals(owner))throw new IllegalStateException("unexpected class");
  ClassWriter writer=new ClassWriter(reader,ClassWriter.COMPUTE_MAXS);int[] hooks={0,0,0,0,0};
  reader.accept(new ClassVisitor(ASM9,writer){
   public MethodVisitor visitMethod(int acc,String name,String desc,String sig,String[] exceptions){
    MethodVisitor m=super.visitMethod(acc,name,desc,sig,exceptions);
    if(name.equals("onEnable")&&desc.equals("()V")) return new MethodVisitor(ASM9,m){
     public void visitInsn(int opcode){
      if(opcode==RETURN){hooks[0]++;super.visitVarInsn(ALOAD,0);super.visitMethodInsn(INVOKESTATIC,"pw/elytrix/freakmodel/AccessoryController","install","(Lpw/elytrix/freakmodel/ElytrixFreakModelPlugin;)V",false);}
      super.visitInsn(opcode);
     }
    };
    if(name.equals("syncPlayerWornAngelRig")&&desc.equals("(Lorg/bukkit/entity/Player;)V"))return new MethodVisitor(ASM9,m){
     public void visitCode(){
      super.visitCode();hooks[3]++;
      super.visitVarInsn(ALOAD,0);super.visitVarInsn(ALOAD,1);
      super.visitMethodInsn(INVOKESTATIC,"pw/elytrix/freakmodel/AccessoryController","tickEyepatch","(Lpw/elytrix/freakmodel/ElytrixFreakModelPlugin;Lorg/bukkit/entity/Player;)V",false);
     }
     public void visitMethodInsn(int op,String own,String method,String d,boolean itf){
      if(own.equals(owner)&&method.equals("resolveWornArmorSpec")&&d.equals("(Lorg/bukkit/inventory/ItemStack;Lpw/elytrix/freakmodel/ModelKind;)Lpw/elytrix/freakmodel/FreakModelSpec;")){
       int index=++hooks[1];if(index>2)throw new IllegalStateException("unexpected resolver calls");
       super.visitInsn(POP); super.visitInsn(POP); super.visitVarInsn(ALOAD,1);
       super.visitMethodInsn(INVOKESTATIC,"pw/elytrix/freakmodel/AccessoryController",index==1?"halo":"back","(Lpw/elytrix/freakmodel/ElytrixFreakModelPlugin;Lorg/bukkit/entity/Player;)Lpw/elytrix/freakmodel/FreakModelSpec;",false); hooks[2]++;return;
      }
      super.visitMethodInsn(op,own,method,d,itf);
     }
    };
    if(name.equals("tickWornAngelRigs")&&desc.equals("()V"))return new MethodVisitor(ASM9,m){
     private boolean afterCounter;
     public void visitFieldInsn(int op,String own,String field,String d){
      super.visitFieldInsn(op,own,field,d);
      afterCounter=op==GETFIELD&&field.equals("globalTickCounter");
     }
     public void visitInsn(int opcode){
      if(afterCounter&&opcode==ICONST_4){afterCounter=false;hooks[4]++;super.visitInsn(ICONST_1);return;}
      afterCounter=false;super.visitInsn(opcode);
     }
    };
    return m;
   }
  },0);
  if(hooks[0]!=1||hooks[1]!=2||hooks[2]!=2||hooks[3]!=1||hooks[4]!=1)throw new IllegalStateException("hooks mismatch");
  Files.write(Path.of(args[1]),writer.toByteArray());
 }
}
