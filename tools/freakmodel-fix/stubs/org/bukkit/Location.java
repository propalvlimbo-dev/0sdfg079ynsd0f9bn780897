package org.bukkit;
public class Location {
    private World world; private double x, z; private float yaw;
    public Location(World world, double x, double y, double z) { this.world=world; this.x=x; this.z=z; }
    public World getWorld(){return world;} public double getX(){return x;} public double getZ(){return z;} public float getYaw(){return yaw;}
    public void set(World world, double x, double y, double z, float yaw) { this.world=world; this.x=x; this.z=z; this.yaw=yaw; }
}
