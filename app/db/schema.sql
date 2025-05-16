-- FACT TABLE
CREATE TABLE IF NOT EXISTS fact_call_evaluation (
    call_id TEXT,
    company_id TEXT,
    agent_id TEXT,
    criterion TEXT,
    score TEXT,
    qa_score INTEGER,
    date TEXT,
    time TEXT
);

-- DIMENSIONS
CREATE TABLE IF NOT EXISTS dim_call (
    call_id TEXT PRIMARY KEY,
    company_id TEXT,
    duration FLOAT,
    channel TEXT,
    call_reason TEXT,
    language TEXT
);

CREATE TABLE IF NOT EXISTS dim_criterion (
    criterion TEXT PRIMARY KEY,
    category TEXT,
    weight FLOAT
);

CREATE TABLE IF NOT EXISTS dim_agent (
    agent_id TEXT PRIMARY KEY,
    team TEXT,
    shift TEXT,
    supervisor TEXT
);
