package com.ticxo.modelengine.api.utils.data.tracker;
/** Compile-time stand-in: the passenger list of a pivot. */
public class CollectionDataTracker extends DataTracker {
    public boolean contains(Object value) { return false; }
    public boolean add(Object value) { return false; }
    public boolean remove(Object value) { return false; }
}
