package com.ticxo.modelengine.api.animation;
import com.ticxo.modelengine.api.generator.blueprint.ModelBlueprint;

public class BlueprintAnimation {
    public BlueprintAnimation(ModelBlueprint blueprint, String name) {}
    public enum LoopMode {
        ONCE, HOLD, LOOP
    }
    public enum OverrideMode {
        FALSE, TRUE, LERP
    }
}
