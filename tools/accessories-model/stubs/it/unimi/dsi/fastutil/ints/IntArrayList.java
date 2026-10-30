package it.unimi.dsi.fastutil.ints;
import java.util.ArrayList;
public class IntArrayList extends ArrayList<Integer> {
    private static final long serialVersionUID = 1L;
    public IntArrayList() { super(); }
    public IntArrayList(java.util.Collection<? extends Integer> c) { super(c); }
    public boolean add(int k) { return super.add(Integer.valueOf(k)); }
    public IntIterator iterator() { return IntIterators.wrap(super.iterator()); }
}
