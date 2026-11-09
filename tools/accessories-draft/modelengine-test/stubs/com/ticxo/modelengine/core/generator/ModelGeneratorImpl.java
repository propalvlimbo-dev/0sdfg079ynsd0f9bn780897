package com.ticxo.modelengine.core.generator;
import java.util.*;
public class ModelGeneratorImpl {
 private final Map<String,String> names=new HashMap<>();
 public String getNamespace(){return "modelengine";}
 public String getTexturePath(){return "entity/models";}
 public Map<String,String> getTextureNameCache(){return names;}
}
