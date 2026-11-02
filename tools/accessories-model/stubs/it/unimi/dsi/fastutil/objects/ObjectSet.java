package it.unimi.dsi.fastutil.objects;
public interface ObjectSet<K> extends java.util.Set<K>, ObjectCollection<K> {
    ObjectIterator<K> iterator();
}
