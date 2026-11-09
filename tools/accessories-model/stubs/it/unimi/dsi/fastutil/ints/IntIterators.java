package it.unimi.dsi.fastutil.ints;
import java.util.Iterator;
/** Helpers building the int iterator views used by the stand-ins. */
public final class IntIterators {
    private IntIterators() {}
    public static IntIterator wrap(final Iterator<Integer> it) {
        return new IntIterator() {
            public boolean hasNext() { return it.hasNext(); }
            public int nextInt() { return it.next().intValue(); }
            public void remove() { it.remove(); }
        };
    }
    public static IntListIterator wrapList(final java.util.List<Integer> list) {
        return new IntListIterator() {
            private int i = 0;
            public boolean hasNext() { return i < list.size(); }
            public int nextInt() { return list.get(i++).intValue(); }
            public boolean hasPrevious() { return i > 0; }
            public int previousInt() { return list.get(--i).intValue(); }
        };
    }
}
