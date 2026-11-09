package wtf.n1zamu.utils;

import java.util.regex.Pattern;
import wtf.n1zamu.NClans;

public class ValidatorUtil {

    private static final Pattern STRIP_ALL_COLORS = Pattern.compile(
            "(?i)(&#[0-9a-f]{6}|\u00a7#[0-9a-f]{6}|<#[0-9a-f]{6}>|[&\u00a7]x([&\u00a7][0-9a-f]){6}|(?<![&\u00a7<#0-9a-f])#[0-9a-f]{6}|[&\u00a7][0-9a-fk-orx])"
    );

    public static String removeAllColors(String input) {
        if (input == null || input.isEmpty()) {
            return "";
        }
        return STRIP_ALL_COLORS.matcher(input).replaceAll("");
    }

    /**
     * Strictly forbids ANY player-supplied color, HEX, or formatting codes in clan names.
     * Clan colors are determined exclusively by clan level progression (levels.yml).
     */
    public static String getValidClanName(String input) {
        if (input == null || input.isEmpty()) {
            return null;
        }
        if (input.indexOf('&') >= 0 || input.indexOf('\u00a7') >= 0 || input.indexOf('#') >= 0
                || input.indexOf('<') >= 0 || input.indexOf('>') >= 0) {
            return null;
        }
        String stripped = removeAllColors(input);
        if (stripped.isEmpty() || !stripped.equals(input)) {
            return null;
        }
        NClans instance = NClans.getInstance();
        if (instance != null && instance.getConfig() != null) {
            String allowed = instance.getConfig().getString("nameAllowedChars", "");
            if (allowed != null && !allowed.isEmpty()) {
                for (int i = 0; i < stripped.length(); i++) {
                    if (allowed.indexOf(stripped.charAt(i)) < 0) {
                        return null;
                    }
                }
            }
        }
        return stripped;
    }
}
