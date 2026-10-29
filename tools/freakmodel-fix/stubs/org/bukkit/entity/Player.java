package org.bukkit.entity;
import org.bukkit.Input; import org.bukkit.Location; import org.bukkit.util.Vector;
public interface Player { Location getLocation(Location location); float getBodyYaw(); Input getCurrentInput(); boolean isFlying(); boolean isGliding(); boolean isOnGround(); boolean isInsideVehicle(); boolean isSwimming(); boolean isSprinting(); Vector getVelocity(); }
