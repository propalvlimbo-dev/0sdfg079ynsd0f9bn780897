import com.ilyapurtov.utils.ReflectionUtil;
import org.bukkit.entity.Player;
public class TitleTest {
  static final class FakePlayer implements Player {
    String title, subtitle; int fi, stay, fo, calls;
    public void sendTitle(String t, String s, int f, int st, int o) { title=t; subtitle=s; fi=f; stay=st; fo=o; calls++; }
  }
  public static void main(String[] args) {
    FakePlayer p = new FakePlayer();
    ReflectionUtil.sendTitle(p, "§aПривет", "§bRTP", 7, 25, 9);
    if (p.calls != 1 || !"§aПривет".equals(p.title) || !"§bRTP".equals(p.subtitle) || p.fi != 7 || p.stay != 25 || p.fo != 9) throw new AssertionError();
    ReflectionUtil.sendTitle(p, null, "test", 0, 20, 0);
    if (p.calls != 2 || p.title != null || !"test".equals(p.subtitle)) throw new AssertionError();
    System.out.println("title mock passed");
  }
}
