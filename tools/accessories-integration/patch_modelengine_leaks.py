#!/usr/bin/env python3
"""Fixes ModelEngine-4.1.0 HttpClient.newHttpClient() thread/off-heap leaks in MojangAPI & UserLimbRegistry and unclosed FileReader in UserLimbRegistry.tryLoad."""
import hashlib
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ME_JAR = ROOT / 'plugins/ModelEngine-4.1.0.jar'
BLIB_JAR = ROOT / 'plugins/BLib.jar'

MOJANG_ENTRY = 'com/ticxo/modelengine/api/utils/MojangAPI.class'
LIMB_ENTRY = 'com/ticxo/modelengine/api/model/limb/UserLimbRegistry.class'

PATCHER_JAVA = r"""
import java.io.*;
import java.nio.file.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;
import org.objectweb.asm.util.*;

public class PatchMELeaks {
    public static void main(String[] args) throws Exception {
        Path mojangPath = Path.of(args[0]);
        Path limbPath = Path.of(args[1]);

        patchMojangAPI(mojangPath);
        patchUserLimbRegistry(limbPath);
    }

    private static void patchMojangAPI(Path path) throws Exception {
        ClassReader cr = new ClassReader(Files.readAllBytes(path));
        ClassNode cn = new ClassNode();
        cr.accept(cn, 0);

        boolean foundField = false;
        for (FieldNode fn : cn.fields) {
            if ("CLIENT".equals(fn.name) && "Ljava/net/http/HttpClient;".equals(fn.desc)) {
                fn.access = Opcodes.ACC_PUBLIC | Opcodes.ACC_STATIC | Opcodes.ACC_FINAL;
                foundField = true;
            }
        }
        if (!foundField) throw new IllegalStateException("MojangAPI.CLIENT field missing");

        int clientRefs = 0;
        for (MethodNode mn : cn.methods) {
            if ("<clinit>".equals(mn.name)) continue;
            for (AbstractInsnNode insn = mn.instructions.getFirst(); insn != null; insn = insn.getNext()) {
                if (insn instanceof MethodInsnNode mi
                        && mi.getOpcode() == Opcodes.INVOKESTATIC
                        && "java/net/http/HttpClient".equals(mi.owner)
                        && "newHttpClient".equals(mi.name)
                        && "()Ljava/net/http/HttpClient;".equals(mi.desc)) {
                    mn.instructions.set(insn, new FieldInsnNode(
                            Opcodes.GETSTATIC,
                            "com/ticxo/modelengine/api/utils/MojangAPI",
                            "CLIENT",
                            "Ljava/net/http/HttpClient;"));
                    clientRefs++;
                } else if (insn instanceof FieldInsnNode fi
                        && fi.getOpcode() == Opcodes.GETSTATIC
                        && "com/ticxo/modelengine/api/utils/MojangAPI".equals(fi.owner)
                        && "CLIENT".equals(fi.name)) {
                    clientRefs++;
                }
            }
        }
        if (clientRefs < 1) throw new IllegalStateException("Expected MojangAPI.CLIENT usage in non-<clinit> methods, got " + clientRefs);

        ClassWriter cw = new ClassWriter(cr, 0);
        cn.accept(cw);
        byte[] out = cw.toByteArray();
        verify(out);
        Files.write(path, out);
        System.out.println("Patched MojangAPI.class (shared MojangAPI.CLIENT refs=" + clientRefs + ")");
    }

    private static void patchUserLimbRegistry(Path path) throws Exception {
        ClassReader cr = new ClassReader(Files.readAllBytes(path));
        ClassNode cn = new ClassNode();
        cr.accept(cn, 0);

        int clientRefs = 0;
        int readerFixed = 0;
        for (MethodNode mn : cn.methods) {
            for (AbstractInsnNode insn = mn.instructions.getFirst(); insn != null; insn = insn.getNext()) {
                if (insn instanceof MethodInsnNode mi
                        && mi.getOpcode() == Opcodes.INVOKESTATIC
                        && "java/net/http/HttpClient".equals(mi.owner)
                        && "newHttpClient".equals(mi.name)
                        && "()Ljava/net/http/HttpClient;".equals(mi.desc)) {
                    mn.instructions.set(insn, new FieldInsnNode(
                            Opcodes.GETSTATIC,
                            "com/ticxo/modelengine/api/utils/MojangAPI",
                            "CLIENT",
                            "Ljava/net/http/HttpClient;"));
                    clientRefs++;
                } else if (insn instanceof FieldInsnNode fi
                        && fi.getOpcode() == Opcodes.GETSTATIC
                        && "com/ticxo/modelengine/api/utils/MojangAPI".equals(fi.owner)
                        && "CLIENT".equals(fi.name)) {
                    clientRefs++;
                }
            }

            if ("tryLoad".equals(mn.name) && "(Ljava/lang/String;)Z".equals(mn.desc)) {
                for (AbstractInsnNode insn = mn.instructions.getFirst(); insn != null; insn = insn.getNext()) {
                    if (insn instanceof TypeInsnNode ti
                            && ti.getOpcode() == Opcodes.NEW
                            && "java/io/FileReader".equals(ti.desc)) {
                        // Sequence: NEW FileReader, DUP, ALOAD 6, INVOKESPECIAL FileReader.<init>(File)V,
                        //           LDC UserLimbCache.class, INVOKEVIRTUAL Gson.fromJson(Reader, Class)Object
                        AbstractInsnNode dup = ti.getNext();
                        AbstractInsnNode aloadFile = dup.getNext();
                        AbstractInsnNode init = aloadFile.getNext();
                        AbstractInsnNode ldc = init.getNext();
                        AbstractInsnNode fromJson = ldc.getNext();
                        if (!(aloadFile instanceof VarInsnNode vf && vf.getOpcode() == Opcodes.ALOAD)
                                || !(init instanceof MethodInsnNode miInit && "<init>".equals(miInit.name))
                                || !(fromJson instanceof MethodInsnNode miGson && "fromJson".equals(miGson.name))) {
                            throw new IllegalStateException("Unexpected FileReader instruction sequence in tryLoad");
                        }
                        InsnList repl = new InsnList();
                        repl.add(new VarInsnNode(Opcodes.ALOAD, vf.var));
                        repl.add(new MethodInsnNode(Opcodes.INVOKEVIRTUAL, "java/io/File", "toPath", "()Ljava/nio/file/Path;", false));
                        repl.add(new FieldInsnNode(Opcodes.GETSTATIC, "java/nio/charset/StandardCharsets", "UTF_8", "Ljava/nio/charset/Charset;"));
                        repl.add(new MethodInsnNode(Opcodes.INVOKESTATIC, "java/nio/file/Files", "readString", "(Ljava/nio/file/Path;Ljava/nio/charset/Charset;)Ljava/lang/String;", false));
                        mn.instructions.insertBefore(ti, repl);
                        mn.instructions.remove(ti);
                        mn.instructions.remove(dup);
                        mn.instructions.remove(aloadFile);
                        mn.instructions.remove(init);
                        ((MethodInsnNode) fromJson).desc = "(Ljava/lang/String;Ljava/lang/Class;)Ljava/lang/Object;";
                        mn.maxStack = Math.max(mn.maxStack, 4);
                        readerFixed++;
                        break;
                    } else if (insn instanceof MethodInsnNode miRead
                            && "java/nio/file/Files".equals(miRead.owner)
                            && "readString".equals(miRead.name)) {
                        readerFixed++;
                        break;
                    }
                }
            }
        }
        if (clientRefs < 1) throw new IllegalStateException("Expected MojangAPI.CLIENT usage in UserLimbRegistry, got " + clientRefs);
        if (readerFixed != 1) throw new IllegalStateException("Expected 1 Files.readString fix in UserLimbRegistry.tryLoad, got " + readerFixed);

        ClassWriter cw = new ClassWriter(cr, 0);
        cn.accept(cw);
        byte[] out = cw.toByteArray();
        verify(out);
        Files.write(path, out);
        System.out.println("Patched UserLimbRegistry.class (shared MojangAPI.CLIENT refs=" + clientRefs + ", Files.readString=" + readerFixed + ")");
    }

    private static void verify(byte[] bytes) throws Exception {
        ClassReader cr = new ClassReader(bytes);
        cr.accept(new CheckClassAdapter(new ClassWriter(0), true), ClassReader.EXPAND_FRAMES);
        ClassNode cn = new ClassNode();
        cr.accept(cn, 0);
        org.objectweb.asm.tree.analysis.Analyzer<org.objectweb.asm.tree.analysis.BasicValue> analyzer =
                new org.objectweb.asm.tree.analysis.Analyzer<>(new org.objectweb.asm.tree.analysis.BasicVerifier());
        for (MethodNode mn : cn.methods) {
            analyzer.analyze(cn.name, mn);
        }
    }
}
"""


