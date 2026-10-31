package com.ticxo.modelengine.api.entity.data;
import com.ticxo.modelengine.api.entity.BaseEntity;
import com.ticxo.modelengine.api.entity.CullType;
import com.ticxo.modelengine.api.nms.entity.wrapper.TrackedEntity;
/**
 * Compile-time stand-in: the Bukkit implementation of {@link IEntityData}.
 * {@code getTracked()} is what lets a plugin put the wearer into the model's
 * own tracking set - without it the player never receives their own model.
 */
public class BukkitEntityData implements IEntityData {
    public TrackedEntity getTracked() { return null; }
    @Override public BaseEntity getBaseEntity() { return null; }
    @Override public boolean hasTracking() { return false; }
    @Override public void setVerticalCull(Boolean v) {}
    @Override public void setBackCull(Boolean v) {}
    @Override public void setBlockedCull(Boolean v) {}
    @Override public void setCullInterval(Integer v) {}
    @Override public void setVerticalCullType(CullType v) {}
    @Override public void setBackCullType(CullType v) {}
    @Override public void setBlockedCullType(CullType v) {}
    @Override public void setCullExempt(java.util.UUID uuid, boolean exempt) {}
}
