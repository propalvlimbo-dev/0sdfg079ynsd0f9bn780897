package com.ticxo.modelengine.api;
import com.ticxo.modelengine.api.animation.keyframe.data.KeyframeReaderRegistry;
public class ModelEngineAPI {
 public static com.ticxo.modelengine.api.utils.config.ConfigCache getConfigCache(){return new com.ticxo.modelengine.api.utils.config.ConfigCache();}
 private static final ModelEngineAPI API=new ModelEngineAPI();
 private final KeyframeReaderRegistry reader=new KeyframeReaderRegistry();
 public static ModelEngineAPI getAPI(){return API;}
 public KeyframeReaderRegistry getKeyframeReaderRegistry(){return reader;}
}
