package org.bukkit.inventory;
import java.util.*;
public class ItemStack {
 public final org.bukkit.Material type; public FakeMeta meta=new FakeMeta();
 public ItemStack(org.bukkit.Material t){type=t;} public org.bukkit.Material getType(){return type;} public boolean hasItemMeta(){return meta!=null;}
 public org.bukkit.inventory.meta.ItemMeta getItemMeta(){return meta;}
 public static class FakeMeta implements org.bukkit.inventory.meta.ItemMeta { public FakeData data=new FakeData(); public org.bukkit.persistence.PersistentDataContainer getPersistentDataContainer(){return data;} }
 public static class FakeData implements org.bukkit.persistence.PersistentDataContainer { public Map<String,String> data=new HashMap<>(); @SuppressWarnings("unchecked") public <P,C> C get(org.bukkit.NamespacedKey k,org.bukkit.persistence.PersistentDataType<P,C> t){return (C)data.get(k.ns+":"+k.key);} }
}
