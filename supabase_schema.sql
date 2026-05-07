CREATE TABLE training_plans (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT UNIQUE NOT NULL,
  exercises JSONB NOT NULL
);

CREATE TABLE workouts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  log_ts TIMESTAMP NOT NULL,
  plan_name TEXT NOT NULL,
  exercise TEXT NOT NULL,
  weight FLOAT NOT NULL,
  sets INTEGER NOT NULL,
  reps INTEGER NOT NULL,
  rpe FLOAT NOT NULL,
  volume FLOAT NOT NULL
);

CREATE TABLE running (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  log_ts TIMESTAMP NOT NULL,
  distance FLOAT NOT NULL,
  duration TEXT NOT NULL,
  pace TEXT NOT NULL,
  hr INTEGER NOT NULL,
  hrr INTEGER NOT NULL,
  category TEXT NOT NULL
);

CREATE TABLE nutrition (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  log_ts TIMESTAMP NOT NULL,
  calories INTEGER NOT NULL,
  protein_g INTEGER NOT NULL,
  carbs_g INTEGER NOT NULL,
  fat_g INTEGER NOT NULL,
  creatine BOOLEAN NOT NULL,
  protein_powder BOOLEAN NOT NULL,
  multivitamin BOOLEAN NOT NULL,
  omega3 BOOLEAN NOT NULL
);

CREATE TABLE weight (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  log_ts TIMESTAMP NOT NULL,
  weight FLOAT NOT NULL,
  notes TEXT
);
