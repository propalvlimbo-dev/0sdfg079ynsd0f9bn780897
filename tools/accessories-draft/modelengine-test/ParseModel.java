import java.nio.file.*;
import java.util.*;
/** Tests actual ModelEngine BlockbenchDeserializer, not its full model generator. */
public class ParseModel {
 public static void main(String[] args) throws Exception {
  Class<?> model=Class.forName("com.ticxo.modelengine.api.generator.parser.blockbench.BlockbenchModel");
  Object adapter=Class.forName("com.ticxo.modelengine.api.generator.parser.blockbench.BlockbenchDeserializer").getConstructor().newInstance();
  Object builder=Class.forName("com.google.gson.GsonBuilder").getConstructor().newInstance();
  builder.getClass().getMethod("registerTypeAdapter",java.lang.reflect.Type.class,Object.class).invoke(builder,model,adapter);
  Object gson=builder.getClass().getMethod("create").invoke(builder);
  Object parsed=gson.getClass().getMethod("fromJson",String.class,Class.class).invoke(gson,Files.readString(Path.of(args[0])),model);
  Map<?,?> elements=(Map<?,?>)model.getMethod("getElements").invoke(parsed);
  Map<?,?> roots=(Map<?,?>)model.getMethod("getOutliner").invoke(parsed);
  Map<?,?> textures=(Map<?,?>)model.getMethod("getTextures").invoke(parsed);
  Map<?,?> animations=(Map<?,?>)model.getMethod("getAnimations").invoke(parsed);
  if(elements.size()!=14 || roots.size()!=1 || textures.size()!=1 || animations.size()!=1 || !animations.containsKey("idle")) throw new AssertionError("unexpected parsed content");
  System.out.println("ModelEngine 4.1.0 deserializer: 14 cubes, 1 root, 1 texture, idle animation");
 }
}
