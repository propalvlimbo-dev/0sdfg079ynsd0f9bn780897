package pw.elytrix.freakmodel;

import org.bukkit.Input;
import org.bukkit.Location;
import org.bukkit.entity.Player;

/** Compatibility replacement for the mismatched tracker shipped in 3.2.3.
 * Body rotation comes from the server's player entity, not a second independent
 * approximation of the vanilla body-turn algorithm.
 */
public final class PlayerBodyTracker {
    public enum MovementMode { IDLE, WALK, FLY }
    private final Location scratch = new Location(null, 0, 0, 0);
    private boolean initialized;
    private String worldName;
    private double previousX, previousZ, speed;
    private float bodyYaw, headYaw, turnSpeed;
    private int movingHoldTicks, airborneHoldTicks;
    private long lastMovementNanos;
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
    public synchronized void resetToYaw(float yaw) {
        if (!Float.isFinite(yaw)) return;
        bodyYaw = headYaw = yaw;
        turnSpeed = 0;
        // Re-baseline position after a teleport, even within the same world.
        initialized = false;
        speed = 0;
        movingHoldTicks = airborneHoldTicks = 0;
        mode = MovementMode.IDLE;
    }
    public synchronized void resetToPlayer(Player player) {
        if (player == null) return;
        Location loc = player.getLocation(scratch);
        headYaw = validYaw(loc.getYaw(), 0);
        bodyYaw = validYaw(player.getBodyYaw(), headYaw);
        turnSpeed = 0;
        speed = 0;
        movingHoldTicks = airborneHoldTicks = 0;
        mode = MovementMode.IDLE;
        initialized = loc.getWorld() != null;
        worldName = initialized ? loc.getWorld().getName() : null;
        previousX = loc.getX();
        previousZ = loc.getZ();
        lastMovementNanos = System.nanoTime();
    }
    private void sampleBody(Player player, float fallbackYaw) {
        float next = validYaw(player.getBodyYaw(), fallbackYaw);
        turnSpeed = Math.abs(wrapDegrees(next - bodyYaw));
        bodyYaw = next;
    }
    public synchronized void stepFromPacket(Player player, Location to) {
        if (player == null || to == null || to.getWorld() == null) return;
        String world = to.getWorld().getName();
        double x = to.getX(), z = to.getZ();
        headYaw = validYaw(to.getYaw(), headYaw);
        if (!initialized || !world.equals(worldName)) {
            initialized = true;
            worldName = world;
            previousX = x;
            previousZ = z;
            speed = 0;
        } else {
            double dx = x - previousX, dz = z - previousZ;
            double distanceSquared = dx * dx + dz * dz;
            previousX = x;
            previousZ = z;
            if (distanceSquared > 64.0) speed = 0;
            else if (distanceSquared > 1.0e-9) {
                speed = speed * 0.45 + Math.sqrt(distanceSquared) * 0.55;
                lastMovementNanos = System.nanoTime();
            }
        }
        // PlayerMoveEvent can precede the server's body-turn update. Never
        // advance a second simulation per packet; sample the real body instead.
        sampleBody(player, headYaw);
    }
    public synchronized void stepServerTick(Player player) {
        if (player == null) return;
        Location loc = player.getLocation(scratch);
        if (loc.getWorld() == null) return;
        if (!initialized || !loc.getWorld().getName().equals(worldName)) resetToPlayer(player);
        headYaw = validYaw(loc.getYaw(), headYaw);
        sampleBody(player, headYaw);
        if (System.nanoTime() - lastMovementNanos >= 75000000L) speed *= 0.55;
        boolean inputMoving = false;
        try {
            Input input = player.getCurrentInput();
            inputMoving = input != null && (input.isForward() || input.isBackward() || input.isLeft() || input.isRight());
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
    // Kept for binary compatibility with the original caller.
    public synchronized void notifyArmSwing() { }
    public synchronized void decayArmSwing() { }
    public synchronized float getBodyYaw() { return bodyYaw; }
    public synchronized float getRawHeadYaw() { return headYaw; }
    public synchronized float getLastTickTurnSpeed() { return turnSpeed; }
    public synchronized MovementMode getMode() { return mode; }
    public synchronized double getHorizSpeedBlocksPerTick() { return speed; }
}
