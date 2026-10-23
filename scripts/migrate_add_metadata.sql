-- Migration: Add extended metadata columns to tracks table
-- Safe to execute multiple times (uses ADD COLUMN IF NOT EXISTS)

ALTER TABLE tracks ADD COLUMN IF NOT EXISTS album VARCHAR(200);
ALTER TABLE tracks ADD COLUMN IF NOT EXISTS genre VARCHAR(200);
ALTER TABLE tracks ADD COLUMN IF NOT EXISTS release_year INTEGER;
ALTER TABLE tracks ADD COLUMN IF NOT EXISTS isrc VARCHAR(200);
ALTER TABLE tracks ADD COLUMN IF NOT EXISTS license_type VARCHAR(200);
ALTER TABLE tracks ADD COLUMN IF NOT EXISTS description TEXT;
