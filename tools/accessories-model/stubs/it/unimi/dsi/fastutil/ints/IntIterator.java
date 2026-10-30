package it.unimi.dsi.fastutil.ints;
import java.util.Iterator;
public interface IntIterator extends Iterator<Integer> {
    int nextInt();
    default Integer next() { return Integer.valueOf(nextInt()); }
}
