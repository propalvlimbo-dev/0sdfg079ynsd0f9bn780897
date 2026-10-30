package it.unimi.dsi.fastutil.objects;
import java.util.LinkedHashMap;
public class Object2ObjectOpenHashMap<K, V> extends LinkedHashMap<K, V> {
    private static final long serialVersionUID = 1L;
    public V computeIfAbsent(K k, Object2ObjectFunction<? super K, ? extends V> f) {
        V v = get(k);
        if (v == null) { v = f.get(k); if (v != null) put(k, v); }
        return v;
    }
}
