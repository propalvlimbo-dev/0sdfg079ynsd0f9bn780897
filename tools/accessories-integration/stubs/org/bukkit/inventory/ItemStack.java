package org.bukkit.inventory; import org.bukkit.Material; import org.bukkit.NamespacedKey; import org.bukkit.inventory.meta.ItemMeta;
public class ItemStack {
    public static class Meta implements ItemMeta {
        public String title; public java.util.List<String> lore; public NamespacedKey model; public Integer cmd;
        public void setLore(java.util.List<String> l){lore=l;} public void setDisplayName(String t){title=t;}
        public void setItemModel(NamespacedKey k){model=k;} public void setCustomModelData(Integer d){cmd=d;}
    }
    public final Meta meta=new Meta(); public ItemStack(Material mat){} public ItemMeta getItemMeta(){return meta;}
    public boolean setItemMeta(ItemMeta m){return m==meta;}
}
