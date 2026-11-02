package org.joml;
/** Compile-time stand-in for joml's mutable 3-vector. */
public class Vector3f {
    public float x, y, z;
    public Vector3f() {}
    public Vector3f(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
    public Vector3f set(float x, float y, float z) { this.x = x; this.y = y; this.z = z; return this; }
}
