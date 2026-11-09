package org.bukkit.event.player;
import org.bukkit.entity.Player;
public class PlayerChangedWorldEvent {
    private final Player player;
    public PlayerChangedWorldEvent(Player player) { this.player = player; }
    public Player getPlayer() { return player; }
}
