#!/usr/bin/env python3
"""
Back Cover Fault Detection System
Detects scratches as small as 0.1mm on dark silicone back covers at 30 pieces/minute

The Algorithm:
1. Wait for sensor trigger (laser tripwire)
2. Capture image from camera
3. Extract phone back (ROI - Region of Interest)
4. Enhance contrast to make scratches visible
5. Compare to golden image (perfect back)
6. Measure defect size
7. Reject if defect > 0.1mm
"""

import cv2
import numpy as np
import logging
from typing import Tuple, List, Dict
from dataclasses import dataclass
import yaml
import threading
import time
from datetime import datetime
import sqlite3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fault_detection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """Result of a single back cover inspection"""
    timestamp: datetime
    defects_found: bool
    defect_count: int
    defect_locations: List[Tuple[int, int, int, int]]  # x, y, w, h
    max_defect_length_mm: float
    max_defect_length_pixels: int
    difference_image: np.ndarray
    status: str  # 'PASS' or 'REJECT'
    
    
class CameraInterface:
    """Interface for camera capture with sensor trigger"""
    
    def __init__(self, camera_id: int = 0):
        self.camera = cv2.VideoCapture(camera_id)
        self.sensor_triggered = False
        
    def configure_camera(self, config: dict):
        """Apply camera configuration"""
        cam_config = config['camera']
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, cam_config['resolution']['width'])
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_config['resolution']['height'])
        self.camera.set(cv2.CAP_PROP_FPS, cam_config['fps'])
        self.camera.set(cv2.CAP_PROP_EXPOSURE, cam_config['exposure'])
        logger.info("Camera configured")
        
    def wait_for_trigger(self, timeout_seconds: float = 10) -> bool:
        """
        STEP 1: Wait for sensor trigger (laser tripwire)
        In production, this would read from a hardware sensor/GPIO
        """
        # TODO: Replace with actual sensor interface
        # For now, simulating with keyboard input
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            if cv2.waitKey(10) & 0xFF == ord('t'):  # Press 't' to trigger
                logger.info("Sensor triggered!")
                return True
        return False
        
    def capture_image(self) -> np.ndarray:
        """STEP 1: Grab the picture"""
        ret, frame = self.camera.read()
        if not ret:
            raise RuntimeError("Failed to capture image from camera")
        return frame
        
    def release(self):
        """Release camera resources"""
        self.camera.release()
        

