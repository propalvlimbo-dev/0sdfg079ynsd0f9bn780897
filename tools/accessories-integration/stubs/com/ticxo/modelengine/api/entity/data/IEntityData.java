package com.ticxo.modelengine.api.entity.data;
import com.ticxo.modelengine.api.entity.BaseEntity;
import com.ticxo.modelengine.api.entity.CullType;
/** Compile-time stand-in: the per-entity data ModelEngine keeps (tracking, culling). */
public interface IEntityData {
    BaseEntity getBaseEntity();
    boolean hasTracking();
    void setVerticalCull(Boolean verticalCull);
    void setBackCull(Boolean backCull);
    void setBlockedCull(Boolean blockedCull);
    void setCullInterval(Integer interval);
    void setVerticalCullType(CullType type);
    void setBackCullType(CullType type);
    void setBlockedCullType(CullType type);
    void setCullExempt(java.util.UUID uuid, boolean exempt);
}
