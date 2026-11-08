package org.bukkit.event.player;
import org.bukkit.entity.Player;
public class PlayerToggleSneakEvent {
    private final Player player;
    private final boolean isSneaking;
    public boolean cancelled;
    public PlayerToggleSneakEvent(Player player, boolean isSneaking) {
        this.player = player;
        this.isSneaking = isSneaking;
    }
    public Player getPlayer() { return player; }
    public boolean isSneaking() { return isSneaking; }
    public boolean isCancelled() { return cancelled; }
    public void setCancelled(boolean cancel) { this.cancelled = cancel; }
}
