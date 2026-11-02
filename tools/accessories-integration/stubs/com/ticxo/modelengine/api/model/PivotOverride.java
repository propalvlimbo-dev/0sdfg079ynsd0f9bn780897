package com.ticxo.modelengine.api.model;
import com.ticxo.modelengine.api.utils.data.tracker.CollectionDataTracker;
import org.bukkit.entity.Entity;
import org.joml.Vector3f;
import java.util.UUID;
import java.util.function.Supplier;
/**
 * Compile-time stand-in: in ModelEngine 4.1.0 this is a class with
 * {@code (UUID, int, Supplier<Vector3f>)} and a static {@code create(Entity)}.
 * The ctor is declared here on purpose so the stub mirrors the engine instead of
 * inventing a no-arg constructor the real class does not have.
 */
public class PivotOverride {
    public PivotOverride(UUID uuid, int id, Supplier<Vector3f> mountOffset) {}
    public static PivotOverride create(Entity entity) { return null; }
    public void addPassenger(int id) {}
    public void removePassenger(int id) {}
    public CollectionDataTracker getPassengers() { return null; }
}
