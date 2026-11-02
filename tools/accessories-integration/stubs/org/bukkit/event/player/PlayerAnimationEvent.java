package org.bukkit.event.player;
import org.bukkit.entity.Player;
public class PlayerAnimationEvent {
    private final Player player;
    public PlayerAnimationEvent(Player player) { this.player = player; }
    public Player getPlayer() { return player; }
}
