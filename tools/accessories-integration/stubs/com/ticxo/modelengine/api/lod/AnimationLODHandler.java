package com.ticxo.modelengine.api.lod;
import com.ticxo.modelengine.api.model.ModeledEntity;

public class AnimationLODHandler {
    private Boolean enabled = Boolean.TRUE;
    public AnimationLODHandler(ModeledEntity entity) {}
    public void setEnabled(Boolean enabled) { this.enabled = enabled; }
    public Boolean getEnabled() { return enabled; }
}
