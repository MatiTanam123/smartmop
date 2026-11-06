-- Jalankan pada database smartmop_db untuk memeriksa hasil instalasi.
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;

SELECT 'devices' AS table_name, COUNT(*) AS total_rows FROM devices
UNION ALL SELECT 'detections', COUNT(*) FROM detections
UNION ALL SELECT 'cleaning_sessions', COUNT(*) FROM cleaning_sessions
UNION ALL SELECT 'robot_commands', COUNT(*) FROM robot_commands
UNION ALL SELECT 'activity_logs', COUNT(*) FROM activity_logs
ORDER BY table_name;

SELECT device_code, device_type, device_name, last_seen_at
FROM devices ORDER BY device_id;

SELECT * FROM v_device_connection_status ORDER BY device_id;
