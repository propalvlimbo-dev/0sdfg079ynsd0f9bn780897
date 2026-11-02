package it.unimi.dsi.fastutil.ints;
import it.unimi.dsi.fastutil.objects.ObjectSet;
import it.unimi.dsi.fastutil.objects.Sets;
import java.util.LinkedHashMap;
import java.util.Map;
public class Int2ObjectOpenHashMap<V> extends LinkedHashMap<Integer, V> implements Int2ObjectMap<V> {
    private static final long serialVersionUID = 1L;
    public V get(int k) { return super.get(Integer.valueOf(k)); }
    public V put(int k, V v) { return super.put(Integer.valueOf(k), v); }
    public IntSet keySet() { return IntSets.wrap(super.keySet()); }
    public ObjectSet<Int2ObjectMap.Entry<V>> int2ObjectEntrySet() {
        final Map<Integer, V> self = this;
        java.util.List<Int2ObjectMap.Entry<V>> list = new java.util.ArrayList<>();
        for (Map.Entry<Integer, V> e : self.entrySet()) {
            final int key = e.getKey();
            final V value = e.getValue();
            list.add(new Int2ObjectMap.Entry<V>() {
                public int getIntKey() { return key; }
                public V getValue() { return value; }
                public Integer getKey() { return Integer.valueOf(key); }
                public V setValue(V v) { return self.put(key, v); }
            });
        }
        return Sets.objectSet(new java.util.LinkedHashSet<Int2ObjectMap.Entry<V>>(list));
    }
}
