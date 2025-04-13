CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    identifier TEXT NOT NULL UNIQUE,
    metadata TEXT NOT NULL DEFAULT '{}',
    createdAt TEXT
);
CREATE INDEX IF NOT EXISTS users_identifier_idx ON users(identifier);
CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    createdAt TEXT,
    name TEXT,
    userId TEXT,
    userIdentifier TEXT,
    tags TEXT DEFAULT '[]',
    metadata TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (userId) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS threads_createdAt_idx ON threads(createdAt);
CREATE INDEX IF NOT EXISTS threads_name_idx ON threads(name);
CREATE TABLE IF NOT EXISTS steps (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    threadId TEXT NOT NULL,
    parentId TEXT,
    streaming BOOLEAN NOT NULL DEFAULT 0,
    waitForAnswer BOOLEAN DEFAULT 0,
    isError BOOLEAN DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    tags TEXT DEFAULT '[]',
    input TEXT,
    output TEXT,
    command TEXT,
    createdAt TEXT,
    start TEXT,
    end TEXT,
    generation TEXT DEFAULT '{}',
    showInput TEXT,
    language TEXT,
    indent INTEGER,
    defaultOpen BOOLEAN DEFAULT 0,
    FOREIGN KEY (threadId) REFERENCES threads(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS steps_createdAt_idx ON steps(createdAt);
CREATE INDEX IF NOT EXISTS steps_end_idx ON steps(end);
CREATE INDEX IF NOT EXISTS steps_parentId_idx ON steps(parentId);
CREATE INDEX IF NOT EXISTS steps_start_idx ON steps(start);
CREATE INDEX IF NOT EXISTS steps_threadId_idx ON steps(threadId);
CREATE INDEX IF NOT EXISTS steps_type_idx ON steps(type);
CREATE INDEX IF NOT EXISTS steps_name_idx ON steps(name);
CREATE INDEX IF NOT EXISTS steps_threadId_start_end_idx ON steps(threadId, start, end);
CREATE TABLE IF NOT EXISTS elements (
    id TEXT PRIMARY KEY,
    threadId TEXT,
    type TEXT,
    url TEXT,
    chainlitKey TEXT,
    name TEXT NOT NULL,
    display TEXT,
    objectKey TEXT,
    size TEXT,
    page INTEGER,
    language TEXT,
    forId TEXT,
    mime TEXT,
    props TEXT DEFAULT '{}',
    FOREIGN KEY (threadId) REFERENCES threads(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS elements_forId_idx ON elements(forId);
CREATE INDEX IF NOT EXISTS elements_threadId_idx ON elements(threadId);
CREATE TABLE IF NOT EXISTS feedbacks (
    id TEXT PRIMARY KEY,
    forId TEXT NOT NULL,
    threadId TEXT NOT NULL,
    value INTEGER NOT NULL,
    comment TEXT
);
CREATE INDEX IF NOT EXISTS feedbacks_value_idx ON feedbacks(value);
CREATE INDEX IF NOT EXISTS feedbacks_forId_idx ON feedbacks(forId);
CREATE TABLE IF NOT EXISTS State (
    threadId TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
