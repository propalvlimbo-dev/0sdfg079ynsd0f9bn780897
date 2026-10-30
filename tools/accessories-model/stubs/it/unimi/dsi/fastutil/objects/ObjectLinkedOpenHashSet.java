package it.unimi.dsi.fastutil.objects;
import java.util.LinkedHashSet;
public class ObjectLinkedOpenHashSet<K> extends LinkedHashSet<K> implements ObjectSet<K> {
    private static final long serialVersionUID = 1L;
    public ObjectIterator<K> iterator() {
        final java.util.Iterator<K> it = super.iterator();
        return new ObjectIterator<K>() {
            public boolean hasNext() { return it.hasNext(); }
            public K next() { return it.next(); }
            public void remove() { it.remove(); }
        };
    }
}
