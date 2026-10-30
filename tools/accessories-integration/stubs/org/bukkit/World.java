package org.bukkit; import org.bukkit.entity.Entity; import java.util.Collection; import java.util.List;
/** Compile-time stand-in: a world only has to answer "what is near this point". */
public interface World { Collection<Entity> getNearbyEntities(Location location,double x,double y,double z); }
