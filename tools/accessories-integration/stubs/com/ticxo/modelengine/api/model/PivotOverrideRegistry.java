package com.ticxo.modelengine.api.model;
import org.bukkit.entity.Entity;
/** Compile-time stand-in. */
public interface PivotOverrideRegistry {
    PivotOverride getOrCreate(Entity entity);
}
