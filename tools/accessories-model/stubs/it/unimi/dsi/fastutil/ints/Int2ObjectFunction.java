package it.unimi.dsi.fastutil.ints;
@FunctionalInterface
public interface Int2ObjectFunction<V> {
    V get(int key);
    default V apply(int key) { return get(key); }
}
