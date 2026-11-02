package com.ticxo.modelengine.api.model.bone;
import com.ticxo.modelengine.api.utils.math.SafeTransform;
/** Compile-time stand-in: only what the accessory code drives. */
public interface ModelBone {
    String getBoneId();
    SafeTransform getLocalTransform();
    void setManualAnimator(ManualAnimator animator);
    ManualAnimator getManualAnimator();
}
