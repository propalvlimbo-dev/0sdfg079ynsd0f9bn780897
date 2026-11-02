package com.ticxo.modelengine.api.nms.impl;
import com.ticxo.modelengine.api.entity.BaseEntity;
import com.ticxo.modelengine.api.nms.entity.wrapper.BodyRotationController;

public class DefaultBodyRotationController implements BodyRotationController {
    private float yHeadRot, xHeadRot, yBodyRot;
    public DefaultBodyRotationController(BaseEntity entity) {}
    @Override public float getYHeadRot() { return yHeadRot; }
    @Override public void setYHeadRot(float v) { yHeadRot = v; }
    @Override public float getXHeadRot() { return xHeadRot; }
    @Override public void setXHeadRot(float v) { xHeadRot = v; }
    @Override public float getYBodyRot() { return yBodyRot; }
    @Override public void setYBodyRot(float v) { yBodyRot = v; }
}
