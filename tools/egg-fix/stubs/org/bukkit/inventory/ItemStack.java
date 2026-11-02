package org.bukkit.inventory;
public class ItemStack implements Cloneable {
 private org.bukkit.Material type; private int amount; private org.bukkit.inventory.meta.ItemMeta meta=new FakeMeta();
 public ItemStack(org.bukkit.Material m,int n){type=m;amount=n;}
 public org.bukkit.Material getType(){return type;} public int getAmount(){return amount;} public void setAmount(int n){amount=n;}
 public int getMaxStackSize(){return 64;} public boolean isSimilar(ItemStack other){return type==other.type;}
 public boolean hasItemMeta(){return meta!=null;} public org.bukkit.inventory.meta.ItemMeta getItemMeta(){return meta;}
 public boolean setItemMeta(org.bukkit.inventory.meta.ItemMeta m){meta=m;return true;} public ItemStack clone(){return new ItemStack(type,amount);}
 public static class FakeMeta implements org.bukkit.inventory.meta.ItemMeta {
  private final FakeData data=new FakeData();
  public void displayName(net.kyori.adventure.text.Component c){} public void lore(java.util.List<? extends net.kyori.adventure.text.Component> l){}
  public org.bukkit.persistence.PersistentDataContainer getPersistentDataContainer(){return data;}
 }
 public static class FakeData implements org.bukkit.persistence.PersistentDataContainer {
  boolean has; public <P,C> void set(org.bukkit.NamespacedKey k,org.bukkit.persistence.PersistentDataType<P,C> t,C v){has=true;}
  public <P,C> boolean has(org.bukkit.NamespacedKey k,org.bukkit.persistence.PersistentDataType<P,C> t){return has;}
 }
}
