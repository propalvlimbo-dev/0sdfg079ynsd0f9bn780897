package cs.cloudstudio.recovered.cloudenchants;
import org.bukkit.Material; import org.bukkit.inventory.ItemStack;
public class CompatTest {
 static void check(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[] args){
  for(CustomEnchant c:CustomEnchant.values()){
   ItemStack book=new ItemStack(Material.ENCHANTED_BOOK);String k="really-enchants:"+c.configKey();
   book.meta.data.data.put(k,c.name()+"_BOOK");check(LegacyEnchantCompat.has(book,c));
   book.meta.data.data.put(k,c.name());check(LegacyEnchantCompat.has(book,c));
   book.meta.data.data.put(k,"BAD_BOOK");check(!LegacyEnchantCompat.has(book,c));
   book.meta.data.data.remove(k);book.meta.data.data.put("minecraft:"+c.configKey(),c.name()+"_BOOK");check(!LegacyEnchantCompat.has(book,c));
   ItemStack axe=new ItemStack(Material.NETHERITE_AXE);axe.meta.data.data.put(k,c.name()+"_BOOK");check(!LegacyEnchantCompat.has(axe,c));axe.meta.data.data.put(k,c.name());check(LegacyEnchantCompat.has(axe,c));
  }
  check(!LegacyEnchantCompat.has(null,CustomEnchant.TELEPATION));
  System.out.println("Legacy enchant mock tests passed");
 }
}
