package com.ticxo.modelengine.api.animation;
public enum ModelState {
    IDLE(null, null),
    WALK(null, null),
    STRAFE(null, null),
    JUMP_START(null, null),
    JUMP(null, null),
    JUMP_END(null, null),
    HOVER(null, null),
    FLY(null, null),
    SPAWN(null, null),
    DEATH(null, null);

    ModelState(BlueprintAnimation.LoopMode loop, BlueprintAnimation.OverrideMode override) {}
}
