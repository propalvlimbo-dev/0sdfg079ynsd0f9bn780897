package it.unimi.dsi.fastutil.ints;
public interface IntSet extends java.util.Set<Integer> {
    boolean add(int k);
    boolean contains(int k);
    IntIterator iterator();
}
