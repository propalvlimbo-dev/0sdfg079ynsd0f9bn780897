import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.objectweb.asm.AnnotationVisitor;
import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassVisitor;
import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.FieldVisitor;
import org.objectweb.asm.Label;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;

public final class PatchAllPlugins {

    private PatchAllPlugins() {
    }

    public static void main(String[] args) throws IOException {
        if (args.length != 3) {
            throw new IllegalArgumentException("Usage: PatchAllPlugins <mode> <in.class> <out.class>");
        }
        String mode = args[0];
        byte[] in = Files.readAllBytes(Path.of(args[1]));
        byte[] out;
        switch (mode) {
            case "hjobs-jobmanager":
                out = patchHJobsJobManager(in);
                break;
            case "hjobs-playerlistener":
                out = patchHJobsPlayerListener(in);
                break;
            case "hjobs-guilistener":
                out = patchHJobsGuiListener(in);
                break;
            case "nclans-clan":
                out = patchNClansClan(in);
                break;
            case "nclans-placeholder":
                out = patchNClansPlaceholder(in);
                break;
            case "nclans-info":
                out = patchNClansInfo(in);
                break;
            case "nclans-levelconfig":
                out = patchNClansLevelConfig(in);
                break;
            case "gc-itemutils":
                out = patchGreatCombatItemUtils(in);
                break;
            case "gc-cooldownmanager":
                out = patchGreatCombatCooldownManager(in);
                break;
            case "gc-playerlistener":
                out = patchGreatCombatPlayerListener(in);
                break;
            case "duels-perf":
                out = patchDuelsPerf(in);
                break;
            case "duels-listener":
                out = patchDuelsListener(in);
                break;
            case "elytrixitems-trap":
                out = patchElytrixItemsTrap(in);
                break;
            case "nmascot-move":
                out = patchNMascotMove(in);
                break;
            case "itemkeep-datamanager":
                out = patchItemKeepDataManager(in);
                break;
            default:
                throw new IllegalArgumentException("Unknown mode: " + mode);
        }
        Files.write(Path.of(args[2]), out);
    }

