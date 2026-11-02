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
    private static final float MAX_VISUAL_LEAD_DEGREES = 18.0f;
    private static final float MAX_REVERSAL_LEAD_DEGREES = 12.0f;
    private static final float VISUAL_LEAD_FACTOR = 0.75f;
    private float bodyYaw, headYaw, turnSpeed, previousBodyStep;
    // Render targets are independent from the state of the body simulation.
    private float renderBodyYaw;
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
    /** One body simulation step; usable for a packet preview without mutating state. */
    private static float simulateBody(float body, float yaw, double dx, double dz, int swing) {
        float target = body;
        if (dx * dx + dz * dz > 0.0025000002) {
            float movementYaw = (float)Math.toDegrees(Math.atan2(dz, dx)) - 90.0f;
            float difference = Math.abs(wrapDegrees(yaw) - movementYaw);
            target = difference > 95.0f && difference < 265.0f ? movementYaw - 180.0f : movementYaw;
        }
        if (swing > 0) target = yaw;
        float next = body + wrapDegrees(target - body) * 0.3f;
        return yaw - clamp(wrapDegrees(yaw - next), -50.0f, 50.0f);
    }
    /** Bounded visual lead for the two-tick display interpolation. */
    private static float visualTarget(float body, float previous, float yaw,
                                      float lastStep, boolean eligible) {
        if (!eligible) return body;
        float delta = wrapDegrees(body - previous);
        // Don't compound the predictive overshoot on an abrupt direction
        // reversal. A small deadband ignores packet/position jitter.
        boolean reversal = Math.abs(delta) > 1.0f && Math.abs(lastStep) > 1.0f
                && delta * lastStep < 0.0f;
        float limit = reversal ? MAX_REVERSAL_LEAD_DEGREES : MAX_VISUAL_LEAD_DEGREES;
        float lead = clamp(delta * VISUAL_LEAD_FACTOR, -limit, limit);
        float result = body + lead;
        // Never predict outside the same head/body range used by the estimate.
        return yaw - clamp(wrapDegrees(yaw - result), -50.0f, 50.0f);
    }
    private static boolean canLead(Player player) {
        return !player.isInsideVehicle() && !player.isFlying() && !player.isGliding()
                && !player.isSwimming();
    }
    public synchronized void resetToYaw(float yaw) {
        if (!Float.isFinite(yaw)) return;
        bodyYaw = headYaw = yaw;
        renderBodyYaw = packetBodyYaw = yaw;
        hasPacketBodyYaw = false;
        turnSpeed = 0;
        previousBodyStep = 0;
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
        // Use the cumulative movement since the last tick to preview one body
        // step as soon as a move arrives. Never advance the committed state here:
        // multiple packets in the same tick must not add multiple rotations.
        headYaw = validYaw(to.getYaw(), headYaw);
        hasPacketBodyYaw = false;
        if (initialized && to.getWorld().getName().equals(worldName) && !player.isInsideVehicle()) {
            double dx = to.getX() - previousX, dz = to.getZ() - previousZ;
            if (dx * dx + dz * dz > 64.0) {
                packetBodyYaw = headYaw;
            } else {
                float preview = simulateBody(bodyYaw, headYaw, dx, dz, swingTicks);
                packetBodyYaw = visualTarget(preview, bodyYaw, headYaw, previousBodyStep, canLead(player));
            }
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
            bodyYaw = simulateBody(bodyYaw, yaw, dx, dz, swingTicks);
        }
        // Apply only to what is rendered, not to the client's-body estimate.
        // The short lead partially compensates the retained two-tick SLERP;
        // it disappears immediately when the estimated body stops turning.
        boolean eligibleForLead = canLead(player);
        renderBodyYaw = visualTarget(bodyYaw, previousBody, yaw, previousBodyStep, eligibleForLead);
        float bodyStep = wrapDegrees(bodyYaw - previousBody);
        turnSpeed = Math.abs(bodyStep);
        previousBodyStep = eligibleForLead ? bodyStep : 0;
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
    public synchronized float getBodyYaw() { return hasPacketBodyYaw ? packetBodyYaw : renderBodyYaw; }
    /** Body estimate before visual lead; exposed for diagnostics and tests. */
    public synchronized float getEstimatedBodyYaw() { return bodyYaw; }
    public synchronized float getRawHeadYaw() { return headYaw; }
    public synchronized float getLastTickTurnSpeed() { return turnSpeed; }
    public synchronized MovementMode getMode() { return mode; }
    public synchronized double getHorizSpeedBlocksPerTick() { return speed; }
}
