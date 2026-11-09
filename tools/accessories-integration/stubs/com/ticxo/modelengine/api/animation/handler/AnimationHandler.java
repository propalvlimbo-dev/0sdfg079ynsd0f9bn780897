package com.ticxo.modelengine.api.animation.handler;
import com.ticxo.modelengine.api.animation.ModelState;
import com.ticxo.modelengine.api.animation.property.IAnimationProperty;
public interface AnimationHandler {
    class DefaultProperty {
        private final ModelState state;
        private final String animation;
        public DefaultProperty(ModelState state, String animation, double lerpIn, double lerpOut, double speed) {
            this.state = state;
            this.animation = animation;
        }
        public ModelState getState() { return state; }
        public String getAnimation() { return animation; }
    }
    void setDefaultProperty(DefaultProperty defaultProperty);
    IAnimationProperty playAnimation(String animation, double lerpIn, double lerpOut, double speed, boolean force);
    boolean isPlayingAnimation(String animation);
    void forceStopAnimation(String animation);
    IAnimationProperty getAnimation(String animation);
}
