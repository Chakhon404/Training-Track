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

-- Drafts table for auto-save
CREATE TABLE drafts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  form_key TEXT UNIQUE NOT NULL,
  data JSONB NOT NULL,
  updated_at TIMESTAMP DEFAULT now()
);

-- Enable RLS
ALTER TABLE drafts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow all" ON drafts USING (true) WITH CHECK (true);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER drafts_updated_at
BEFORE UPDATE ON drafts
FOR EACH ROW EXECUTE FUNCTION update_updated_at();
