package pw.elytrix.freakmodel;
import org.bukkit.Location;
import org.bukkit.entity.Player;

/** Compile-time stand-in for PlayerBodyTracker already shipped in ElytrixFreakModel.jar. */
public final class PlayerBodyTracker {
    private float bodyYaw;
    private double speed;
    public synchronized void resetToYaw(float yaw) {
        this.bodyYaw = yaw;
    }
    public synchronized void resetToPlayer(Player player) {
        if (player != null) this.bodyYaw = player.getBodyYaw();
    }
    public synchronized void stepFromPacket(Player player, Location to) {
        if (to != null) this.bodyYaw = to.getYaw();
        else if (player != null) this.bodyYaw = player.getBodyYaw();
    }
    public synchronized void stepServerTick(Player player) {
        if (player != null && this.bodyYaw == 0.0F) this.bodyYaw = player.getBodyYaw();
    }
    public synchronized void notifyArmSwing() {}
    public synchronized float getBodyYaw() { return bodyYaw; }
    public synchronized double getHorizSpeedBlocksPerTick() { return speed; }
    public synchronized void setMockState(float yaw, double speed) {
        this.bodyYaw = yaw;
        this.speed = speed;
    }
}
