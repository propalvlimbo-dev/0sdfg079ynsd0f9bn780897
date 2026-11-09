package com.ticxo.modelengine.api.model.render;
import com.ticxo.modelengine.api.utils.data.tracker.DataTracker;
/** Compile-time stand-in: the renderer that owns the pivot entity. */
public interface DisplayRenderer extends ModelRenderer {
    Pivot getPivot();
    interface Pivot {
        int getId();
        boolean isOverridden();
        DataTracker getPosition();
    }
}
