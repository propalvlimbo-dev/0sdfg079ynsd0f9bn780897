package org.bukkit.persistence; public interface PersistentDataContainer { <P,C> C get(org.bukkit.NamespacedKey k,PersistentDataType<P,C> type); }
