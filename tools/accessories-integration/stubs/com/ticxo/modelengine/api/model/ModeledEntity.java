package com.ticxo.modelengine.api.model;
import java.util.Optional;
/** Compile-time stand-in. */
public interface ModeledEntity {
    com.ticxo.modelengine.api.entity.BaseEntity getBase();
    boolean isDestroyed();
    void setBaseEntityVisible(boolean visible);
    Optional<ActiveModel> addModel(ActiveModel model, boolean passenger);
    Optional<ActiveModel> removeModel(String modelId);
    Optional<ActiveModel> getModel(String modelId);
    void setYBodyRotImmediately(float yaw);
    void setYHeadRotImmediately(float yaw);
    void setXHeadRotImmediately(float pitch);
    void setRotationTick(int tick);
}
