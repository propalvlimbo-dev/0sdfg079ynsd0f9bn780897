package org.bukkit.entity;
import org.bukkit.Input; import org.bukkit.util.Vector;
public interface Player extends Entity { float getBodyYaw(); Input getCurrentInput(); boolean isFlying(); boolean isGliding(); boolean isOnGround(); boolean isInsideVehicle(); Entity getVehicle(); boolean isSwimming(); boolean isSprinting(); Vector getVelocity(); }
