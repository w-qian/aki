"""TypeScript sample data for code analyzer tests."""

TYPESCRIPT_SAMPLE = {
    "app.ts": """
        import { User } from './models/user';
        
        interface AppConfig {
            port: number;
            debug: boolean;
        }
        
        const config: AppConfig = {
            port: 3000,
            debug: true
        };
        
        function startApp(config: AppConfig): void {
            console.log(`Starting app on port ${config.port}`);
        }
        
        class Application {
            private config: AppConfig;
            
            constructor(config: AppConfig) {
                this.config = config;
            }
            
            public run(): void {
                startApp(this.config);
            }
        }
        
        const app = new Application(config);
        app.run();
        """,
    "models/user.ts": """
        export interface User {
            id: number;
            name: string;
            email: string;
        }
        
        export class UserService {
            private users: User[] = [];
            
            public addUser(user: User): void {
                this.users.push(user);
            }
            
            public getUser(id: number): User | undefined {
                return this.users.find(user => user.id === id);
            }
        }
        """,
}
