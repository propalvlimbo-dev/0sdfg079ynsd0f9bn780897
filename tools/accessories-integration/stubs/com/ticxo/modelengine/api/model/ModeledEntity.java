package com.ticxo.modelengine.api.model;
import com.ticxo.modelengine.api.lod.AnimationLODHandler;
import java.util.Optional;
/** Compile-time stand-in. */
public interface ModeledEntity {
    com.ticxo.modelengine.api.entity.BaseEntity getBase();
    AnimationLODHandler getAnimationLodHandler();
    boolean isDestroyed();
    void destroy();
    void setBaseEntityVisible(boolean visible);
    void setModelRotationLocked(boolean locked);
    Optional<ActiveModel> addModel(ActiveModel model, boolean passenger);
    Optional<ActiveModel> removeModel(String modelId);
    Optional<ActiveModel> getModel(String modelId);
    void setYBodyRotImmediately(float yaw);
    void setYHeadRotImmediately(float yaw);
    void setXHeadRotImmediately(float pitch);
    void setRotationTick(int tick);
}
