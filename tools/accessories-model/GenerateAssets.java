import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/**
 * Generates the resource-pack item/model JSON files for one Blockbench blueprint with the real
 * ModelEngine 4.1.0 generator (BlockbenchDeserializer + BlockbenchParser.populateBlueprint /
 * populateAssets) at Use-New-Rotation=false, exactly like the live server does.
 *
 * Only platform/fastutil/slf4j stand-ins from ./stubs are used; plugins/ is never modified.
 * Output layout matches what ModelEngine writes into its own "resource pack" folder, so the
 * files can be merged into Elytrix-RP-1.21.zip unchanged.
 */
public final class GenerateAssets {
    public static void main(String[] args) throws Exception {
        if (args.length < 2 || args.length > 3) {
            throw new IllegalArgumentException("Usage: GenerateAssets <blueprint.bbmodel> <output-dir> [model-name]");
        }
        Path blueprintFile = Path.of(args[0]).toAbsolutePath();
        Path output = Path.of(args[1]).toAbsolutePath();
        if (!Files.isRegularFile(blueprintFile)) throw new IllegalArgumentException("missing blueprint: " + blueprintFile);

        Class<?> blockbenchModel = Class.forName("com.ticxo.modelengine.api.generator.parser.blockbench.BlockbenchModel");
        Object adapter = Class.forName("com.ticxo.modelengine.api.generator.parser.blockbench.BlockbenchDeserializer")
                .getConstructor().newInstance();
        Object builder = Class.forName("com.google.gson.GsonBuilder").getConstructor().newInstance();
        builder.getClass().getMethod("registerTypeAdapter", java.lang.reflect.Type.class, Object.class)
                .invoke(builder, blockbenchModel, adapter);
        Object gson = builder.getClass().getMethod("create").invoke(builder);
        Object model = gson.getClass().getMethod("fromJson", String.class, Class.class)
                .invoke(gson, Files.readString(blueprintFile), blockbenchModel);

        Class<?> parserClass = Class.forName("com.ticxo.modelengine.core.generator.parser.blockbench.BlockbenchParser");
        Class<?> unsafeClass = Class.forName("sun.misc.Unsafe");
        java.lang.reflect.Field unsafeField = unsafeClass.getDeclaredField("theUnsafe");
        unsafeField.setAccessible(true);
        Object unsafe = unsafeField.get(null);
        Object parser = unsafeClass.getMethod("allocateInstance", Class.class).invoke(unsafe, parserClass);
        java.lang.reflect.Field generatorField = parserClass.getDeclaredField("generator");
        generatorField.setAccessible(true);
        generatorField.set(parser, Class.forName("com.ticxo.modelengine.core.generator.ModelGeneratorImpl")
                .getConstructor().newInstance());
        java.lang.reflect.Field behaviors = parserClass.getDeclaredField("behaviorParsers");
        behaviors.setAccessible(true);
        behaviors.set(parser, new LinkedHashSet<>());

        Class<?> blueprintClass = Class.forName("com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint");
        Object blueprint = blueprintClass.getConstructor().newInstance();
        Class<?> collectorClass = Class.forName("com.ticxo.modelengine.api.error.ErrorCollector");
        Object collector = collectorClass.getConstructor(String.class).newInstance("elytrix-assets");

        String name = args.length > 2 ? args[2] : rootName(Files.readString(blueprintFile));
        if (name == null || !name.matches("[a-z0-9_]+")) throw new IllegalStateException("unsafe blueprint name: " + name);

        java.lang.reflect.Method populateBlueprint = parserClass.getDeclaredMethod(
                "populateBlueprint", blockbenchModel, blueprintClass, collectorClass);
        populateBlueprint.setAccessible(true);
        populateBlueprint.invoke(parser, model, blueprint, collector);

        blueprintClass.getMethod("setName", String.class).invoke(blueprint, name);
        blueprintClass.getMethod("constructFlatBoneMap", collectorClass).invoke(blueprint, collector);

        Class<?> assetsClass = Class.forName("com.ticxo.modelengine.api.generator.assets.ModelAssets");
        Object assets = assetsClass.getConstructor().newInstance();
        assetsClass.getMethod("setName", String.class).invoke(assets, name);
        java.lang.reflect.Method populateAssets = parserClass.getDeclaredMethod(
                "populateAssets", blockbenchModel, blueprintClass, assetsClass, collectorClass);
        populateAssets.setAccessible(true);
        populateAssets.invoke(parser, model, blueprint, assets, collector);

        List<?> errors = (List<?>) collectorClass.getMethod("getErrorList").invoke(collector);
        if (!errors.isEmpty()) throw new IllegalStateException("parser reported errors: " + errors);

        @SuppressWarnings("unchecked")
        Map<String, Collection<Object>> models = (Map<String, Collection<Object>>) assetsClass.getMethod("getModels").invoke(assets);
        Class<?> itemModelClass = Class.forName("com.ticxo.modelengine.api.generator.assets.JavaItemModel");
        int elements = 0;
        for (Collection<Object> group : models.values()) {
            if (group.size() != 1) {
                throw new IllegalStateException("expected exactly one item model per bone, got " + group.size());
            }
            Object itemModel = group.iterator().next();
            elements += ((List<?>) itemModelClass.getMethod("getElements").invoke(itemModel)).size();
            String boneName = (String) itemModelClass.getMethod("getName").invoke(itemModel);
            if (boneName == null || !boneName.matches("[a-z0-9_]+")) throw new IllegalStateException("unsafe model name: " + boneName);

            Path modelFile = output.resolve("assets/modelengine/models/" + name + "/" + boneName + ".json");
            Files.createDirectories(modelFile.getParent());
            Files.writeString(modelFile, (String) gson.getClass().getMethod("toJson", Object.class).invoke(gson, itemModel),
                    StandardCharsets.UTF_8);

            Path itemFile = output.resolve("assets/modelengine/items/" + name + "/" + boneName + ".json");
            Files.createDirectories(itemFile.getParent());
            Files.writeString(itemFile, "{\"model\":{\"model\":\"modelengine:" + name + "/" + boneName
                    + "\",\"tints\":[{\"index\":0,\"default\":16777215,\"type\":\"minecraft:custom_model_data\"}],"
                    + "\"type\":\"minecraft:model\"}}", StandardCharsets.UTF_8);
        }
        List<?> textures = (List<?>) assetsClass.getMethod("getTextures").invoke(assets);
        System.out.println("Generated " + models.size() + " bone models, " + elements + " cubes, "
                + textures.size() + " texture(s) for " + name + " -> " + output);
    }

    /** Reads the root "name" of a .bbmodel (the identifier ModelEngine registers by default). */
    static String rootName(String json) {
        java.util.regex.Matcher matcher = java.util.regex.Pattern
                .compile("\"name\"\\s*:\\s*\"([A-Za-z0-9_]+)\"").matcher(json);
        return matcher.find() ? matcher.group(1) : null;
    }

    private GenerateAssets() {
    }
}
