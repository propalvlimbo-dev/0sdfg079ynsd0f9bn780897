package pw.elytrix.freakmodel;

import org.bukkit.Input;
import org.bukkit.Location;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

/** Tracks the likely client-rendered player body yaw, separately from head yaw.
 * Paper's server-side getBodyYaw is not a reliable representation of the body
 * rendered by each client. Run the approximation once per server tick, not once
 * per movement packet: packet frequency varies even when the game tick does not.
 */
public final class PlayerBodyTracker {
    public enum MovementMode { IDLE, WALK, FLY }
    private final Location scratch = new Location(null, 0, 0, 0);
    private final Location vehicleScratch = new Location(null, 0, 0, 0);
    private boolean initialized;
    private String worldName;
    private double previousX, previousZ, speed;
    private float bodyYaw, headYaw, turnSpeed;
    // An event-time visual preview must not alter the tick simulation's state.
    private float packetBodyYaw;
    private boolean hasPacketBodyYaw;
    private int movingHoldTicks, airborneHoldTicks, swingTicks;
    private MovementMode mode = MovementMode.IDLE;

    public static float wrapDegrees(float angle) {
        angle %= 360.0f;
        if (angle >= 180.0f) angle -= 360.0f;
        if (angle < -180.0f) angle += 360.0f;
        return angle;
    }
    private static float validYaw(float candidate, float fallback) {
        return Float.isFinite(candidate) ? candidate : (Float.isFinite(fallback) ? fallback : 0.0f);
    }
    private static float clamp(float value, float low, float high) {
        return Math.max(low, Math.min(high, value));
    }
    public synchronized void resetToYaw(float yaw) {
        if (!Float.isFinite(yaw)) return;
        bodyYaw = headYaw = yaw;
        packetBodyYaw = yaw;
        hasPacketBodyYaw = false;
        turnSpeed = 0;
        initialized = false;
        speed = 0;
        movingHoldTicks = airborneHoldTicks = swingTicks = 0;
        mode = MovementMode.IDLE;
    }
    public synchronized void resetToPlayer(Player player) {
        if (player == null) return;
        Location loc = player.getLocation(scratch);
        float yaw = validYaw(loc.getYaw(), headYaw);
        resetToYaw(yaw);
        if (loc.getWorld() != null) {
            worldName = loc.getWorld().getName();
            previousX = loc.getX();
            previousZ = loc.getZ();
            initialized = true;
        }
    }
    public synchronized void stepFromPacket(Player player, Location to) {
        if (player == null || to == null || to.getWorld() == null) return;
        // Show a bounded correction immediately, but leave the last completed
        // tick's bodyYaw unchanged. Otherwise the next tick applies its movement
        // smoothing on top of the packet correction and rotates the body twice.
        headYaw = validYaw(to.getYaw(), headYaw);
        hasPacketBodyYaw = false;
        if (initialized && to.getWorld().getName().equals(worldName) && !player.isInsideVehicle()) {
            float delta = wrapDegrees(headYaw - bodyYaw);
            packetBodyYaw = bodyYaw + delta - clamp(delta, -50.0f, 50.0f);
            hasPacketBodyYaw = true;
        }
    }
    public synchronized void stepServerTick(Player player) {
        if (player == null) return;
        Location loc = player.getLocation(scratch);
        if (loc.getWorld() == null) return;
        float yaw = validYaw(loc.getYaw(), headYaw);
        String world = loc.getWorld().getName();
        hasPacketBodyYaw = false;
        if (!initialized || !world.equals(worldName)) {
            resetToPlayer(player);
            return;
        }
        double x = loc.getX(), z = loc.getZ();
        double dx = x - previousX, dz = z - previousZ;
        double distanceSquared = dx * dx + dz * dz;
        previousX = x;
        previousZ = z;
        headYaw = yaw;
        if (distanceSquared > 64.0) {
            // Large teleports are not a direction of walking.
            resetToPlayer(player);
            return;
        }
        speed = speed * 0.45 + Math.sqrt(distanceSquared) * 0.55;
        float previousBody = bodyYaw;
        if (player.isInsideVehicle()) {
            Entity vehicle = player.getVehicle();
            float vehicleYaw = vehicle == null ? yaw : validYaw(vehicle.getLocation(vehicleScratch).getYaw(), yaw);
            float relative = clamp(wrapDegrees(yaw - vehicleYaw), -85.0f, 85.0f);
            bodyYaw = yaw - relative;
            if (relative * relative > 2500.0f) bodyYaw += relative * 0.2f;
        } else {
            float target = bodyYaw;
            if (distanceSquared > 0.0025000002) {
                float movementYaw = (float)Math.toDegrees(Math.atan2(dz, dx)) - 90.0f;
                float difference = Math.abs(wrapDegrees(yaw) - movementYaw);
                target = difference > 95.0f && difference < 265.0f ? movementYaw - 180.0f : movementYaw;
            }
            if (swingTicks > 0) target = yaw;
            bodyYaw += wrapDegrees(target - bodyYaw) * 0.3f;
            // Limit the body's angle relative to the head, without forcing the
            // body to follow small head-only movements while standing still.
            bodyYaw = yaw - clamp(wrapDegrees(yaw - bodyYaw), -50.0f, 50.0f);
        }
        turnSpeed = Math.abs(wrapDegrees(bodyYaw - previousBody));
        if (swingTicks > 0) --swingTicks;
        boolean inputMoving = false;
        try {
            Input input = player.getCurrentInput();
            // Opposing keys cancel on the same axis. W+A+D is still forward,
            // while A+D (or W+S) alone must not start a walking animation.
            inputMoving = input != null && ((input.isForward() != input.isBackward())
                    || (input.isLeft() != input.isRight()));
        } catch (LinkageError ignored) { /* API compatibility */ }
        boolean flying = player.isFlying() || player.isGliding();
        boolean airborne = !player.isOnGround() && !player.isInsideVehicle() && !player.isSwimming()
                && Math.abs(player.getVelocity().getY()) > 0.16;
        if (flying) airborneHoldTicks = 6;
        else if (airborne) airborneHoldTicks = Math.min(6, airborneHoldTicks + 1);
        else if (airborneHoldTicks > 0) --airborneHoldTicks;
        if ((inputMoving || speed > 0.018 || player.isSprinting()) && !player.isInsideVehicle()) movingHoldTicks = 5;
        else if (movingHoldTicks > 0) --movingHoldTicks;
        mode = flying || airborneHoldTicks >= 3 ? MovementMode.FLY : movingHoldTicks > 0 ? MovementMode.WALK : MovementMode.IDLE;
    }
    public synchronized void notifyArmSwing() { swingTicks = 6; }
    // Preserved for compatibility; swing time is advanced exactly once per tick.
    public synchronized void decayArmSwing() { }
    public synchronized float getBodyYaw() { return hasPacketBodyYaw ? packetBodyYaw : bodyYaw; }
    public synchronized float getRawHeadYaw() { return headYaw; }
    public synchronized float getLastTickTurnSpeed() { return turnSpeed; }
    public synchronized MovementMode getMode() { return mode; }
    public synchronized double getHorizSpeedBlocksPerTick() { return speed; }
}
