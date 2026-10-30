package pw.elytrix.freakmodel;
import java.util.*;
import org.bukkit.*;
import org.bukkit.entity.*;
import org.bukkit.inventory.*;
import org.bukkit.persistence.*;
import org.bukkit.event.inventory.*;
import org.bukkit.command.*;
import org.bukkit.plugin.*;
import org.bukkit.event.*;
import com.ticxo.modelengine.api.ModelEngineAPI;

public class AccessoryTest {
 static class Data implements PersistentDataContainer {Map<NamespacedKey,Object> m=new HashMap<>();@SuppressWarnings("unchecked") public <P,C>C get(NamespacedKey k,PersistentDataType<P,C> t){return (C)m.get(k);}public <P,C>void set(NamespacedKey k,PersistentDataType<P,C> t,C v){m.put(k,v);} public void remove(NamespacedKey k){m.remove(k);}}
 static class PlayerFake implements Player {boolean admin;Data data=new Data();String msg;public boolean hasPermission(String s){return admin;}public Data getPersistentDataContainer(){return data;}public Inventory opened;public InventoryView openInventory(Inventory i){opened=i;return null;}public void sendMessage(String s){msg=s;}}
 static FreakModelSpec spec(String id){return new FreakModelSpec(id,ModelKind.ANGEL_WINGS,id,List.of(),Material.FEATHER,"model",34,id,List.of(),1,0,0,1,1,2,0,0,0,0,0,0,0,0,0,0,0,false,false);}
 static void check(boolean c,String s){if(!c)throw new AssertionError(s);}
 public static void main(String[] args){
  ElytrixFreakModelPlugin plugin=new ElytrixFreakModelPlugin();plugin.wings=spec("angel_wings");plugin.halo=spec("angel_halo");PlayerFake p=new PlayerFake();
  p.data.set(AccessoryController.BACK,PersistentDataType.STRING,"kaneki");p.data.set(AccessoryController.HALO,PersistentDataType.STRING,"halo");
  check(AccessoryController.back(plugin,p)==null && AccessoryController.halo(plugin,p)==null,"non-admin denied");
  p.admin=true;FreakModelSpec a=AccessoryController.back(plugin,p);check(a!=null && a.blueprintId.equals("elytrix_kaneki_tentacles"),"tentacles selected");check(a==AccessoryController.back(plugin,p),"reuses spec");check(AccessoryController.halo(plugin,p)==plugin.halo,"halo independent");
  p.data.set(AccessoryController.BACK,PersistentDataType.STRING,"wings");check(AccessoryController.back(plugin,p)==plugin.wings,"wings selected");
  p.data.set(AccessoryController.BACK,PersistentDataType.STRING,"bad");check(AccessoryController.back(plugin,p)==null,"unknown rejected");
  p.admin=false;check(AccessoryController.halo(plugin,p)==null,"permission revocation applied");
  class PM implements PluginManager {Listener listener;public void registerEvents(Listener l,Plugin p){listener=l;}} PM pm=new PM();Bukkit.manager=pm;
  AccessoryController.install(plugin);AccessoryController controller=(AccessoryController)pm.listener;
  check(plugin.mockCommand.executor==controller,"executor registered");
  p.admin=false;check(controller.onCommand(p,new Command(),"аксессуары",new String[0]),"command handled");
  check(p.opened!=null,"menu visible to non-admin");
  check(Bukkit.slots.get(15).meta.model.equals(new NamespacedKey("reallyworld","kaneki_tentacles_icon")),"tentacle menu icon");
  check(Bukkit.slots.get(11).meta.model.equals(new NamespacedKey("reallyworld","angel_wings")),"wings icon");
  InventoryClickEvent click=new InventoryClickEvent();click.view=()->p.opened;click.who=p;click.slot=15;
  p.data.remove(AccessoryController.BACK);controller.onClick(click);check(click.cancelled && AccessoryController.back(plugin,p)==null && !p.data.m.containsKey(AccessoryController.BACK),"non-admin click denied");
  p.admin=true;ModelEngineAPI.loaded=false;controller.onClick(click);check(!p.data.m.containsKey(AccessoryController.BACK),"missing model denied");
  ModelEngineAPI.loaded=true;controller.onClick(click);check(AccessoryController.back(plugin,p).blueprintId.equals("elytrix_kaneki_tentacles"),"menu selection");
  click.slot=13;controller.onClick(click);check(AccessoryController.halo(plugin,p)==plugin.halo,"independent halo click");
  click.slot=11;controller.onClick(click);check(AccessoryController.back(plugin,p)==plugin.wings,"wings replace tentacles");
  click.slot=21;controller.onClick(click);check(AccessoryController.back(plugin,p)==null && AccessoryController.halo(plugin,p)!=null,"clear only back");
  InventoryDragEvent drag=new InventoryDragEvent();drag.view=click.view;controller.onDrag(drag);check(drag.cancelled,"drag cancelled");
  System.out.println("Accessory GUI, permission, selection and cached tentacle spec mock tests passed");
 }
}
