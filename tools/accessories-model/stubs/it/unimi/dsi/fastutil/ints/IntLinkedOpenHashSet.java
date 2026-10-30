package it.unimi.dsi.fastutil.ints;
import java.util.LinkedHashSet;
public class IntLinkedOpenHashSet extends LinkedHashSet<Integer> implements IntSet {
    private static final long serialVersionUID = 1L;
    public boolean add(int k) { return super.add(Integer.valueOf(k)); }
    public boolean contains(int k) { return super.contains(Integer.valueOf(k)); }
    public IntListIterator iterator() {
        return IntIterators.wrapList(new java.util.ArrayList<Integer>(this));
    }
}
