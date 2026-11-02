package net.kyori.adventure.text.serializer.legacy;
public interface LegacyComponentSerializer {
 static LegacyComponentSerializer legacyAmpersand(){return s -> (t,b)->null;}
 net.kyori.adventure.text.Component deserialize(String text);
}
