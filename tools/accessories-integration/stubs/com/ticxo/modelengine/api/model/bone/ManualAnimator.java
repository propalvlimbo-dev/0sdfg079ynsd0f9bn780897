package com.ticxo.modelengine.api.model.bone;
/** Compile-time stand-in: ModelEngine calls animate() for every bone tick. */
public interface ManualAnimator {
    boolean applyBoneDefaultLocal();
    void animate(ModelBone bone);
}
