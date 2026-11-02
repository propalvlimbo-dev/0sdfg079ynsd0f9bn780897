package com.ticxo.modelengine.api.model;
import org.bukkit.entity.Entity;
/**
 * Compile-time stand-in.
 *
 * <p>In ModelEngine 4.1.0 this is a <b>class</b>, not an interface. Compiling
 * against an interface emitted {@code invokeinterface} and the server died with
 * {@code IncompatibleClassChangeError: Found class PivotOverrideRegistry, but
 * interface was expected}. build.py now cross-checks every stub against the real
 * jar, so this cannot slip through again.
 */
public class PivotOverrideRegistry {
    public PivotOverride getOrCreate(Entity entity) { return null; }
}
