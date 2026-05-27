-- 后盖故障检测数据库架构

-- 存储后盖信息的表
CREATE TABLE IF NOT EXISTS back_covers (
    id VARCHAR(50) PRIMARY KEY,
    serial_number VARCHAR(100) UNIQUE NOT NULL,
    model VARCHAR(100) NOT NULL,
    manufacturing_date DATE,
    color VARCHAR(50),
    status ENUM('active', 'inactive', 'retired') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_model (model)
);

-- 存储故障记录的表
CREATE TABLE IF NOT EXISTS faults (
    id INT AUTO_INCREMENT PRIMARY KEY,
    back_cover_id VARCHAR(50) NOT NULL,
    fault_type VARCHAR(100) NOT NULL,
    severity ENUM('critical', 'high', 'medium', 'low') DEFAULT 'medium',
    description TEXT,
    detected_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    detected_by VARCHAR(100),
    status ENUM('open', 'in_progress', 'resolved', 'closed') DEFAULT 'open',
    resolution_notes TEXT,
    resolved_date DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (back_cover_id) REFERENCES back_covers(id),
    INDEX idx_back_cover_id (back_cover_id),
    INDEX idx_status (status),
    INDEX idx_severity (severity),
    INDEX idx_detected_date (detected_date)
);

-- 存储故障类型/类别的表
CREATE TABLE IF NOT EXISTS fault_categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    typical_severity ENUM('critical', 'high', 'medium', 'low'),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 跟踪故障趋势和指标的表
CREATE TABLE IF NOT EXISTS fault_metrics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    date DATE NOT NULL,
    total_back_covers INT,
    total_faults INT,
    critical_faults INT,
    high_faults INT,
    medium_faults INT,
    low_faults INT,
    resolved_faults INT,
    open_faults INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_date (date)
);

-- 插入常见故障类别
INSERT IGNORE INTO fault_categories (name, description, typical_severity) VALUES
('Crack', '后盖中的物理裂纹或破裂', 'high'),
('Scratch', '表面划痕或磨损', 'low'),
('Discoloration', '颜色褪色或变色', 'low'),
('Warping', '后盖翘曲或弯曲', 'medium'),
('Sensor Failure', '后盖上的传感器不工作', 'critical'),
('Adhesive Failure', '粘合剂层失效或分离', 'high'),
('Manufacturing Defect', '制造中存在的缺陷', 'medium');