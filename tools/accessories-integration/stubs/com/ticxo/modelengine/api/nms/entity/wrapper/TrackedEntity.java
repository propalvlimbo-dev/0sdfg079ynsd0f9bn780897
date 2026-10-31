package com.ticxo.modelengine.api.nms.entity.wrapper;
import java.util.UUID;
/** Compile-time stand-in: the NMS entity tracker wrapper (interface in 4.1.0). */
public interface TrackedEntity {
    int getBaseRange();
    void setBaseRange(int range);
    void addForcedPairing(UUID player);
    void removeForcedPairing(UUID player);
}
