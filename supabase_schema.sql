-- ============================================================
--  TRAINING TRACK — Supabase Schema
--  รัน script นี้ใน Supabase SQL Editor ครั้งเดียวตามลำดับ Step
-- ============================================================


-- ============================================================
--  STEP 1 : Extensions
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- ============================================================
--  STEP 2 : Shared Utility Functions
--  สร้าง function กลางที่ใช้ร่วมกันก่อน เพื่อให้ Trigger ใน
--  Step 5-6 เรียกใช้ได้ทันที
-- ============================================================

-- อัปเดต updated_at อัตโนมัติทุกครั้งที่มีการ UPDATE
CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ซิงค์ weight_kg และ body_fat_pct จาก weight → user_profile อัตโนมัติ
CREATE OR REPLACE FUNCTION fn_sync_health_stats()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE user_profile
  SET
    weight_kg     = NEW.weight,
    body_fat_pct  = COALESCE(NEW.body_fat_pct, body_fat_pct),
    updated_at    = now()
  WHERE id = (SELECT id FROM user_profile ORDER BY updated_at DESC LIMIT 1);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ============================================================
--  STEP 3 : Tables
--  สร้างทุก column ใน CREATE TABLE ทันที ไม่มี ALTER TABLE
-- ============================================================

-- ------------------------------------------------------------
--  3-A  training_plans
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS training_plans (
  id        UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
  name      TEXT    UNIQUE NOT NULL,
  exercises JSONB   NOT NULL
);

-- ------------------------------------------------------------
--  3-B  workouts
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workouts (
  id           UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
  log_ts       TIMESTAMP NOT NULL,
  plan_name    TEXT      NOT NULL,
  exercise     TEXT      NOT NULL,
  weight       FLOAT     NOT NULL,
  sets         INTEGER   NOT NULL,
  reps         INTEGER   NOT NULL,
  rpe          FLOAT     NOT NULL,
  volume       FLOAT     NOT NULL,
  duration_sec INT       DEFAULT 0
);

-- ------------------------------------------------------------
--  3-C  running
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS running (
  id       UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
  log_ts   TIMESTAMP NOT NULL,
  distance FLOAT     NOT NULL,
  duration TEXT      NOT NULL,
  pace     TEXT      NOT NULL,
  hr       INTEGER   NOT NULL,
  hrr      INTEGER   NOT NULL,
  category TEXT      NOT NULL
);

-- ------------------------------------------------------------
--  3-D  nutrition  (รวมทุก supplement column ไว้ตั้งแต่แรก)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS nutrition (
  id             UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
  log_ts         TIMESTAMP NOT NULL,
  food_name      TEXT,
  calories       INTEGER   NOT NULL,
  protein_g      INTEGER   NOT NULL,
  carbs_g        INTEGER   NOT NULL,
  fat_g          INTEGER   NOT NULL,
  meal_score     INT       DEFAULT NULL,

  -- Core supplements
  creatine       BOOLEAN   NOT NULL DEFAULT FALSE,
  protein_powder BOOLEAN   NOT NULL DEFAULT FALSE,
  multivitamin   BOOLEAN   NOT NULL DEFAULT FALSE,
  omega3         BOOLEAN   NOT NULL DEFAULT FALSE,

  -- Extended supplements
  fish_oil       BOOLEAN   DEFAULT FALSE,
  astaxanthin    BOOLEAN   DEFAULT FALSE,
  magnesium      BOOLEAN   DEFAULT FALSE,
  zinc           BOOLEAN   DEFAULT FALSE,
  vitamin_d3     BOOLEAN   DEFAULT FALSE,
  vitamin_c      BOOLEAN   DEFAULT FALSE,
  bcaa_eaa       BOOLEAN   DEFAULT FALSE,
  pre_workout    BOOLEAN   DEFAULT FALSE,
  caffeine       BOOLEAN   DEFAULT FALSE,
  probiotics     BOOLEAN   DEFAULT FALSE,
  b_complex      BOOLEAN   DEFAULT FALSE
);

