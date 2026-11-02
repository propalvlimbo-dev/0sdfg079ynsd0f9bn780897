package org.bukkit.event.entity;
import org.bukkit.entity.Player;
public class PlayerDeathEvent {
    private final Player entity;
    public PlayerDeathEvent(Player entity) { this.entity = entity; }
    public Player getEntity() { return entity; }
}
