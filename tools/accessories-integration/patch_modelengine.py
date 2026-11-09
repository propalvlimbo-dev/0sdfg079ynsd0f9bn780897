#!/usr/bin/env python3
"""Removes the 12-blueprint import cap (BIPUSH 12 -> SIPUSH 8192) in ModelEngine-4.1.0.jar."""
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ME_JAR = ROOT / 'plugins/ModelEngine-4.1.0.jar'
TARGET_ENTRY = 'com/ticxo/modelengine/core/generator/ModelGeneratorImpl.class'

PATCHER_JAVA = r"""
import java.nio.file.*;
import org.objectweb.asm.*;
import org.objectweb.asm.tree.*;

public class PatchME {
    public static void main(String[] args) throws Exception {
        Path clsPath = Path.of(args[0]);
        byte[] bytes = Files.readAllBytes(clsPath);
        ClassReader cr = new ClassReader(bytes);
        ClassNode cn = new ClassNode();
        cr.accept(cn, 0);

        int patched = 0;
        for (MethodNode mn : cn.methods) {
            if ("importModelsInternal".equals(mn.name) && "(Z)V".equals(mn.desc)) {
                for (AbstractInsnNode insn = mn.instructions.getFirst(); insn != null; insn = insn.getNext()) {
                    if (insn instanceof IntInsnNode ii
                            && ii.getOpcode() == Opcodes.BIPUSH
                            && ii.operand == 12) {
                        AbstractInsnNode prev = insn.getPrevious();
                        while (prev != null && prev.getOpcode() == -1) prev = prev.getPrevious();
                        if (prev instanceof MethodInsnNode mi && "size".equals(mi.name)) {
                            mn.instructions.set(insn, new IntInsnNode(Opcodes.SIPUSH, 8192));
                            patched++;
                        }
                    }
                    if (insn instanceof IntInsnNode ii2
                            && ii2.getOpcode() == Opcodes.SIPUSH
                            && ii2.operand == 8192) {
                        patched++;
                    }
                }
            }
        }
        if (patched != 1) {
            throw new IllegalStateException("Expected 1 patched import cap in ModelGeneratorImpl, got " + patched);
        }
        ClassWriter cw = new ClassWriter(cr, 0);
        cn.accept(cw);
        Files.write(clsPath, cw.toByteArray());
        System.out.println("Patched ModelGeneratorImpl.importModelsInternal cap -> 8192");
    }
}
"""


def main():
    java = os.environ['JAVA']
    ecj = os.environ['ECJ']
    asm_jar = '/tmp/tools/package/deps/tiny-remapper-0.14.1-fat.jar'

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        (tmp_dir / 'PatchME.java').write_text(PATCHER_JAVA, encoding='utf-8')
        subprocess.run([java, '-jar', ecj, '-21', '-proc:none', '-cp', asm_jar,
                        '-d', str(tmp_dir), str(tmp_dir / 'PatchME.java')], check=True)

        cls_file = tmp_dir / 'ModelGeneratorImpl.class'
        with zipfile.ZipFile(ME_JAR, 'r') as zf:
            cls_file.write_bytes(zf.read(TARGET_ENTRY))

        subprocess.run([java, '-cp', f'{tmp_dir}:{asm_jar}', 'PatchME', str(cls_file)], check=True)
        new_cls = cls_file.read_bytes()

        out_jar = tmp_dir / 'ModelEngine-patched.jar'
        with zipfile.ZipFile(ME_JAR, 'r') as src, zipfile.ZipFile(out_jar, 'w') as dst:
            for info in src.infolist():
                data = new_cls if info.filename == TARGET_ENTRY else src.read(info.filename)
                dst.writestr(info, data)

        with zipfile.ZipFile(out_jar, 'r') as check_zf:
            assert check_zf.testzip() is None

        shutil.move(str(out_jar), str(ME_JAR))
        print('Updated:', ME_JAR)


if __name__ == '__main__':
    main()
