package org.bukkit.event.player;
import org.bukkit.Location;
import org.bukkit.entity.Player;
public class PlayerMoveEvent {
    private final Player player;
    private final Location to;
    public boolean cancelled;
    public PlayerMoveEvent(Player player, Location to) { this.player = player; this.to = to; }
    public Player getPlayer() { return player; }
    public Location getTo() { return to; }
    public boolean isCancelled() { return cancelled; }
    public void setCancelled(boolean cancel) { this.cancelled = cancel; }
}