class ImageProcessor:
    """Core image processing pipeline"""
    
    def __init__(self, config: dict):
        self.config = config
        self.calibration = config['calibration']
        self.pixels_per_mm = self.calibration['pixels_per_mm']
        self.min_threshold_pixels = self.calibration['min_defect_threshold_pixels']
        
    def extract_roi(self, image: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
        """
        STEP 2: Find the phone in the picture (ROI Extraction)
        Converts to grayscale, finds largest rectangle, crops to it
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Find contours
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            logger.warning("No contours found in image")
            return image, (0, 0, image.shape[1], image.shape[0])
        
        # Find largest contour (should be the phone back)
        largest_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_contour)
        
        # Add padding
        padding = int(max(w, h) * 0.1)
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(image.shape[1] - x, w + 2 * padding)
        h = min(image.shape[0] - y, h + 2 * padding)
        
        roi = image[y:y+h, x:x+w]
        logger.info(f"ROI extracted: {x}, {y}, {w}, {h}")
        
        return roi, (x, y, w, h)
        
    def enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """
        STEP 3: Fix the lighting (Image Equalization)
        Stretches contrast to make scratches on dark silicone visible
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Histogram stretching: make darkest 10% pure black, brightest 10% pure white
        p_low = np.percentile(gray, 10)
        p_high = np.percentile(gray, 90)
        
        enhanced = ((gray - p_low) / (p_high - p_low) * 255).astype(np.uint8)
        enhanced = np.clip(enhanced, 0, 255)
        
        logger.info("Contrast enhanced")
        return enhanced
        
    def blur_and_subtract(self, enhanced: np.ndarray, kernel_size: int = 25) -> np.ndarray:
        """
        METHOD B: Blur & Subtract (removes silicone grain texture)
        Scratches are lines, grain is random texture
        """
        # Create blurred version (texture blurs out, scratches remain as faint lines)
        blurred = cv2.GaussianBlur(enhanced, (kernel_size, kernel_size), 0)
        
        # Subtract blurred from original
        # Scratches appear as white lines, grain cancels out
        difference = cv2.subtract(enhanced, blurred)
        
        logger.info("Blur & subtract applied")
        return difference
        
    def compare_to_golden(self, enhanced: np.ndarray, golden_image: np.ndarray) -> np.ndarray:
        """
        STEP 4: Find the scratches (Defect Detection)
        METHOD A: Perfect Image Subtraction
        """
        # Align images (handle ±5mm shift tolerance)
        aligned_golden = self._align_images(enhanced, golden_image)
        
        # Subtract: if difference > threshold, it's a defect
        difference = cv2.absdiff(enhanced, aligned_golden)
        
        logger.info("Image subtraction complete")
        return difference
        
    def _align_images(self, img1: np.ndarray, img2: np.ndarray) -> np.ndarray:
        """
        Align two images by shifting to find best match
        Allows for ±5mm movement tolerance
        """
        max_shift = self.config['image_processing']['defect_detection']['alignment_max_shift_pixels']
        best_score = float('inf')
        best_shift_x, best_shift_y = 0, 0
        
        for shift_x in range(-max_shift, max_shift + 1, 2):
            for shift_y in range(-max_shift, max_shift + 1, 2):
                # Shift img2
                M = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
                shifted = cv2.warpAffine(img2, M, (img2.shape[1], img2.shape[0]))
                
                # Calculate difference
                score = cv2.absdiff(img1, shifted).sum()
                
                if score < best_score:
                    best_score = score
                    best_shift_x = shift_x
                    best_shift_y = shift_y
        
        M = np.float32([[1, 0, best_shift_x], [0, 1, best_shift_y]])
        aligned = cv2.warpAffine(img2, M, (img2.shape[1], img2.shape[0]))
        logger.info(f"Images aligned with shift: ({best_shift_x}, {best_shift_y}) pixels")
        
        return aligned
        
    def detect_defects(self, difference: np.ndarray) -> Tuple[List[Tuple[int, int, int, int]], np.ndarray]:
        """
        Detect defects from difference image
        Applies threshold and finds contours
        """
        threshold = self.config['image_processing']['defect_detection']['pixel_difference_threshold']
        
        # Apply threshold
        _, binary = cv2.threshold(difference, threshold, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        defects = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            # Get the length (longest dimension)
            length_pixels = max(w, h)
            length_mm = length_pixels / self.pixels_per_mm
            
            # Only keep significant defects
            if length_pixels > self.min_threshold_pixels:
                defects.append((x, y, w, h, length_pixels, length_mm))
                logger.info(f"Defect found: {length_mm:.2f}mm ({length_pixels}px)")
        
        return defects, binary
        
    def measure_defects(self, defects: List[Tuple]) -> Tuple[int, float]:
        """
        STEP 5: Check the size (The 0.1mm rule)
        Returns: (defect_count, max_length_mm)
        """
        if not defects:
            return 0, 0.0
        
        defect_count = len(defects)
        max_length_mm = max(d[5] for d in defects)  # Get max length in mm
        
        logger.info(f"Defect measurement: {defect_count} defects, max size {max_length_mm:.2f}mm")
        return defect_count, max_length_mm


class FaultDatabase:
    """Log faults to database for tracking"""
    
    def __init__(self, db_path: str = "fault_database.db"):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        """Initialize database if not exists"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                defects_found BOOLEAN,
                defect_count INTEGER,
                max_defect_length_mm REAL,
                status TEXT,
                image_path TEXT,
                difference_map_path TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized")
        
    def log_detection(self, result: DetectionResult, image_path: str = None, diff_path: str = None):
        """Log detection result to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO detections 
            (timestamp, defects_found, defect_count, max_defect_length_mm, status, image_path, difference_map_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            result.timestamp,
            result.defects_found,
            result.defect_count,
            result.max_defect_length_mm,
            result.status,
            image_path,
            diff_path
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"Detection logged: {result.status}")


class RejectionController:
    """Handle rejection signal output"""
    
    def __init__(self, config: dict):
        self.config = config['output']['rejection_signal']
        # TODO: Initialize GPIO for air nozzle control
        
    def reject_part(self):
        """
        STEP 6: The output - activate air nozzle to blow off part
        """
        duration_ms = self.config['duration_ms']
        logger.info(f"REJECTION SIGNAL: Activating air nozzle for {duration_ms}ms")
        
        # TODO: Actual GPIO control
        # gpio.output(AIR_NOZZLE_PIN, HIGH)
        # time.sleep(duration_ms / 1000.0)
        # gpio.output(AIR_NOZZLE_PIN, LOW)
        
        # Simulation:
        print("🔴 AIR NOZZLE ACTIVATED - PART REJECTED")
        time.sleep(duration_ms / 1000.0)
        print("🔴 AIR NOZZLE DEACTIVATED")
        
    def pass_part(self):
        """Part passed inspection"""
        logger.info("Part passed inspection - continuing to next station")
        print("✅ PART PASSED - CONTINUE")


class FaultDetectionSystem:
    """Main system orchestrator"""
    
    def __init__(self, config_path: str = "config/camera_config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.camera = CameraInterface()
        self.camera.configure_camera(self.config)
        
        self.processor = ImageProcessor(self.config)
        self.database = FaultDatabase()
        self.rejection = RejectionController(self.config)
        
        self.golden_image = None
        self._load_golden_image()
        
    def _load_golden_image(self):
        """Load the reference golden image"""
        try:
            self.golden_image = cv2.imread('golden_image.jpg', cv2.IMREAD_GRAYSCALE)
            if self.golden_image is None:
                logger.warning("Golden image not found - using blur/subtract method instead")
            else:
                logger.info("Golden image loaded")
        except Exception as e:
            logger.error(f"Error loading golden image: {e}")
            
    def process_single_part(self) -> DetectionResult:
        """
        Process a single back cover through the entire pipeline
        THE MAIN ALGORITHM
        """
        logger.info("=" * 60)
        logger.info("Starting part inspection")
        
        # STEP 1: Wait for sensor trigger and capture image
        if not self.camera.wait_for_trigger():
            logger.warning("Timeout waiting for sensor trigger")
            return None
            
        image = self.camera.capture_image()
        logger.info("Image captured")
        
        # STEP 2: Extract ROI (find the phone rectangle)
        roi, roi_coords = self.processor.extract_roi(image)
        
        # STEP 3: Enhance contrast to make scratches visible
        enhanced = self.processor.enhance_contrast(roi)
        
        # STEP 4: Find scratches (using golden image if available, else blur method)
        if self.golden_image is not None:
            difference = self.processor.compare_to_golden(enhanced, self.golden_image)
        else:
            difference = self.processor.blur_and_subtract(enhanced)
        
        # STEP 4 (continued): Detect defects from difference image
        defects, binary = self.processor.detect_defects(difference)
        
        # STEP 5: Measure defects and check if > 0.1mm
        defect_count, max_length_mm = self.processor.measure_defects(defects)
        
        # STEP 6: Make decision
        min_threshold = self.config['calibration']['min_defect_threshold_mm']
        defects_found = (defect_count > 0 and max_length_mm >= min_threshold)
        
        if defects_found:
            status = "REJECT"
            self.rejection.reject_part()
        else:
            status = "PASS"
            self.rejection.pass_part()
        
        result = DetectionResult(
            timestamp=datetime.now(),
            defects_found=defects_found,
            defect_count=defect_count,
            defect_locations=[(d[0], d[1], d[2], d[3]) for d in defects],
            max_defect_length_mm=max_length_mm,
            max_defect_length_pixels=max([d[4] for d in defects]) if defects else 0,
            difference_image=difference,
            status=status
        )
        
        # Log to database
        self.database.log_detection(result)
        
        logger.info(f"Inspection complete: {status}")
        logger.info("=" * 60)
        
        return result
        
    def run_production_line(self):
        """
        Main loop: Run continuous inspection at 30 pieces/minute
        """
        logger.info("Starting production line inspection")
        print("\n⏳ Waiting for parts... Press 't' to simulate sensor trigger\n")
        
        try:
            while True:
                result = self.process_single_part()
                if result is None:
                    continue
                    
                # Small delay between parts (30 pieces/min = 2 seconds per piece)
                time.sleep(0.5)
                
        except KeyboardInterrupt:
            logger.info("Production line stopped by user")
        finally:
            self.shutdown()
            
    def shutdown(self):
        """Clean shutdown"""
        self.camera.release()
        cv2.destroyAllWindows()
        logger.info("System shutdown complete")


if __name__ == "__main__":
    system = FaultDetectionSystem("config/camera_config.yaml")
    system.run_production_line()