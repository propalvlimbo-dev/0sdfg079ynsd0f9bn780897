package com.ticxo.modelengine.api.model;
import com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint;
import com.ticxo.modelengine.api.model.bone.ModelBone;
import com.ticxo.modelengine.api.model.render.ModelRenderer;
/** Compile-time stand-in: only the calls the accessory code makes. */
public interface ActiveModel {
    boolean isDestroyed();
    void destroy();
    ModelBlueprint getBlueprint();
    java.util.Optional<ModelBone> getBone(String id);
    ModelRenderer getModelRenderer();
    ModeledEntity getModeledEntity();
    void setBlockLight(int light);
    void setSkyLight(int light);
    void setCanHurt(boolean value);
    void setShadowVisible(boolean value);
    void setHitboxVisible(boolean value);
    void setLockPitch(boolean value);
    void setLockYaw(boolean value);
    void setViewRange(float range);
    void setScale(double scale);
    void setPivotOverride(PivotOverride pivot);
    void setModelRotationLocked(Boolean locked);
    void setLockedXHeadRot(float value);
    void setLockedYHeadRot(float value);
    void setLockedYBodyRot(float value);
}
