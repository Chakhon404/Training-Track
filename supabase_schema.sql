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
  volume FLOAT NOT NULL,
  duration_sec INT DEFAULT 0
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

-- USER PROFILE TABLE
CREATE TABLE user_profile (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  weight_kg FLOAT,
  height_cm FLOAT,
  body_fat_pct FLOAT,
  goal_weight_kg FLOAT,
  goal_calories INT,
  goal_protein_g INT,
  goal_carbs_g INT,
  goal_fat_g INT,
  supplements JSONB DEFAULT '[]',
  notes TEXT,
  updated_at TIMESTAMP DEFAULT now()
);

ALTER TABLE user_profile ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow all" ON user_profile USING (true) WITH CHECK (true);

CREATE OR REPLACE FUNCTION update_user_profile_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER user_profile_updated_at
BEFORE UPDATE ON user_profile
FOR EACH ROW EXECUTE FUNCTION update_user_profile_updated_at();

-- WELLNESS TABLE
CREATE TABLE wellness (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  log_date DATE UNIQUE NOT NULL,
  sleep_start TIMESTAMP,
  sleep_end TIMESTAMP,
  sleep_duration_min INT,
  sleep_score INT,
  resting_hr INT,
  stress_avg INT,
  body_battery_start INT,
  body_battery_end INT,
  training_readiness INT,
  updated_at TIMESTAMP DEFAULT now()
);

ALTER TABLE wellness ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow all" ON wellness USING (true) WITH CHECK (true);

CREATE OR REPLACE FUNCTION update_wellness_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER wellness_updated_at
BEFORE UPDATE ON wellness
FOR EACH ROW EXECUTE FUNCTION update_wellness_updated_at();
