package org.bukkit.event.player;
import org.bukkit.entity.Player;
public class PlayerRespawnEvent {
    private final Player player;
    public PlayerRespawnEvent(Player player) { this.player = player; }
    public Player getPlayer() { return player; }
}
