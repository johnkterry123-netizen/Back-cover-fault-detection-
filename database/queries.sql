-- 故障检测分析查询

-- 1. 基本统计
-- ==================

-- 检查总零件数和通过/失败率
SELECT 
    COUNT(*) as total_inspected,
    SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) as passed,
    SUM(CASE WHEN status = 'REJECT' THEN 1 ELSE 0 END) as rejected,
    ROUND(100.0 * SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) / COUNT(*), 2) as pass_rate_percent
FROM detections;

-- 缺陷计数分布
SELECT 
    defect_count,
    COUNT(*) as frequency,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM detections WHERE defects_found = 1), 2) as percent_of_defects
FROM detections
WHERE defects_found = 1
GROUP BY defect_count
ORDER BY defect_count;

-- 平均缺陷大小
SELECT 
    COUNT(*) as defect_instances,
    ROUND(AVG(max_defect_length_mm), 3) as avg_defect_mm,
    ROUND(MIN(max_defect_length_mm), 3) as min_defect_mm,
    ROUND(MAX(max_defect_length_mm), 3) as max_defect_mm,
    ROUND(STDDEV(max_defect_length_mm), 3) as stddev_defect_mm
FROM detections
WHERE defects_found = 1;

-- 2. 按时间分析
-- ======================

-- 按小时统计缺陷
SELECT 
    DATE(timestamp) as date,
    HOUR(timestamp) as hour,
    COUNT(*) as total_parts,
    SUM(CASE WHEN defects_found = 1 THEN 1 ELSE 0 END) as defects,
    ROUND(100.0 * SUM(CASE WHEN defects_found = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as defect_rate_percent
FROM detections
GROUP BY DATE(timestamp), HOUR(timestamp)
ORDER BY timestamp DESC;

-- 按日期统计缺陷
SELECT 
    DATE(timestamp) as date,
    COUNT(*) as total_parts,
    SUM(CASE WHEN defects_found = 1 THEN 1 ELSE 0 END) as defects,
    ROUND(100.0 * SUM(CASE WHEN defects_found = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as defect_rate_percent,
    ROUND(AVG(max_defect_length_mm), 3) as avg_defect_mm
FROM detections
GROUP BY DATE(timestamp)
ORDER BY date DESC;

-- 每日报告汇总
SELECT 
    'Daily Report' as report_type,
    CURDATE() as report_date,
    (SELECT COUNT(*) FROM detections WHERE DATE(timestamp) = CURDATE()) as parts_inspected,
    (SELECT COUNT(*) FROM detections WHERE DATE(timestamp) = CURDATE() AND defects_found = 1) as defects_found;