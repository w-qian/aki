-- Enable pgcrypto extension for UUID generation
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- User table
CREATE TABLE IF NOT EXISTS "User" (
    "id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "metadata" JSONB NOT NULL,
    "identifier" TEXT NOT NULL,
    CONSTRAINT "User_identifier_key" UNIQUE ("identifier")
);
CREATE INDEX IF NOT EXISTS "User_identifier_idx" ON "User"("identifier");

-- Thread table
CREATE TABLE IF NOT EXISTS "Thread" (
    "id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "deletedAt" TIMESTAMP,
    "name" TEXT,
    "metadata" JSONB NOT NULL,
    "tags" TEXT[] DEFAULT '{}',
    "userId" UUID,
    CONSTRAINT "Thread_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id")
);
CREATE INDEX IF NOT EXISTS "Thread_createdAt_idx" ON "Thread"("createdAt");
CREATE INDEX IF NOT EXISTS "Thread_name_idx" ON "Thread"("name");

-- Step table (with TEXT type instead of ENUM)
CREATE TABLE IF NOT EXISTS "Step" (
    "id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "parentId" UUID,
    "threadId" UUID,
    "input" TEXT,
    "metadata" JSONB NOT NULL,
    "name" TEXT,
    "output" TEXT,
    "type" TEXT NOT NULL,  -- Changed from StepType ENUM to TEXT
    "showInput" TEXT DEFAULT 'json',
    "isError" BOOLEAN DEFAULT FALSE,
    "startTime" TIMESTAMP NOT NULL,
    "endTime" TIMESTAMP NOT NULL,
    CONSTRAINT "Step_parentId_fkey" FOREIGN KEY ("parentId") REFERENCES "Step"("id") ON DELETE CASCADE,
    CONSTRAINT "Step_threadId_fkey" FOREIGN KEY ("threadId") REFERENCES "Thread"("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "Step_createdAt_idx" ON "Step"("createdAt");
CREATE INDEX IF NOT EXISTS "Step_endTime_idx" ON "Step"("endTime");
CREATE INDEX IF NOT EXISTS "Step_parentId_idx" ON "Step"("parentId");
CREATE INDEX IF NOT EXISTS "Step_startTime_idx" ON "Step"("startTime");
CREATE INDEX IF NOT EXISTS "Step_threadId_idx" ON "Step"("threadId");
CREATE INDEX IF NOT EXISTS "Step_type_idx" ON "Step"("type");  -- Index still works with TEXT
CREATE INDEX IF NOT EXISTS "Step_name_idx" ON "Step"("name");
CREATE INDEX IF NOT EXISTS "Step_threadId_startTime_endTime_idx" ON "Step"("threadId", "startTime", "endTime");

-- Element table
CREATE TABLE IF NOT EXISTS "Element" (
    "id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "threadId" UUID,
    "stepId" UUID NOT NULL,
    "metadata" JSONB NOT NULL,
    "mime" TEXT,
    "name" TEXT NOT NULL,
    "objectKey" TEXT,
    "url" TEXT,
    "chainlitKey" TEXT,
    "display" TEXT,
    "size" TEXT,
    "language" TEXT,
    "page" INTEGER,
    "props" JSONB,
    CONSTRAINT "Element_stepId_fkey" FOREIGN KEY ("stepId") REFERENCES "Step"("id") ON DELETE CASCADE,
    CONSTRAINT "Element_threadId_fkey" FOREIGN KEY ("threadId") REFERENCES "Thread"("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "Element_stepId_idx" ON "Element"("stepId");
CREATE INDEX IF NOT EXISTS "Element_threadId_idx" ON "Element"("threadId");

-- Feedback table
CREATE TABLE IF NOT EXISTS "Feedback" (
    "id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "stepId" UUID,
    "name" TEXT NOT NULL,
    "value" FLOAT NOT NULL,
    "comment" TEXT,
    CONSTRAINT "Feedback_stepId_fkey" FOREIGN KEY ("stepId") REFERENCES "Step"("id")
);
CREATE INDEX IF NOT EXISTS "Feedback_createdAt_idx" ON "Feedback"("createdAt");
CREATE INDEX IF NOT EXISTS "Feedback_name_idx" ON "Feedback"("name");
CREATE INDEX IF NOT EXISTS "Feedback_stepId_idx" ON "Feedback"("stepId");
CREATE INDEX IF NOT EXISTS "Feedback_value_idx" ON "Feedback"("value");
CREATE INDEX IF NOT EXISTS "Feedback_name_value_idx" ON "Feedback"("name", "value");

-- State table
CREATE TABLE IF NOT EXISTS "State" (
    "threadId" TEXT PRIMARY KEY,
    "state" JSONB NOT NULL,
    "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS "State_updatedAt_idx" ON "State"("updatedAt");