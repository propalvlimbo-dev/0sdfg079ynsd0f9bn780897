package com.ticxo.modelengine.api.model.render;
/** Compile-time stand-in: ModelEngine returns a live DisplayRenderer here. */
public interface ModelRenderer {
    boolean isInitialized();
    void initialize();
}
