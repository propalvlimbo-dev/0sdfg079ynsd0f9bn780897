package it.unimi.dsi.fastutil.ints;
import it.unimi.dsi.fastutil.objects.ObjectSet;
public interface Int2ObjectMap<V> extends java.util.Map<Integer, V> {
    V get(int k);
    V put(int k, V v);
    default V computeIfAbsent(int k, Int2ObjectFunction<? extends V> f) {
        V v = get(k);
        if (v == null) { v = f.get(k); if (v != null) put(k, v); }
        return v;
    }
    IntSet keySet();
    ObjectSet<Int2ObjectMap.Entry<V>> int2ObjectEntrySet();
    interface Entry<V> extends java.util.Map.Entry<Integer, V> {
        int getIntKey();
        V getValue();
    }
}
