package com.ticxo.modelengine.api;
import com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint;
import org.bukkit.entity.Entity;
import com.ticxo.modelengine.api.model.ModeledEntity;
import com.ticxo.modelengine.api.model.ActiveModel;
import com.ticxo.modelengine.api.model.PivotOverrideRegistry;
/** Compile-time stand-in for ModelEngineAPI: the mock tests never touch a live engine. */
public class ModelEngineAPI {
    /** Swapped by the mock tests; null keeps every call inert, like an unloaded engine. */
    public interface Backend {
        ModelBlueprint blueprint(String id);
        ModeledEntity modeledEntity(Entity entity);
        ActiveModel createActiveModel(ModelBlueprint blueprint);
        PivotOverrideRegistry pivots();
    }
    public static Backend backend;
    public static ModelBlueprint getBlueprint(String id) { return backend == null ? null : backend.blueprint(id); }
    public static ModeledEntity getOrCreateModeledEntity(Entity entity) { return backend == null ? null : backend.modeledEntity(entity); }
    public static ModeledEntity getModeledEntity(Entity entity) { return backend == null ? null : backend.modeledEntity(entity); }
    public static ActiveModel createActiveModel(ModelBlueprint blueprint) { return backend == null ? null : backend.createActiveModel(blueprint); }
    public static PivotOverrideRegistry getPivotOverrideRegistry() { return backend == null ? null : backend.pivots(); }
}