-- ------------------------------------------------------------
--  3-E  weight
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS weight (
  id           UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
  log_ts       TIMESTAMP NOT NULL,
  weight       FLOAT     NOT NULL,
  body_fat_pct FLOAT,
  notes        TEXT
);

-- ------------------------------------------------------------
--  3-F  drafts  (auto-save สำหรับ form ต่างๆ)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS drafts (
  id         UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
  form_key   TEXT    UNIQUE NOT NULL,
  data       JSONB   NOT NULL,
  updated_at TIMESTAMP DEFAULT now()
);

-- ------------------------------------------------------------
--  3-G  user_profile  (รวม default_supplements ไว้ตั้งแต่แรก)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_profile (
  id                   UUID  PRIMARY KEY DEFAULT uuid_generate_v4(),
  weight_kg            FLOAT,
  height_cm            FLOAT,
  body_fat_pct         FLOAT,
  goal_weight_kg       FLOAT,
  goal_calories        INT,
  goal_protein_g       INT,
  goal_carbs_g         INT,
  goal_fat_g           INT,
  supplements          JSONB     DEFAULT '[]',
  default_supplements  JSONB     DEFAULT '[]',
  notes                TEXT,
  updated_at           TIMESTAMP DEFAULT now()
);

-- ------------------------------------------------------------
--  3-H  wellness
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wellness (
  id                  UUID  PRIMARY KEY DEFAULT uuid_generate_v4(),
  log_date            DATE  UNIQUE NOT NULL,
  sleep_start         TIMESTAMP,
  sleep_end           TIMESTAMP,
  sleep_duration_min  INT,
  sleep_score         INT,
  resting_hr          INT,
  stress_avg          INT,
  body_battery_start  INT,
  body_battery_end    INT,
  training_readiness  INT,
  updated_at          TIMESTAMP DEFAULT now()
);


-- ============================================================
--  STEP 4 : Row Level Security (RLS)
--  เปิด RLS และสร้าง policy สำหรับ table ที่ต้องการ
-- ============================================================

ALTER TABLE drafts       ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE wellness     ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow all" ON drafts       USING (true) WITH CHECK (true);
CREATE POLICY "allow all" ON user_profile USING (true) WITH CHECK (true);
CREATE POLICY "allow all" ON wellness     USING (true) WITH CHECK (true);


-- ============================================================
--  STEP 5 : updated_at Triggers
--  ใช้ fn_set_updated_at() จาก Step 2 ร่วมกันทุก table
-- ============================================================

CREATE TRIGGER tr_drafts_updated_at
BEFORE UPDATE ON drafts
FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER tr_user_profile_updated_at
BEFORE UPDATE ON user_profile
FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER tr_wellness_updated_at
BEFORE UPDATE ON wellness
FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();


-- ============================================================
--  STEP 6 : Business Logic Triggers
-- ============================================================

-- tr_sync_health_stats
-- ทุกครั้งที่บันทึกน้ำหนักใหม่ลงใน weight table
-- จะอัปเดต weight_kg และ body_fat_pct ใน user_profile โดยอัตโนมัติ
-- หมายเหตุ: body_fat_pct ใช้ COALESCE เพื่อไม่ทับค่าเดิมถ้า entry ใหม่ไม่มีข้อมูล

CREATE TRIGGER tr_sync_health_stats
AFTER INSERT OR UPDATE ON weight
FOR EACH ROW EXECUTE FUNCTION fn_sync_health_stats();

-- ============================================================
--  STEP 7 : Performance Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_workouts_log_ts   ON workouts(log_ts);
CREATE INDEX IF NOT EXISTS idx_running_log_ts     ON running(log_ts);
CREATE INDEX IF NOT EXISTS idx_nutrition_log_ts   ON nutrition(log_ts);
CREATE INDEX IF NOT EXISTS idx_weight_log_ts      ON weight(log_ts);
CREATE INDEX IF NOT EXISTS idx_wellness_log_date  ON wellness(log_date);

-- ============================================================
--  STEP 8 : Per-Set Logging Migration
-- ============================================================
ALTER TABLE workouts ADD COLUMN IF NOT EXISTS set_number INT DEFAULT 1;