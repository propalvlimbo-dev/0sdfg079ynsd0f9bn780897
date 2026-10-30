package elytrix;

import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.security.ProtectionDomain;
import java.nio.charset.StandardCharsets;

/** Narrow startup-only workaround for DivineMC #30's early virtual executor. */
public final class EarlyThreadFix {
    private static final String TARGET="org/bxteam/divinemc/config/DivineConfig$PerformanceCategory";
    public static void premain(String args, Instrumentation inst) {
        System.out.println("[Elytrix early-chat-fix] agent active; waiting for DivineMC config class");
        inst.addTransformer(new ClassFileTransformer() {
            @Override public byte[] transform(ClassLoader loader, String name, Class<?> type, ProtectionDomain domain, byte[] source) {
                if (!TARGET.equals(name)) return null;
                try {
                    byte[] changed=source.clone(); patch(changed);
                    System.out.println("[Elytrix early-chat-fix] disabled virtual threads before server construction");
                    return changed;
                } catch (Throwable ex) {
                    System.err.println("[Elytrix early-chat-fix] ERROR: unexpected DivineMC bytecode, original class unchanged: " + ex);
                    return null;
                }
            }
        });
    }
    private static int u1(byte[] b,int p) {return b[p]&255;}
    private static int u2(byte[] b,int p) {return (u1(b,p)<<8)|u1(b,p+1);}
    private static int u4(byte[] b,int p) {return (u2(b,p)<<16)|u2(b,p+2);}
    private static int attributes(byte[] b,int p) {
        int count=u2(b,p);p+=2;
        for(int i=0;i<count;i++){int len=u4(b,p+2);if(len<0)throw new IllegalArgumentException("invalid attribute");p+=6+len;}
        return p;
    }
    public static void patch(byte[] b) {
        if(u4(b,0)!=0xCAFEBABE)throw new IllegalArgumentException("not a class file");
        int count=u2(b,8),p=10;String[] utf=new String[count];int[] tag=new int[count],a=new int[count],c=new int[count];
        for(int i=1;i<count;i++) {
            int t=tag[i]=u1(b,p++);
            switch(t) {
              case 1: int length=u2(b,p);p+=2;utf[i]=new String(b,p,length,StandardCharsets.UTF_8);p+=length;break;
              case 3: case 4: p+=4;break;
              case 5: case 6: p+=8;i++;break;
              case 7: case 8: case 16: case 19: case 20: a[i]=u2(b,p);p+=2;break;
              case 9: case 10: case 11: case 12: case 17: case 18: a[i]=u2(b,p);c[i]=u2(b,p+2);p+=4;break;
              case 15: p+=3;break;
              default:throw new IllegalArgumentException("unknown constant pool tag "+t);
            }
        }
        int field=0;
        for(int i=1;i<count;i++) if(tag[i]==9 && tag[a[i]]==7 && tag[c[i]]==12 && TARGET.equals(utf[a[a[i]]]) && "virtualThreadsEnabled".equals(utf[a[c[i]]]) && "Z".equals(utf[c[c[i]]])) {
            if(field!=0)throw new IllegalArgumentException("duplicate target field");field=i;
        }
        if(field==0)throw new IllegalArgumentException("target field not found");
        p+=6;int interfaces=u2(b,p);p+=2+interfaces*2;
        int fields=u2(b,p);p+=2;
        for(int i=0;i<fields;i++)p=attributes(b,p+6);
        int methods=u2(b,p);p+=2;int found=0,pos=-1;
        for(int i=0;i<methods;i++) {
            String name=utf[u2(b,p+2)];int q=p+6,attrs=u2(b,q);q+=2;
            for(int j=0;j<attrs;j++) {
                String attr=utf[u2(b,q)];int len=u4(b,q+2);
                if(len<0)throw new IllegalArgumentException("invalid code length");
                if("<clinit>".equals(name)&&"Code".equals(attr)) {
                    int codeLength=u4(b,q+10),start=q+14,end=start+codeLength;
                    if(codeLength<0||end>q+6+len)throw new IllegalArgumentException("invalid bytecode");
                    for(int k=start;k+3<end;k++) if(u1(b,k)==4 && u1(b,k+1)==179 && u2(b,k+2)==field){found++;pos=k;}
                }
                q+=6+len;
            }
            p=q;
        }
        if(found!=1)throw new IllegalArgumentException("expected one static initialization; found "+found);
        b[pos]=3; // iconst_1 -> iconst_0, all control flow and frames unchanged
    }
}
