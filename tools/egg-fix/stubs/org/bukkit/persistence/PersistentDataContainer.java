package org.bukkit.persistence;
public interface PersistentDataContainer {
 <P,C> void set(org.bukkit.NamespacedKey k,PersistentDataType<P,C> t,C v);
 <P,C> boolean has(org.bukkit.NamespacedKey k,PersistentDataType<P,C> t);
}
