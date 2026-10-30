package org.bukkit.inventory; import org.bukkit.Material; import org.bukkit.NamespacedKey; import org.bukkit.inventory.meta.ItemMeta;
public class ItemStack {
    public static class Meta implements ItemMeta {
        public String title; public java.util.List<String> lore; public NamespacedKey model; public Integer cmd;
        public final FakeEquippable equippable = new FakeEquippable();
        public final org.bukkit.persistence.PersistentDataContainer data = new Data();
        public void setLore(java.util.List<String> l){lore=l;} public void setDisplayName(String t){title=t;}
        public void setItemModel(NamespacedKey k){model=k;} public void setCustomModelData(Integer d){cmd=d;}
        public org.bukkit.inventory.meta.components.EquippableComponent getEquippable(){return equippable;}
        public void setEquippable(org.bukkit.inventory.meta.components.EquippableComponent c){
            equippable.slot = c.getSlot(); equippable.model = c.getModel();
        }
        public org.bukkit.persistence.PersistentDataContainer getPersistentDataContainer(){return data;}
    }
    public static class FakeEquippable implements org.bukkit.inventory.meta.components.EquippableComponent {
        public org.bukkit.inventory.EquipmentSlot slot; public NamespacedKey model;
        public org.bukkit.inventory.EquipmentSlot getSlot(){return slot;} public void setSlot(org.bukkit.inventory.EquipmentSlot s){slot=s;}
        public NamespacedKey getModel(){return model;} public void setModel(NamespacedKey k){model=k;}
    }
    public static class Data implements org.bukkit.persistence.PersistentDataContainer {
        public final java.util.Map<NamespacedKey,Object> map = new java.util.HashMap<>();
        @SuppressWarnings("unchecked") public <P,C> C get(NamespacedKey k, org.bukkit.persistence.PersistentDataType<P,C> t){return (C) map.get(k);}
        public <P,C> void set(NamespacedKey k, org.bukkit.persistence.PersistentDataType<P,C> t, C v){map.put(k,v);}
        public void remove(NamespacedKey k){map.remove(k);}
    }
    public final Meta meta=new Meta(); public final Material type; public ItemStack(Material mat){type=mat;} public Material getType(){return type;} public ItemMeta getItemMeta(){return meta;}
    public boolean setItemMeta(ItemMeta m){return m==meta;}
}
