package com.ticxo.modelengine.api.animation.property;
import com.ticxo.modelengine.api.animation.BlueprintAnimation;
public interface IAnimationProperty {
    double getSpeed();
    void setSpeed(double speed);
    void setForceLoopMode(BlueprintAnimation.LoopMode mode);
}
