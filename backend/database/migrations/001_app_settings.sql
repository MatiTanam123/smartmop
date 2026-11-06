-- SmartMop extra application/network settings.
-- Run this after schema_base.sql when the original nine-table schema already exists.
CREATE TABLE IF NOT EXISTS app_settings (
    setting_id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (setting_id = 1),
    image_size INTEGER NOT NULL DEFAULT 640 CHECK (image_size IN (320, 416, 640, 960, 1280)),
    show_bbox BOOLEAN NOT NULL DEFAULT TRUE,
    save_detection_images BOOLEAN NOT NULL DEFAULT TRUE,
    low_battery_threshold NUMERIC(5,2) NOT NULL DEFAULT 20 CHECK (low_battery_threshold BETWEEN 0 AND 100),
    low_soap_threshold NUMERIC(5,2) NOT NULL DEFAULT 15 CHECK (low_soap_threshold BETWEEN 0 AND 100),
    stop_on_low_battery BOOLEAN NOT NULL DEFAULT TRUE,
    wifi_ssid VARCHAR(100),
    server_host VARCHAR(255),
    api_port INTEGER NOT NULL DEFAULT 5000 CHECK (api_port BETWEEN 1 AND 65535),
    api_prefix VARCHAR(80) NOT NULL DEFAULT '/api',
    camera_ip INET,
    controller_ip INET,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO app_settings (setting_id)
VALUES (1)
ON CONFLICT (setting_id) DO NOTHING;
