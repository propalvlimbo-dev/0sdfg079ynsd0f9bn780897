package com.ticxo.modelengine.api.entity;
import com.ticxo.modelengine.api.entity.data.IEntityData;
import java.util.UUID;
/** Compile-time stand-in: ModelEngine 4.1.0 ships this as an interface. */
public interface BaseEntity {
    IEntityData getData();
    int getEntityId();
    UUID getUUID();
}
