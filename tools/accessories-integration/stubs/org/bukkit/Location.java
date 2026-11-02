package org.bukkit;
public class Location {
    private final World world;
    private final double x, y, z;
    private final float yaw, pitch;
    public Location(World w, double x, double y, double z) {
        this(w, x, y, z, 0.0F, 0.0F);
    }
    public Location(World w, double x, double y, double z, float yaw, float pitch) {
        this.world = w;
        this.x = x;
        this.y = y;
        this.z = z;
        this.yaw = yaw;
        this.pitch = pitch;
    }
    public World getWorld() { return world; }
    public double getX() { return x; }
    public double getY() { return y; }
    public double getZ() { return z; }
    public float getYaw() { return yaw; }
    public float getPitch() { return pitch; }
}
