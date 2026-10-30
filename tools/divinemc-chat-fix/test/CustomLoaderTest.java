import java.net.URLClassLoader;
import java.nio.file.Path;
public class CustomLoaderTest {
 public static void main(String[] args)throws Exception {
  try(URLClassLoader serverLoader=new URLClassLoader(new java.net.URL[]{Path.of(args[0]).toUri().toURL()},null)){
   Class<?> boot=Class.forName("BootstrapTest",true,serverLoader);
   boot.getMethod("main",String[].class).invoke(null,(Object)new String[0]);
  }
 }
}
