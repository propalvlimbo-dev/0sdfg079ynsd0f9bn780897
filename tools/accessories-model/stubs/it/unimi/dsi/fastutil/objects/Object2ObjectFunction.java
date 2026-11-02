package it.unimi.dsi.fastutil.objects;
@FunctionalInterface
public interface Object2ObjectFunction<K, V> {
    V get(Object key);
    default V apply(Object key) { return get(key); }
}
