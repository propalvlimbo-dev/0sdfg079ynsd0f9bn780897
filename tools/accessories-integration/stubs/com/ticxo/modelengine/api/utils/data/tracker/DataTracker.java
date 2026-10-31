package com.ticxo.modelengine.api.utils.data.tracker;
/** Compile-time stand-in: the base of every tracker, it owns markDirty(). */
public class DataTracker {
    public void markDirty() {}
    public void clearDirty() {}
    public boolean isDirty() { return false; }
    public Object get() { return null; }
    public void set(Object value) {}
}
