package com.ticxo.modelengine.api.model.render;
/** Compile-time stand-in: the renderer that owns the pivot entity. */
public interface DisplayRenderer extends ModelRenderer {
    Pivot getPivot();
    interface Pivot {
        int getId();
    }
}
