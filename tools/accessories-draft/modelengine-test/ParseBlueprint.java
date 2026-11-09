import java.nio.file.*; import java.nio.charset.StandardCharsets; import java.lang.reflect.*; import java.util.*;
public class ParseBlueprint {
 public static void main(String[] a)throws Exception {
  Class<?> bb=Class.forName("com.ticxo.modelengine.api.generator.parser.blockbench.BlockbenchModel");
  Object adapter=Class.forName("com.ticxo.modelengine.api.generator.parser.blockbench.BlockbenchDeserializer").getConstructor().newInstance();
  Object builder=Class.forName("com.google.gson.GsonBuilder").getConstructor().newInstance(); builder.getClass().getMethod("registerTypeAdapter",Type.class,Object.class).invoke(builder,bb,adapter);
  Object g=builder.getClass().getMethod("create").invoke(builder); Object model=g.getClass().getMethod("fromJson",String.class,Class.class).invoke(g,Files.readString(Path.of(a[0])),bb);
  Class<?> parser=Class.forName("com.ticxo.modelengine.core.generator.parser.blockbench.BlockbenchParser");
  Class<?> u=Class.forName("sun.misc.Unsafe");Field uf=u.getDeclaredField("theUnsafe");uf.setAccessible(true); Object unsafe=uf.get(null); Object obj=u.getMethod("allocateInstance",Class.class).invoke(unsafe,parser);
  Field generator=parser.getDeclaredField("generator");generator.setAccessible(true);generator.set(obj,Class.forName("com.ticxo.modelengine.core.generator.ModelGeneratorImpl").getConstructor().newInstance());
  Field f=parser.getDeclaredField("behaviorParsers");f.setAccessible(true);f.set(obj,new LinkedHashSet<>());
  Class<?> bp=Class.forName("com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint");Object blueprint=bp.getConstructor().newInstance();
  Class<?> ec=Class.forName("com.ticxo.modelengine.api.error.ErrorCollector");Object collector=ec.getConstructor(String.class).newInstance("test");
  Method p=parser.getDeclaredMethod("populateBlueprint",bb,bp,ec);p.setAccessible(true);p.invoke(obj,model,blueprint,collector);
  bp.getMethod("setName",String.class).invoke(blueprint,"elytrix_kaneki_tentacles");
  bp.getMethod("constructFlatBoneMap",ec).invoke(blueprint,collector);
  Class<?> ac=Class.forName("com.ticxo.modelengine.api.generator.assets.ModelAssets");Object assets=ac.getConstructor().newInstance();ac.getMethod("setName",String.class).invoke(assets,"elytrix_kaneki_tentacles");
  Method populate=parser.getDeclaredMethod("populateAssets",bb,bp,ac,ec);populate.setAccessible(true);populate.invoke(obj,model,blueprint,assets,collector);
  Map<?,?> models=(Map<?,?>)ac.getMethod("getModels").invoke(assets);
  if (!models.keySet().equals(Set.of("left_upper","left_lower","right_upper","right_lower"))) throw new AssertionError("wrong generated bones: "+models.keySet());
  int elements=0; Class<?> item=Class.forName("com.ticxo.modelengine.api.generator.assets.JavaItemModel");
  for (Object collection:models.values()) for (Object itemModel:(Collection<?>)collection) elements+=((List<?>)item.getMethod("getElements").invoke(itemModel)).size();
  if(elements!=20 || ((List<?>)ac.getMethod("getTextures").invoke(assets)).size()!=1 || !((Map<?,?>)bp.getMethod("getAnimations").invoke(blueprint)).containsKey("idle") || !((List<?>)ec.getMethod("getErrorList").invoke(collector)).isEmpty()) throw new AssertionError("unexpected assets or parser errors; elements="+elements);
  Object idle=((Map<?,?>)bp.getMethod("getAnimations").invoke(blueprint)).get("idle");
  Map<?,?> timelines=(Map<?,?>)idle.getClass().getMethod("getTimelines").invoke(idle);
  if(timelines.size()!=4)throw new AssertionError("expected four animated bones, got "+timelines.size());
  Field flatField=bp.getDeclaredField("flatMap");flatField.setAccessible(true); Map<?,?> flat=(Map<?,?>)flatField.get(blueprint);Set<Object> boneIds=new HashSet<>();
  for(Object bone:flat.values())boneIds.add(bone.getClass().getMethod("getUuid").invoke(bone));
  if(!boneIds.containsAll(timelines.keySet()))throw new AssertionError("animation timelines must target blueprint bones");
  Class<?> kt=Class.forName("com.ticxo.modelengine.api.animation.keyframe.KeyframeType");
  Object rotation=Class.forName("com.ticxo.modelengine.api.animation.keyframe.KeyframeTypes").getField("ROTATION").get(null);
  for(Object timeline:timelines.values()){
   Map<?,?> frames=(Map<?,?>)timeline.getClass().getMethod("getInterpolator",kt).invoke(timeline,rotation);
   if(frames==null || frames.size()!=25)throw new AssertionError("expected 25 rotation keyframes per animated bone: "+frames);
  }
  String output=System.getProperty("modelengine.test.output");
  if(output!=null){
   Path root=Path.of(output);
   for(Object group:models.values()){
    Collection<?> collection=(Collection<?>)group;
    if(collection.size()!=1)throw new AssertionError("export expects one model per bone");
    Object m=collection.iterator().next();String name=(String)item.getMethod("getName").invoke(m);
    if(!name.matches("[a-z0-9_]+"))throw new AssertionError("unsafe model name");
    Path file=root.resolve("assets/modelengine/models/elytrix_kaneki_tentacles/"+name+".json");Files.createDirectories(file.getParent());Files.writeString(file,(String)g.getClass().getMethod("toJson",Object.class).invoke(g,m),StandardCharsets.UTF_8);
    Path itemFile=root.resolve("assets/modelengine/items/elytrix_kaneki_tentacles/"+name+".json");Files.createDirectories(itemFile.getParent());Files.writeString(itemFile,"{\"model\":{\"model\":\"modelengine:elytrix_kaneki_tentacles/"+name+"\",\"tints\":[{\"index\":0,\"default\":16777215,\"type\":\"minecraft:custom_model_data\"}],\"type\":\"minecraft:model\"}}",StandardCharsets.UTF_8);
   }
  }
  System.out.println("ModelEngine populateBlueprint/assets with mocked API and Use-New-Rotation="+System.getProperty("modelengine.test.rotation", "true")+": 4 item models, 20 elements, 1 texture, 4 animated bones with 25 keyframes, no collected warnings");
 }
}
