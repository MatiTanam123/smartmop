-- Add support for the controller's existing float-switch telemetry payload.
-- Run once in Supabase SQL Editor after the original SMARTMOP schema.
ALTER TABLE device_telemetry
    ADD COLUMN IF NOT EXISTS soap_available BOOLEAN;
