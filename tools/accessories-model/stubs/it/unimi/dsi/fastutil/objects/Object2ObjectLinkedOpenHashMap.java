package it.unimi.dsi.fastutil.objects;
import java.util.LinkedHashMap;
public class Object2ObjectLinkedOpenHashMap<K, V> extends LinkedHashMap<K, V> {
    private static final long serialVersionUID = 1L;
    public V computeIfAbsent(K k, Object2ObjectFunction<? super K, ? extends V> f) {
        V v = get(k);
        if (v == null) { v = f.get(k); if (v != null) put(k, v); }
        return v;
    }
    public ObjectSortedSet<java.util.Map.Entry<K, V>> entrySet() {
        return Sets.objectSortedSet(new java.util.ArrayList<java.util.Map.Entry<K, V>>(super.entrySet()));
    }
}