def main():
    java = os.environ['JAVA']
    ecj = os.environ['ECJ']
    asm_jar = str(BLIB_JAR)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        (tmp_dir / 'PatchMELeaks.java').write_text(PATCHER_JAVA, encoding='utf-8')
        subprocess.run([java, '-jar', ecj, '-21', '-proc:none', '-cp', asm_jar,
                        '-d', str(tmp_dir), str(tmp_dir / 'PatchMELeaks.java')], check=True)

        mojang_cls = tmp_dir / 'MojangAPI.class'
        limb_cls = tmp_dir / 'UserLimbRegistry.class'
        with zipfile.ZipFile(ME_JAR, 'r') as zf:
            mojang_cls.write_bytes(zf.read(MOJANG_ENTRY))
            limb_cls.write_bytes(zf.read(LIMB_ENTRY))

        subprocess.run([java, '-Xverify:all', '-cp', f'{tmp_dir}:{asm_jar}',
                        'PatchMELeaks', str(mojang_cls), str(limb_cls)], check=True)

        new_mojang = mojang_cls.read_bytes()
        new_limb = limb_cls.read_bytes()

        out_jar = tmp_dir / 'ModelEngine-patched.jar'
        with zipfile.ZipFile(ME_JAR, 'r') as src, zipfile.ZipFile(out_jar, 'w') as dst:
            for info in src.infolist():
                if info.filename == MOJANG_ENTRY:
                    dst.writestr(info, new_mojang)
                elif info.filename == LIMB_ENTRY:
                    dst.writestr(info, new_limb)
                else:
                    dst.writestr(info, src.read(info.filename))

        with zipfile.ZipFile(out_jar, 'r') as check_zf:
            assert check_zf.testzip() is None

        shutil.move(str(out_jar), str(ME_JAR))
        print('Updated:', ME_JAR, hashlib.sha256(ME_JAR.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