    // 1A. hJobs JobManager: add peekPlayerStats(UUID) and make getPlayerStats(UUID) delegate to ensurePlayerStatsLoaded(UUID)
    private static byte[] patchHJobsJobManager(byte[] in) {
        ClassReader cr = new ClassReader(in);
        ClassWriter cw = new ClassWriter(cr, ClassWriter.COMPUTE_MAXS);
        final boolean[] hasPeek = {false};
        cr.accept(new ClassVisitor(Opcodes.ASM9, cw) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                if ("peekPlayerStats".equals(name) && "(Ljava/util/UUID;)Ljava/util/Map;".equals(desc)) {
                    hasPeek[0] = true;
                }
                if ("getPlayerStats".equals(name) && "(Ljava/util/UUID;)Ljava/util/Map;".equals(desc)) {
                    MethodVisitor mv = super.visitMethod(access, name, desc, sig, ex);
                    mv.visitCode();
                    mv.visitVarInsn(Opcodes.ALOAD, 0);
                    mv.visitFieldInsn(Opcodes.GETFIELD, "com/hokokrtet/hjobs/manager/JobManager",
                            "plugin", "Lcom/hokokrtet/hjobs/HJobs;");
                    mv.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "com/hokokrtet/hjobs/HJobs",
                            "getDatabaseManager", "()Lcom/hokokrtet/hjobs/manager/DatabaseManager;", false);
                    mv.visitVarInsn(Opcodes.ALOAD, 1);
                    mv.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "com/hokokrtet/hjobs/manager/DatabaseManager",
                            "ensurePlayerStatsLoaded", "(Ljava/util/UUID;)Ljava/util/Map;", false);
                    mv.visitInsn(Opcodes.ARETURN);
                    mv.visitMaxs(0, 0);
                    mv.visitEnd();
                    return null;
                }
                return super.visitMethod(access, name, desc, sig, ex);
            }

            @Override
            public void visitEnd() {
                if (!hasPeek[0]) {
                    MethodVisitor mv = super.visitMethod(Opcodes.ACC_PUBLIC, "peekPlayerStats",
                            "(Ljava/util/UUID;)Ljava/util/Map;",
                            "(Ljava/util/UUID;)Ljava/util/Map<Ljava/lang/String;Lcom/hokokrtet/hjobs/data/JobStat;>;",
                            null);
                    mv.visitCode();
                    mv.visitVarInsn(Opcodes.ALOAD, 0);
                    mv.visitFieldInsn(Opcodes.GETFIELD, "com/hokokrtet/hjobs/manager/JobManager",
                            "playerStats", "Ljava/util/Map;");
                    mv.visitVarInsn(Opcodes.ALOAD, 1);
                    mv.visitMethodInsn(Opcodes.INVOKEINTERFACE, "java/util/Map",
                            "get", "(Ljava/lang/Object;)Ljava/lang/Object;", true);
                    mv.visitTypeInsn(Opcodes.CHECKCAST, "java/util/Map");
                    mv.visitInsn(Opcodes.ARETURN);
                    mv.visitMaxs(0, 0);
                    mv.visitEnd();
                }
                super.visitEnd();
            }
        }, 0);
        return cw.toByteArray();
    }

    // 1B. hJobs PlayerListener: add @EventHandler onPlayerJoin(PlayerJoinEvent) and make onPlayerQuit save async
    private static byte[] patchHJobsPlayerListener(byte[] in) {
        ClassReader cr = new ClassReader(in);
        ClassWriter cw = new ClassWriter(cr, ClassWriter.COMPUTE_MAXS);
        final boolean[] hasJoin = {false};
        cr.accept(new ClassVisitor(Opcodes.ASM9, cw) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                if ("onPlayerJoin".equals(name) && "(Lorg/bukkit/event/player/PlayerJoinEvent;)V".equals(desc)) {
                    hasJoin[0] = true;
                }
                MethodVisitor mv = super.visitMethod(access, name, desc, sig, ex);
                if ("onPlayerQuit".equals(name) && "(Lorg/bukkit/event/player/PlayerQuitEvent;)V".equals(desc)) {
                    return new MethodVisitor(Opcodes.ASM9, mv) {
                        @Override
                        public void visitMethodInsn(int op, String owner, String mName, String mDesc, boolean itf) {
                            if ("com/hokokrtet/hjobs/manager/DatabaseManager".equals(owner)
                                    && "savePlayerStats".equals(mName)
                                    && "(Ljava/util/UUID;)V".equals(mDesc)) {
                                super.visitMethodInsn(op, owner, "savePlayerStatsAsync", mDesc, itf);
                            } else {
                                super.visitMethodInsn(op, owner, mName, mDesc, itf);
                            }
                        }
                    };
                }
                return mv;
            }

            @Override
            public void visitEnd() {
                if (!hasJoin[0]) {
                    MethodVisitor mv = super.visitMethod(Opcodes.ACC_PUBLIC, "onPlayerJoin",
                            "(Lorg/bukkit/event/player/PlayerJoinEvent;)V", null, null);
                    AnnotationVisitor av = mv.visitAnnotation("Lorg/bukkit/event/EventHandler;", true);
                    av.visitEnd();
                    mv.visitCode();
                    mv.visitVarInsn(Opcodes.ALOAD, 0);
                    mv.visitFieldInsn(Opcodes.GETFIELD, "com/hokokrtet/hjobs/listener/PlayerListener",
                            "plugin", "Lcom/hokokrtet/hjobs/HJobs;");
                    mv.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "com/hokokrtet/hjobs/HJobs",
                            "getDatabaseManager", "()Lcom/hokokrtet/hjobs/manager/DatabaseManager;", false);
                    mv.visitVarInsn(Opcodes.ALOAD, 1);
                    mv.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "org/bukkit/event/player/PlayerJoinEvent",
                            "getPlayer", "()Lorg/bukkit/entity/Player;", false);
                    mv.visitMethodInsn(Opcodes.INVOKEINTERFACE, "org/bukkit/entity/Player",
                            "getUniqueId", "()Ljava/util/UUID;", true);
                    mv.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "com/hokokrtet/hjobs/manager/DatabaseManager",
                            "loadPlayerStats", "(Ljava/util/UUID;)V", false);
                    mv.visitInsn(Opcodes.RETURN);
                    mv.visitMaxs(0, 0);
                    mv.visitEnd();
                }
                super.visitEnd();
            }
        }, 0);
        return cw.toByteArray();
    }

    // 1C. hJobs GuiListener: immediately trigger savePlayerStatsAsync(player.getUniqueId()) after every GUI item sale
    private static byte[] patchHJobsGuiListener(byte[] in) {
        // Check idempotency
        final boolean[] alreadySaved = {false};
        new ClassReader(in).accept(new ClassVisitor(Opcodes.ASM9) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                return new MethodVisitor(Opcodes.ASM9) {
                    @Override
                    public void visitMethodInsn(int op, String owner, String mName, String mDesc, boolean itf) {
                        if ("savePlayerStatsAsync".equals(mName)) {
                            alreadySaved[0] = true;
                        }
                    }
                };
            }
        }, 0);
        if (alreadySaved[0]) {
            return in;
        }

        ClassReader cr = new ClassReader(in);
        ClassWriter cw = new ClassWriter(cr, ClassWriter.COMPUTE_MAXS);
        cr.accept(new ClassVisitor(Opcodes.ASM9, cw) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                MethodVisitor mv = super.visitMethod(access, name, desc, sig, ex);
                if ("onInventoryClick".equals(name)) {
                    return new MethodVisitor(Opcodes.ASM9, mv) {
                        @Override
                        public void visitMethodInsn(int op, String owner, String mName, String mDesc, boolean itf) {
                            super.visitMethodInsn(op, owner, mName, mDesc, itf);
                            if ("com/hokokrtet/hjobs/manager/GuiManager".equals(owner)
                                    && "openJobMenu".equals(mName)
                                    && "(Lorg/bukkit/entity/Player;Ljava/lang/String;)V".equals(mDesc)) {
                                super.visitVarInsn(Opcodes.ALOAD, 0);
                                super.visitFieldInsn(Opcodes.GETFIELD, "com/hokokrtet/hjobs/listener/GuiListener",
                                        "plugin", "Lcom/hokokrtet/hjobs/HJobs;");
                                super.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "com/hokokrtet/hjobs/HJobs",
                                        "getDatabaseManager", "()Lcom/hokokrtet/hjobs/manager/DatabaseManager;", false);
                                super.visitVarInsn(Opcodes.ALOAD, 3);
                                super.visitMethodInsn(Opcodes.INVOKEINTERFACE, "org/bukkit/entity/Player",
                                        "getUniqueId", "()Ljava/util/UUID;", true);
                                super.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "com/hokokrtet/hjobs/manager/DatabaseManager",
                                        "savePlayerStatsAsync", "(Ljava/util/UUID;)V", false);
                            }
                        }
                    };
                }
                return mv;
            }
        }, 0);
        return cw.toByteArray();
    }

    // 3A. NClans Clan: strip manual color/HEX codes on <init> and setName so legacy clans.yml entries are auto-sanitized
    private static byte[] patchNClansClan(byte[] in) {
        final boolean[] already = {false};
        new ClassReader(in).accept(new ClassVisitor(Opcodes.ASM9) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                if ("<init>".equals(name)) {
                    return new MethodVisitor(Opcodes.ASM9) {
                        @Override
                        public void visitMethodInsn(int op, String owner, String mName, String mDesc, boolean itf) {
                            if ("wtf/n1zamu/utils/ValidatorUtil".equals(owner) && "removeAllColors".equals(mName)) {
                                already[0] = true;
                            }
                        }
                    };
                }
                return null;
            }
        }, 0);
        if (already[0]) {
            return in;
        }

        ClassReader cr = new ClassReader(in);
        ClassWriter cw = new ClassWriter(cr, ClassWriter.COMPUTE_MAXS);
        cr.accept(new ClassVisitor(Opcodes.ASM9, cw) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                MethodVisitor mv = super.visitMethod(access, name, desc, sig, ex);
                if ("<init>".equals(name) || "setName".equals(name)) {
                    return new MethodVisitor(Opcodes.ASM9, mv) {
                        @Override
                        public void visitFieldInsn(int op, String owner, String fName, String fDesc) {
                            if (op == Opcodes.PUTFIELD && "wtf/n1zamu/clans/Clan".equals(owner)
                                    && "name".equals(fName) && "Ljava/lang/String;".equals(fDesc)) {
                                super.visitMethodInsn(Opcodes.INVOKESTATIC, "wtf/n1zamu/utils/ValidatorUtil",
                                        "removeAllColors", "(Ljava/lang/String;)Ljava/lang/String;", false);
                            }
                            super.visitFieldInsn(op, owner, fName, fDesc);
                        }
                    };
                }
                return mv;
            }
        }, 0);
        return cw.toByteArray();
    }

    // 3B. NClans ClanPlaceholder: formatColoredClanName ALWAYS uses level color from LevelUtil.getClanLevel(clan.getExp())
    private static byte[] patchNClansPlaceholder(byte[] in) {
        ClassReader cr = new ClassReader(in);
        ClassWriter cw = new ClassWriter(cr, ClassWriter.COMPUTE_MAXS);
        cr.accept(new ClassVisitor(Opcodes.ASM9, cw) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                if ("formatColoredClanName".equals(name) && "(Lwtf/n1zamu/clans/Clan;)Ljava/lang/String;".equals(desc)) {
                    MethodVisitor mv = super.visitMethod(access, name, desc, sig, ex);
                    mv.visitCode();
                    Label nonNullClan = new Label();
                    Label nonEmptyClean = new Label();
                    Label defaultColor = new Label();
                    Label haveColor = new Label();

                    mv.visitVarInsn(Opcodes.ALOAD, 0);
                    mv.visitJumpInsn(Opcodes.IFNONNULL, nonNullClan);
                    mv.visitLdcInsn("");
                    mv.visitInsn(Opcodes.ARETURN);

                    mv.visitLabel(nonNullClan);
                    mv.visitFrame(Opcodes.F_SAME, 0, null, 0, null);
                    mv.visitVarInsn(Opcodes.ALOAD, 0);
                    mv.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "wtf/n1zamu/clans/Clan",
                            "getName", "()Ljava/lang/String;", false);
                    mv.visitMethodInsn(Opcodes.INVOKESTATIC, "wtf/n1zamu/utils/ValidatorUtil",
                            "removeAllColors", "(Ljava/lang/String;)Ljava/lang/String;", false);
                    mv.visitVarInsn(Opcodes.ASTORE, 1);

                    mv.visitVarInsn(Opcodes.ALOAD, 1);
                    mv.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "java/lang/String",
                            "isEmpty", "()Z", false);
                    mv.visitJumpInsn(Opcodes.IFEQ, nonEmptyClean);
                    mv.visitLdcInsn("");
                    mv.visitInsn(Opcodes.ARETURN);

                    mv.visitLabel(nonEmptyClean);
                    mv.visitFrame(Opcodes.F_APPEND, 1, new Object[]{"java/lang/String"}, 0, null);
                    mv.visitVarInsn(Opcodes.ALOAD, 0);
                    mv.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "wtf/n1zamu/clans/Clan",
                            "getExp", "()I", false);
                    mv.visitMethodInsn(Opcodes.INVOKESTATIC, "wtf/n1zamu/utils/LevelUtil",
                            "getClanLevel", "(I)Lwtf/n1zamu/level/Level;", false);
                    mv.visitVarInsn(Opcodes.ASTORE, 2);

                    mv.visitVarInsn(Opcodes.ALOAD, 2);
                    mv.visitJumpInsn(Opcodes.IFNULL, defaultColor);
                    mv.visitVarInsn(Opcodes.ALOAD, 2);
                    mv.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "wtf/n1zamu/level/Level",
                            "getColor", "()Ljava/lang/String;", false);
                    mv.visitJumpInsn(Opcodes.IFNULL, defaultColor);
                    mv.visitVarInsn(Opcodes.ALOAD, 2);
                    mv.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "wtf/n1zamu/level/Level",
                            "getColor", "()Ljava/lang/String;", false);
                    mv.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "java/lang/String",
                            "isEmpty", "()Z", false);
                    mv.visitJumpInsn(Opcodes.IFNE, defaultColor);
                    mv.visitVarInsn(Opcodes.ALOAD, 2);
                    mv.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "wtf/n1zamu/level/Level",
                            "getColor", "()Ljava/lang/String;", false);
                    mv.visitJumpInsn(Opcodes.GOTO, haveColor);

                    mv.visitLabel(defaultColor);
                    mv.visitFrame(Opcodes.F_APPEND, 1, new Object[]{"wtf/n1zamu/level/Level"}, 0, null);
                    mv.visitLdcInsn("&7");

                    mv.visitLabel(haveColor);
                    mv.visitFrame(Opcodes.F_SAME1, 0, null, 1, new Object[]{"java/lang/String"});
                    mv.visitVarInsn(Opcodes.ALOAD, 1);
                    mv.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "java/lang/String",
                            "concat", "(Ljava/lang/String;)Ljava/lang/String;", false);
                    mv.visitMethodInsn(Opcodes.INVOKESTATIC, "wtf/n1zamu/utils/HexUtil",
                            "translateHexColorCodes", "(Ljava/lang/String;)Ljava/lang/String;", false);
                    mv.visitInsn(Opcodes.ARETURN);
                    mv.visitMaxs(0, 0);
                    mv.visitEnd();
                    return null;
                }
                return super.visitMethod(access, name, desc, sig, ex);
            }
        }, 0);
        return cw.toByteArray();
    }

    // 3C. NClans InfoFunction: replace clan.getName() with ClanPlaceholder.formatColoredClanName(clan) in <init>
    private static byte[] patchNClansInfo(byte[] in) {
        ClassReader cr = new ClassReader(in);
        ClassWriter cw = new ClassWriter(cr, ClassWriter.COMPUTE_MAXS);
        cr.accept(new ClassVisitor(Opcodes.ASM9, cw) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                MethodVisitor mv = super.visitMethod(access, name, desc, sig, ex);
                if ("<init>".equals(name) && "(Lwtf/n1zamu/clans/Clan;)V".equals(desc)) {
                    return new MethodVisitor(Opcodes.ASM9, mv) {
                        @Override
                        public void visitMethodInsn(int op, String owner, String mName, String mDesc, boolean itf) {
                            if (op == Opcodes.INVOKEVIRTUAL && "wtf/n1zamu/clans/Clan".equals(owner)
                                    && "getName".equals(mName) && "()Ljava/lang/String;".equals(mDesc)) {
                                super.visitMethodInsn(Opcodes.INVOKESTATIC, "wtf/n1zamu/placeholder/ClanPlaceholder",
                                        "formatColoredClanName", "(Lwtf/n1zamu/clans/Clan;)Ljava/lang/String;", false);
                            } else {
                                super.visitMethodInsn(op, owner, mName, mDesc, itf);
                            }
                        }
                    };
                }
                return mv;
            }
        }, 0);
        return cw.toByteArray();
    }

    // 3D. NClans LevelConfiguration: cache Map<Integer, Level> in cachedLevels field instead of reparsing 100 YAML sections per call
    private static byte[] patchNClansLevelConfig(byte[] in) {
        final boolean[] already = {false};
        new ClassReader(in).accept(new ClassVisitor(Opcodes.ASM9) {
            @Override
            public FieldVisitor visitField(int access, String name, String desc, String sig, Object value) {
                if ("cachedLevels".equals(name)) {
                    already[0] = true;
                }
                return null;
            }
        }, 0);
        if (already[0]) {
            return in;
        }

        ClassReader cr = new ClassReader(in);
        ClassWriter cw = new ClassWriter(cr, ClassWriter.COMPUTE_MAXS);
        cr.accept(new ClassVisitor(Opcodes.ASM9, cw) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                if ("levels".equals(name) && "()Ljava/util/Map;".equals(desc)) {
                    return super.visitMethod(Opcodes.ACC_PRIVATE, "buildLevelsUncached", desc, sig, ex);
                }
                MethodVisitor mv = super.visitMethod(access, name, desc, sig, ex);
                if (("setupYml".equals(name) || "reloadYml".equals(name)) && "()V".equals(desc)) {
                    return new MethodVisitor(Opcodes.ASM9, mv) {
                        @Override
                        public void visitInsn(int opcode) {
                            if (opcode == Opcodes.RETURN) {
                                super.visitVarInsn(Opcodes.ALOAD, 0);
                                super.visitVarInsn(Opcodes.ALOAD, 0);
                                super.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "wtf/n1zamu/level/config/LevelConfiguration",
                                        "buildLevelsUncached", "()Ljava/util/Map;", false);
                                super.visitMethodInsn(Opcodes.INVOKESTATIC, "java/util/Collections",
                                        "unmodifiableMap", "(Ljava/util/Map;)Ljava/util/Map;", false);
                                super.visitFieldInsn(Opcodes.PUTFIELD, "wtf/n1zamu/level/config/LevelConfiguration",
                                        "cachedLevels", "Ljava/util/Map;");
                            }
                            super.visitInsn(opcode);
                        }
                    };
                }
                return mv;
            }

            @Override
            public void visitEnd() {
                FieldVisitor fv = super.visitField(Opcodes.ACC_PRIVATE | Opcodes.ACC_VOLATILE,
                        "cachedLevels", "Ljava/util/Map;", null, null);
                if (fv != null) {
                    fv.visitEnd();
                }

                MethodVisitor mv = super.visitMethod(Opcodes.ACC_PUBLIC, "levels",
                        "()Ljava/util/Map;",
                        "()Ljava/util/Map<Ljava/lang/Integer;Lwtf/n1zamu/level/Level;>;", null);
                mv.visitCode();
                Label ready = new Label();
                mv.visitVarInsn(Opcodes.ALOAD, 0);
                mv.visitFieldInsn(Opcodes.GETFIELD, "wtf/n1zamu/level/config/LevelConfiguration",
                        "cachedLevels", "Ljava/util/Map;");
                mv.visitVarInsn(Opcodes.ASTORE, 1);
                mv.visitVarInsn(Opcodes.ALOAD, 1);
                mv.visitJumpInsn(Opcodes.IFNONNULL, ready);
                mv.visitVarInsn(Opcodes.ALOAD, 0);
                mv.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "wtf/n1zamu/level/config/LevelConfiguration",
                        "buildLevelsUncached", "()Ljava/util/Map;", false);
                mv.visitMethodInsn(Opcodes.INVOKESTATIC, "java/util/Collections",
                        "unmodifiableMap", "(Ljava/util/Map;)Ljava/util/Map;", false);
                mv.visitVarInsn(Opcodes.ASTORE, 1);
                mv.visitVarInsn(Opcodes.ALOAD, 0);
                mv.visitVarInsn(Opcodes.ALOAD, 1);
                mv.visitFieldInsn(Opcodes.PUTFIELD, "wtf/n1zamu/level/config/LevelConfiguration",
                        "cachedLevels", "Ljava/util/Map;");
                mv.visitLabel(ready);
                mv.visitFrame(Opcodes.F_APPEND, 1, new Object[]{"java/util/Map"}, 0, null);
                mv.visitVarInsn(Opcodes.ALOAD, 1);
                mv.visitInsn(Opcodes.ARETURN);
                mv.visitMaxs(0, 0);
                mv.visitEnd();
                super.visitEnd();
            }
        }, 0);
        return cw.toByteArray();
    }

    // 5A. GreatCombat ItemUtils: never disable plugin on decode error + add decodeWithFallback(base64, materialKey)
    private static byte[] patchGreatCombatItemUtils(byte[] in) {
        final boolean[] hasFallback = {false};
        new ClassReader(in).accept(new ClassVisitor(Opcodes.ASM9) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                if ("decodeWithFallback".equals(name)) {
                    hasFallback[0] = true;
                }
                return null;
            }
        }, 0);
        if (hasFallback[0]) {
            return in;
        }

        ClassReader cr = new ClassReader(in);
        ClassWriter cw = new ClassWriter(cr, ClassWriter.COMPUTE_MAXS);
        cr.accept(new ClassVisitor(Opcodes.ASM9, cw) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                MethodVisitor mv = super.visitMethod(access, name, desc, sig, ex);
                if ("decode".equals(name) && "(Ljava/lang/String;)Lorg/bukkit/inventory/ItemStack;".equals(desc)) {
                    return new MethodVisitor(Opcodes.ASM9, mv) {
                        @Override
                        public void visitMethodInsn(int op, String owner, String mName, String mDesc, boolean itf) {
                            if ("org/bukkit/plugin/PluginManager".equals(owner) && "disablePlugin".equals(mName)) {
                                // Stack top has [PluginManager, Plugin]; pop both instead of disabling GreatCombat!
                                super.visitInsn(Opcodes.POP2);
                            } else {
                                super.visitMethodInsn(op, owner, mName, mDesc, itf);
                            }
                        }
                    };
                }
                return mv;
            }

            @Override
            public void visitEnd() {
                MethodVisitor mv = super.visitMethod(Opcodes.ACC_PUBLIC | Opcodes.ACC_STATIC,
                        "decodeWithFallback",
                        "(Ljava/lang/String;Ljava/lang/String;)Lorg/bukkit/inventory/ItemStack;",
                        null, null);
                mv.visitCode();
                Label popAndTryMaterial = new Label();
                Label tryMaterial = new Label();
                Label popAndReturnNull = new Label();
                Label returnNull = new Label();

                mv.visitVarInsn(Opcodes.ALOAD, 0);
                mv.visitJumpInsn(Opcodes.IFNULL, tryMaterial);
                mv.visitVarInsn(Opcodes.ALOAD, 0);
                mv.visitMethodInsn(Opcodes.INVOKEVIRTUAL, "java/lang/String", "isEmpty", "()Z", false);
                mv.visitJumpInsn(Opcodes.IFNE, tryMaterial);

                mv.visitVarInsn(Opcodes.ALOAD, 0);
                mv.visitMethodInsn(Opcodes.INVOKESTATIC, "dev/enco/greatcombat/utils/ItemUtils",
                        "decode", "(Ljava/lang/String;)Lorg/bukkit/inventory/ItemStack;", false);
                mv.visitInsn(Opcodes.DUP);
                mv.visitJumpInsn(Opcodes.IFNULL, popAndTryMaterial);
                mv.visitInsn(Opcodes.ARETURN);

                mv.visitLabel(popAndTryMaterial);
                mv.visitFrame(Opcodes.F_SAME1, 0, null, 1, new Object[]{"org/bukkit/inventory/ItemStack"});
                mv.visitInsn(Opcodes.POP);

                mv.visitLabel(tryMaterial);
                mv.visitFrame(Opcodes.F_SAME, 0, null, 0, null);
                mv.visitVarInsn(Opcodes.ALOAD, 1);
                mv.visitJumpInsn(Opcodes.IFNULL, returnNull);
                mv.visitVarInsn(Opcodes.ALOAD, 1);
                mv.visitMethodInsn(Opcodes.INVOKESTATIC, "org/bukkit/Material",
                        "matchMaterial", "(Ljava/lang/String;)Lorg/bukkit/Material;", false);
                mv.visitInsn(Opcodes.DUP);
                mv.visitJumpInsn(Opcodes.IFNULL, popAndReturnNull);
                mv.visitVarInsn(Opcodes.ASTORE, 2);
                mv.visitTypeInsn(Opcodes.NEW, "org/bukkit/inventory/ItemStack");
                mv.visitInsn(Opcodes.DUP);
                mv.visitVarInsn(Opcodes.ALOAD, 2);
                mv.visitMethodInsn(Opcodes.INVOKESPECIAL, "org/bukkit/inventory/ItemStack",
                        "<init>", "(Lorg/bukkit/Material;)V", false);
                mv.visitInsn(Opcodes.ARETURN);

                mv.visitLabel(popAndReturnNull);
                mv.visitFrame(Opcodes.F_SAME1, 0, null, 1, new Object[]{"org/bukkit/Material"});
                mv.visitInsn(Opcodes.POP);

                mv.visitLabel(returnNull);
                mv.visitFrame(Opcodes.F_SAME, 0, null, 0, null);
                mv.visitInsn(Opcodes.ACONST_NULL);
                mv.visitInsn(Opcodes.ARETURN);
                mv.visitMaxs(0, 0);
                mv.visitEnd();
                super.visitEnd();
            }
        }, 0);
        return cw.toByteArray();
    }

    // 5B. GreatCombat CooldownManager: pass section key (v5) to ItemUtils.decodeWithFallback(base64, key)
    private static byte[] patchGreatCombatCooldownManager(byte[] in) {
        ClassReader cr = new ClassReader(in);
        ClassWriter cw = new ClassWriter(cr, ClassWriter.COMPUTE_MAXS);
        cr.accept(new ClassVisitor(Opcodes.ASM9, cw) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                MethodVisitor mv = super.visitMethod(access, name, desc, sig, ex);
                if ("setupCooldownItems".equals(name)) {
                    return new MethodVisitor(Opcodes.ASM9, mv) {
                        @Override
                        public void visitMethodInsn(int op, String owner, String mName, String mDesc, boolean itf) {
                            if (op == Opcodes.INVOKESTATIC && "dev/enco/greatcombat/utils/ItemUtils".equals(owner)
                                    && "decode".equals(mName)
                                    && "(Ljava/lang/String;)Lorg/bukkit/inventory/ItemStack;".equals(mDesc)) {
                                super.visitVarInsn(Opcodes.ALOAD, 5);
                                super.visitMethodInsn(Opcodes.INVOKESTATIC, owner, "decodeWithFallback",
                                        "(Ljava/lang/String;Ljava/lang/String;)Lorg/bukkit/inventory/ItemStack;", false);
                            } else {
                                super.visitMethodInsn(op, owner, mName, mDesc, itf);
                            }
                        }
                    };
                }
                return mv;
            }
        }, 0);
        return cw.toByteArray();
    }

    // 5C. GreatCombat PlayerListener: make hasPermission("greatcombat.cooldowns.bypass") always false in handleCooldown
    private static byte[] patchGreatCombatPlayerListener(byte[] in) {
        ClassReader cr = new ClassReader(in);
        ClassWriter cw = new ClassWriter(cr, ClassWriter.COMPUTE_MAXS);
        cr.accept(new ClassVisitor(Opcodes.ASM9, cw) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                MethodVisitor mv = super.visitMethod(access, name, desc, sig, ex);
                if ("handleCooldown".equals(name)) {
                    return new MethodVisitor(Opcodes.ASM9, mv) {
                        @Override
                        public void visitMethodInsn(int op, String owner, String mName, String mDesc, boolean itf) {
                            if (op == Opcodes.INVOKEINTERFACE && "org/bukkit/entity/Player".equals(owner)
                                    && "hasPermission".equals(mName)
                                    && "(Ljava/lang/String;)Z".equals(mDesc)) {
                                // Stack has [Player, String("greatcombat.cooldowns.bypass")]; pop both and push false (0)
                                super.visitInsn(Opcodes.POP2);
                                super.visitInsn(Opcodes.ICONST_0);
                            } else {
                                super.visitMethodInsn(op, owner, mName, mDesc, itf);
                            }
                        }
                    };
                }
                return mv;
            }
        }, 0);
        return cw.toByteArray();
    }

    // 6A. Duels ElytrixDuelPerf: delegate tryTeleport(...) to ElytrixDuelTeleportFix.tryTeleport(...)
    private static byte[] patchDuelsPerf(byte[] in) {
        ClassReader cr = new ClassReader(in);
        ClassWriter cw = new ClassWriter(cr, ClassWriter.COMPUTE_MAXS);
        final String targetDesc =
                "(Lme/realized/duels/DuelsPlugin;Lme/realized/duels/util/Loadable;Lorg/bukkit/entity/Player;Lorg/bukkit/Location;)V";
        cr.accept(new ClassVisitor(Opcodes.ASM9, cw) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                if ("tryTeleport".equals(name) && targetDesc.equals(desc)) {
                    MethodVisitor mv = super.visitMethod(access, name, desc, sig, ex);
                    mv.visitCode();
                    mv.visitVarInsn(Opcodes.ALOAD, 0);
                    mv.visitVarInsn(Opcodes.ALOAD, 1);
                    mv.visitVarInsn(Opcodes.ALOAD, 2);
                    mv.visitVarInsn(Opcodes.ALOAD, 3);
                    mv.visitMethodInsn(Opcodes.INVOKESTATIC,
                            "me/realized/duels/util/ElytrixDuelTeleportFix",
                            "tryTeleport",
                            targetDesc,
                            false);
                    mv.visitInsn(Opcodes.RETURN);
                    mv.visitMaxs(0, 0);
                    mv.visitEnd();
                    return null;
                }
                return super.visitMethod(access, name, desc, sig, ex);
            }
        }, 0);
        return cw.toByteArray();
    }

    // 6B. Duels DuelManager$DuelListener: honor "Duels-Teleport" metadata inside on(PlayerTeleportEvent)
    private static byte[] patchDuelsListener(byte[] in) {
        ClassReader cr = new ClassReader(in);
        ClassWriter cw = new ClassWriter(cr, ClassWriter.COMPUTE_MAXS);
        cr.accept(new ClassVisitor(Opcodes.ASM9, cw) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                MethodVisitor mv = super.visitMethod(access, name, desc, sig, ex);
                if ("on".equals(name) && "(Lorg/bukkit/event/player/PlayerTeleportEvent;)V".equals(desc)) {
                    return new MethodVisitor(Opcodes.ASM9, mv) {
                        @Override
                        public void visitMethodInsn(int op, String owner, String mName, String mDesc, boolean itf) {
                            if (op == Opcodes.INVOKEVIRTUAL
                                    && "me/realized/duels/arena/ArenaManagerImpl".equals(owner)
                                    && "isInMatch".equals(mName)
                                    && "(Lorg/bukkit/entity/Player;)Z".equals(mDesc)) {
                                super.visitMethodInsn(Opcodes.INVOKESTATIC,
                                        "me/realized/duels/util/ElytrixDuelTeleportFix",
                                        "shouldBlockTeleportInMatch",
                                        "(Lme/realized/duels/arena/ArenaManagerImpl;Lorg/bukkit/entity/Player;)Z",
                                        false);
                            } else {
                                super.visitMethodInsn(op, owner, mName, mDesc, itf);
                            }
                        }
                    };
                }
                return mv;
            }
        }, 0);
        return cw.toByteArray();
    }

    // 7. ElytrixItems ItemEffects$TrapItem: block trap activation near active AirDrop before cooldown/item consumption
    private static byte[] patchElytrixItemsTrap(byte[] in) {
        ClassReader cr = new ClassReader(in);
        ClassWriter cw = new ClassWriter(cr, ClassWriter.COMPUTE_MAXS);
        cr.accept(new ClassVisitor(Opcodes.ASM9, cw) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                MethodVisitor mv = super.visitMethod(access, name, desc, sig, ex);
                if ("execute".equals(name) && "(Lorg/bukkit/event/player/PlayerInteractEvent;)V".equals(desc)) {
                    return new MethodVisitor(Opcodes.ASM9, mv) {
                        @Override
                        public void visitMethodInsn(int op, String owner, String mName, String mDesc, boolean itf) {
                            if (op == Opcodes.INVOKESTATIC
                                    && "topka/simbay/rwitems/items/ItemRegistry$Items".equals(owner)
                                    && "getItem".equals(mName)
                                    && "(Lorg/bukkit/inventory/ItemStack;Ltopka/simbay/rwitems/items/ItemRegistry$Items;)Ltopka/simbay/rwitems/items/ItemRegistry$Items;".equals(mDesc)) {
                                super.visitVarInsn(Opcodes.ALOAD, 1);
                                super.visitMethodInsn(Opcodes.INVOKESTATIC,
                                        "topka/simbay/rwitems/utils/ElytrixAirTrapGuard",
                                        "validateTrapUse",
                                        "(Lorg/bukkit/inventory/ItemStack;Ltopka/simbay/rwitems/items/ItemRegistry$Items;Lorg/bukkit/event/player/PlayerInteractEvent;)Ltopka/simbay/rwitems/items/ItemRegistry$Items;",
                                        false);
                            } else {
                                super.visitMethodInsn(op, owner, mName, mDesc, itf);
                            }
                        }
                    };
                }
                return mv;
            }
        }, 0);
        return cw.toByteArray();
    }

    // 8. NMascot PlayerMoveListener: disable both /fly and /god in active Talisman region without dead CMI call
    private static byte[] patchNMascotMove(byte[] in) {
        ClassReader cr = new ClassReader(in);
        ClassWriter cw = new ClassWriter(cr, ClassWriter.COMPUTE_MAXS);
        cr.accept(new ClassVisitor(Opcodes.ASM9, cw) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                if ("onMove".equals(name) && "(Lorg/bukkit/event/player/PlayerMoveEvent;)V".equals(desc)) {
                    MethodVisitor mv = super.visitMethod(access, name, desc, sig, ex);
                    mv.visitCode();
                    mv.visitVarInsn(Opcodes.ALOAD, 1);
                    mv.visitMethodInsn(Opcodes.INVOKESTATIC,
                            "ru/Travka/util/ElytrixMascotGuard",
                            "onPlayerMove",
                            "(Lorg/bukkit/event/player/PlayerMoveEvent;)V",
                            false);
                    mv.visitInsn(Opcodes.RETURN);
                    mv.visitMaxs(0, 0);
                    mv.visitEnd();
                    return null;
                }
                return super.visitMethod(access, name, desc, sig, ex);
            }
        }, 0);
        return cw.toByteArray();
    }

    // 9. ItemKeep DataManager: clone items, guarantee shield/quest shulker enchants, and drop overflow items
    private static byte[] patchItemKeepDataManager(byte[] in) {
        ClassReader cr = new ClassReader(in);
        ClassWriter cw = new ClassWriter(cr, ClassWriter.COMPUTE_MAXS);
        cr.accept(new ClassVisitor(Opcodes.ASM9, cw) {
            @Override
            public MethodVisitor visitMethod(int access, String name, String desc, String sig, String[] ex) {
                if ("giveItem".equals(name) && "(Lorg/bukkit/entity/Player;Ljava/lang/String;)V".equals(desc)) {
                    MethodVisitor mv = super.visitMethod(access, name, desc, sig, ex);
                    mv.visitCode();
                    mv.visitVarInsn(Opcodes.ALOAD, 0);
                    mv.visitFieldInsn(Opcodes.GETFIELD,
                            "ru/penatov/itemkeep/data/DataManager",
                            "dataConfig",
                            "Lorg/bukkit/configuration/file/FileConfiguration;");
                    mv.visitVarInsn(Opcodes.ALOAD, 1);
                    mv.visitVarInsn(Opcodes.ALOAD, 2);
                    mv.visitMethodInsn(Opcodes.INVOKESTATIC,
                            "ru/penatov/itemkeep/data/ElytrixItemKeepFix",
                            "giveItem",
                            "(Lorg/bukkit/configuration/file/FileConfiguration;Lorg/bukkit/entity/Player;Ljava/lang/String;)V",
                            false);
                    mv.visitInsn(Opcodes.RETURN);
                    mv.visitMaxs(0, 0);
                    mv.visitEnd();
                    return null;
                }
                return super.visitMethod(access, name, desc, sig, ex);
            }
        }, 0);
        return cw.toByteArray();
    }
}
