# 实现指南：手机后壳故障检测系统

完整的分步部署和操作故障检测系统的指南。

## 第1阶段：设置（1-2小时）

### 1.1 安装软件
```bash
# 克隆仓库
git clone <repository-url>
cd Back-cover-fault-detection-

# 安装Python依赖项
pip install -r requirements.txt

# 创建所需目录
mkdir -p database logs defect_logs
```

### 1.2 硬件检查清单
- [ ] 工业摄像机（2048x2048分辨率，≥60 FPS）
- [ ] 镜头（固定焦距，与距离匹配）
- [ ] 穹顶灯（45°角）
- [ ] 环灯（25°角，可调强度）
- [ ] 激光断点传感器
- [ ] 气喷嘴（80 PSI可调）
- [ ] 传送带（30件/分钟）
- [ ] 工业PC/树莓派4

### 1.3 网络设置
- [ ] 将摄像机连接到PC（USB 3.0或GigE）
- [ ] 配置摄像机IP地址（如果是GigE）
- [ ] 测试摄像机：`python -c "import cv2; cap = cv2.VideoCapture(0); print(cap.isOpened())"`

---

## 第2阶段：校准（2-4小时）

### 2.1 物理设置
```
开始校准前：
1. 在传送带上方安装摄像机
2. 将光线角度设置为45°（穹顶）和25°（环形）
3. 调整光线强度以在划痕上产生白色阴影
4. 位置激光传感器以在零件到达时触发
5. 在出口安装气喷嘴
```

### 2.2 像素-毫米校准

**目标：** 建立转换，使1像素= 0.05mm（允许0.1mm检测）

```bash
python src/calibration_tool.py
# 选择："1. 校准像素-毫米转换"
```

**说明：**
1. 在摄像机下放置标尺（毫米标记可见）
2. 使用精确的照明（与生产相同）
3. 测量标尺上10mm之间的像素距离
4. 记录：pixels_per_mm = pixel_distance / 10

**例子：**
```
测量：10mm标尺= 200像素
计算：200像素/ 10mm = 20像素/mm
1像素= 0.05mm
0.1mm阈值= 2像素
```

**更新配置：**
```yaml
# config/camera_config.yaml
calibration:
  pixels_per_mm: 20  # YOUR_VALUE
  min_defect_threshold_pixels: 2  # 0.1mm
```

### 2.3 创建黄金图像（完美参考）

```bash
python src/calibration_tool.py
# 选择："2. 创建黄金参考图像"
```

**说明：**
1. 获得完美的无缺陷后壳
2. 在摄像机下放置标准光线
3. 系统捕获5帧并使用最清晰的
4. 保存为：`golden_image.jpg`

**关键：** 此图像代表"完美"- 任何偏差都将被标记为缺陷。

### 2.4 测试图像处理设置

```bash
python src/calibration_tool.py
# 选择："3. 测试对比度增强"
```

使用滑块优化：
- **百分位低：** 当前10（最暗10%→纯黑）
- **百分位高：** 当前90（最亮10%→纯白）

如需更新：
```yaml
image_processing:
  contrast_enhancement:
    percentile_low: 10  # 如果划痕不可见则调整
    percentile_high: 90
```

### 2.5 测试模糊内核大小（晶粒去除）

```bash
python src/calibration_tool.py
# 选择："4. 测试模糊内核大小"
```

**目标：** 去除硅胶晶粒纹理同时保留划痕线

- 更大的内核=更多晶粒去除
- 太大=模糊划痕
- 典型范围：21-35

如需更新：
```yaml
image_processing:
  blur_and_subtract:
    blur_kernel_size: 25  # 如果晶粒未去除则调整
```

### 2.6 测试检测阈值

```bash
python src/calibration_tool.py
# 选择："5. 测试检测阈值"
```

**目标：** 检测划痕而不产生灰尘/变化的误检

- 较低值=更敏感（捕获微小划痕，更多误检）
- 较高值=不太敏感（漏检小划痕，较少误检）
- 平衡是关键

