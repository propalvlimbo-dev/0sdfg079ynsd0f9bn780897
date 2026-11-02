package it.unimi.dsi.fastutil.ints;
public interface IntListIterator extends IntIterator {
    boolean hasPrevious();
    int previousInt();
    default Integer previous() { return Integer.valueOf(previousInt()); }
}
