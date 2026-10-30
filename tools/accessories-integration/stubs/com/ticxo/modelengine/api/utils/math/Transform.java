package com.ticxo.modelengine.api.utils.math;
import org.joml.Vector3f;
import java.util.function.Consumer;
/** Compile-time stand-in: the parts of ModelEngine's transform the crawler touches. */
public class Transform {
    private final Vector3f position = new Vector3f();
    private final Vector3f leftEuler = new Vector3f();
    public Vector3f getPosition() { return position; }
    public Vector3f getLeftEuler() { return leftEuler; }
    public Vector3f setPosition(Vector3f value) { return position.set(value.x, value.y, value.z); }
    public Vector3f setLeftEuler(Vector3f value) { return leftEuler.set(value.x, value.y, value.z); }
    public void mutatePosition(Consumer<Vector3f> consumer) { consumer.accept(position); }
    public void mutateLeftEuler(Consumer<Vector3f> consumer) { consumer.accept(leftEuler); }
}
