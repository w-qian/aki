"""Java sample data for code analyzer tests."""

JAVA_SAMPLE = {
    "Main.java": """
        public class Main {
            private String name;
            private int age;
            
            public Main(String name, int age) {
                this.name = name;
                this.age = age;
            }
            
            public String getName() {
                return name;
            }
            
            public int getAge() {
                return age;
            }
            
            public static void main(String[] args) {
                System.out.println("Hello World");
            }
        }
        """,
    "interfaces/Runnable.java": """
        package interfaces;
        
        public interface Runnable {
            void run();
        }
        """,
    "implementations/Task.java": """
        package implementations;
        
        import interfaces.Runnable;
        
        public class Task implements Runnable {
            @Override
            public void run() {
                System.out.println("Running task");
            }
        }
        """,
}