典型范围：30-80

如需更新：
```yaml
image_processing:
  defect_detection:
    pixel_difference_threshold: 50  # 根据误检率调整
```

---

## 第3阶段：测试与验证（2-3小时）

### 3.1 实验室测试

```bash
# 运行检测系统
python src/main_detection.py
```

**测试用例：**
1. **完美后壳** - 按't'，应显示：✅ 通过
2. **故意划痕** - 用标记笔创建0.15mm线，应显示：🔴 拒收
3. **灰尘粒子** - 小灰尘，应显示：✅ 通过（忽略<0.1mm）
4. **多个缺陷** - 多条划痕，应显示：🔴 拒收

### 3.2 性能测试

测量：
- **FPS：** 应以≥30件/分钟处理
- **准确度：** 测试100个零件，记录误检和漏检
- **误检率：** 应<1%

```bash
# 检查处理速度
# 应在<2秒内完成1个零件
```

### 3.3 传感器集成测试

修改 `src/main_detection.py` 以读取实际传感器：
```python
def wait_for_trigger(self):
    # 替换为实际GPIO
    while not GPIO.input(SENSOR_PIN):
        pass
    return True
```

在30件/分钟的实时传送带上测试。

---

## 第4阶段：生产部署

### 4.1 硬件集成

```python
# src/main_detection.py - 修改拒收信号
def reject_part(self):
    GPIO.output(AIR_NOZZLE_PIN, HIGH)
    time.sleep(0.5)  # 500ms脉冲
    GPIO.output(AIR_NOZZLE_PIN, LOW)
```

### 4.2 启动系统

```bash
# 作为后台进程运行
nohup python src/main_detection.py > production.log 2>&1 &

# 监视日志
tail -f production.log
```

### 4.3 数据库监视

```bash
# 检查系统状态
sqlite3 fault_database.db
```

```sql
-- 系统是否运行？
SELECT MAX(timestamp) as last_inspection,
       TIMESTAMPDIFF(MINUTE, MAX(timestamp), NOW()) as minutes_ago
FROM detections;

-- 今天的缺陷率
SELECT COUNT(*) as total,
       SUM(CASE WHEN defects_found = 1 THEN 1 ELSE 0 END) as defects,
       ROUND(100.0 * SUM(CASE WHEN defects_found = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as rate_percent
FROM detections WHERE DATE(timestamp) = CURDATE();
```

---

## 第5阶段：持续运营

### 每日检查清单
- [ ] 验证系统正在运行：`tail production.log`
- [ ] 检查缺陷率：查询数据库
- [ ] 检查摄像机镜头是否脏污
- [ ] 验证光线一致性
- [ ] 检查异常缺陷（有规律？）

### 每周
- [ ] 审查误检事件
- [ ] 检查气喷嘴压力（80 PSI）
- [ ] 验证传感器触发（清洁激光镜头）
- [ ] 备份数据库

### 每月
- [ ] 重新运行完整校准
- [ ] 更新黄金图像（使用新的完美零件）
- [ ] 审查缺陷趋势
- [ ] 彻底清洁摄像机光学元件
- [ ] 检查软件日志是否有错误

### 每季度
- [ ] 深度传感器/摄像机清洁
- [ ] 如果光线改变则重新校准
- [ ] 审查和分析缺陷模式
- [ ] 更新文档

---

## 成功检查清单

- [ ] 校准完成并验证
- [ ] 黄金图像已捕获（真的是完美零件）
- [ ] 系统检测到故意划痕
- [ ] 系统忽略灰尘（<0.1mm）
- [ ] 误检率<1%
- [ ] 处理速度≥30件/分钟
- [ ] 数据库记录工作
- [ ] 气喷嘴拒收信号工作
- [ ] 传感器触发集成完成
- [ ] 监控/告警设置
- [ ] 员工接受培训
- [ ] 备份程序已记录
- [ ] 维护计划已建立

---

## 支持

如有问题，请参阅上面的故障排除指南或提交GitHub问题。