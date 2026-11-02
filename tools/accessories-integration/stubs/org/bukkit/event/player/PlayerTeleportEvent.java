package org.bukkit.event.player;
import org.bukkit.Location;
import org.bukkit.entity.Player;
public class PlayerTeleportEvent extends PlayerMoveEvent {
    public PlayerTeleportEvent(Player player, Location to) { super(player, to); }
}
