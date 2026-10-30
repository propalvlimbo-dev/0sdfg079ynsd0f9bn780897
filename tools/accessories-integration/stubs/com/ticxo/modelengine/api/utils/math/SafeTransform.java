package com.ticxo.modelengine.api.utils.math;
import org.joml.Vector3f;
import java.util.function.Consumer;
/** Compile-time stand-in for the double-buffered transform. */
public class SafeTransform {
    private final Transform safe = new Transform();
    public Vector3f getSafePosition() { return safe.getPosition(); }
    public Vector3f getSafeLeftEuler() { return safe.getLeftEuler(); }
    public Vector3f setPosition(Vector3f value) { return safe.setPosition(value); }
    public Vector3f setLeftEuler(Vector3f value) { return safe.setLeftEuler(value); }
    public void mutateSafe(Consumer<Transform> consumer) { consumer.accept(safe); }
}
