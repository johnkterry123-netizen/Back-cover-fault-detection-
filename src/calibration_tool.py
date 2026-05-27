#!/usr/bin/env python3
"""
Calibration Tool for Back Cover Fault Detection System

This tool helps you:
1. Calibrate the pixel-to-mm conversion (for 0.1mm detection)
2. Create a golden image (reference perfect back cover)
3. Test image processing settings
"""

import cv2
import numpy as np
import yaml
import argparse
from typing import Tuple


class CalibrationTool:
    """Interactive calibration for the detection system"""
    
    def __init__(self, config_path: str = "config/camera_config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.camera = cv2.VideoCapture(0)
        
    def calibrate_pixels_per_mm(self) -> float:
        """
        Calibrate pixel-to-mm conversion
        
        Instructions:
        1. Place a ruler (marked in mm) under your camera
        2. Align with the lighting setup
        3. Measure pixel distance between two known mm positions
        """
        print("\n" + "="*60)
        print("CALIBRATION: Pixel-to-MM Conversion")
        print("="*60)
        print("\nInstructions:")
        print("1. Place a ruler (with mm marks) under the camera")
        print("2. Press SPACE to capture image")
        print("3. Click two points 10mm apart on the ruler")
        print("4. The system will calculate pixels_per_mm\n")
        
        # Capture reference image
        print("Capturing calibration image...")
        ret, frame = self.camera.read()
        if not ret:
            print("ERROR: Could not capture image")
            return None
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        enhanced = self._enhance_contrast(gray)
        
        # Display for user to click points
        points = []
        def click_event(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                points.append((x, y))
                cv2.circle(enhanced, (x, y), 5, 0, -1)
                cv2.imshow('Calibration Image', enhanced)
                if len(points) == 2:
                    print(f"Points marked: {points}")
        
        cv2.imshow('Calibration Image', enhanced)
        cv2.setMouseCallback('Calibration Image', click_event)
        print("Click two points exactly 10mm apart: ")
        
        while len(points) < 2:
            if cv2.waitKey(1) & 0xFF == ord('q'):
                return None
        
        cv2.destroyAllWindows()
        
        # Calculate pixels per mm
        pixel_distance = np.sqrt(
            (points[1][0] - points[0][0])**2 + 
            (points[1][1] - points[0][1])**2
        )
        mm_distance = 10.0  # We measured 10mm
        pixels_per_mm = pixel_distance / mm_distance
        
        print(f"\n✓ Calibration Complete!")
        print(f"  Pixel distance: {pixel_distance:.2f} pixels")
        print(f"  MM distance: {mm_distance}mm")
        print(f"  Pixels per MM: {pixels_per_mm:.2f}")
        print(f"  1 pixel = {1/pixels_per_mm:.4f}mm")
        print(f"\n  Update your config:")
        print(f"  calibration:")
        print(f"    pixels_per_mm: {pixels_per_mm:.2f}")
        
        # Ask if user wants to save
        response = input("\nSave this calibration value? (y/n): ")
        if response.lower() == 'y':
            self._save_calibration_value(pixels_per_mm)
        
        return pixels_per_mm
    
    def create_golden_image(self) -> bool:
        """
        Create a reference image of a PERFECT back cover
        
        Instructions:
        1. Get a perfect, unmarked back cover
        2. Place it under the camera with proper lighting
        3. The system will capture and save it as golden_image.jpg
        """
        print("\n" + "="*60)
        print("CREATE GOLDEN IMAGE (Reference Perfect Back Cover)")
        print("="*60)
        print("\nInstructions:")
        print("1. Get a perfect, unmarked back cover")
        print("2. Place it under the camera with standard lighting")
        print("3. Ensure consistent lighting (same as production)")
        print("4. Press SPACE when ready to capture\n")
        
        input("Press ENTER when ready to capture golden image: ")
        
        # Capture multiple frames and use the sharpest one
        print("Capturing 5 frames to find the sharpest...")
        best_frame = None
        best_sharpness = 0
        
        for i in range(5):
            ret, frame = self.camera.read()
            if ret:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
                print(f"  Frame {i+1}: sharpness={sharpness:.2f}")
                
                if sharpness > best_sharpness:
                    best_sharpness = sharpness
                    best_frame = gray
        
        if best_frame is None:
            print("ERROR: Could not capture images")
            return False
        
        # Enhance and save
        enhanced = self._enhance_contrast(best_frame)
        cv2.imwrite('golden_image.jpg', enhanced)
        
        # Show preview
        cv2.imshow('Golden Image (Reference)', enhanced)
        print("\n✓ Golden image saved as 'golden_image.jpg'")
        print("\nPreview (press any key to close):")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
        return True
    
    def test_contrast_enhancement(self):
        """
        Test contrast enhancement settings
        Helps find optimal histogram stretching percentiles
        """
        print("\n" + "="*60)
        print("TEST: Contrast Enhancement")
        print("="*60)
        print("Adjusting histogram percentiles to enhance scratches...")
        print("Press 'q' to quit\n")
        
        # Sliders for percentile adjustment
        cv2.namedWindow('Contrast Adjustment')
        cv2.createTrackbar('Percentile Low', 'Contrast Adjustment', 10, 50, lambda x: None)
        cv2.createTrackbar('Percentile High', 'Contrast Adjustment', 90, 100, lambda x: None)
        
        while True:
            ret, frame = self.camera.read()
            if not ret:
                break
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Get trackbar values
            p_low = cv2.getTrackbarPos('Percentile Low', 'Contrast Adjustment')
            p_high = cv2.getTrackbarPos('Percentile High', 'Contrast Adjustment')
            
            # Apply histogram stretching
            v_low = np.percentile(gray, p_low)
            v_high = np.percentile(gray, p_high)
            
            enhanced = ((gray - v_low) / (v_high - v_low) * 255).astype(np.uint8)
            enhanced = np.clip(enhanced, 0, 255)
            
            cv2.imshow('Contrast Adjustment', enhanced)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cv2.destroyAllWindows()
        print(f"✓ Optimal settings: percentile_low={p_low}, percentile_high={p_high}")
    
    def test_blur_kernel_size(self):
        """
        Test blur kernel size for grain removal
        Larger kernel = more grain removal, but may blur scratches
        """
        print("\n" + "="*60)
        print("TEST: Blur Kernel Size (Grain Removal)")
        print("="*60)
        print("Adjust kernel size to remove silicone grain...")
        print("Press 'q' to quit\n")
        
        cv2.namedWindow('Blur Effect')
        cv2.createTrackbar('Kernel Size', 'Blur Effect', 25, 151, lambda x: None % 2 + 1)
        
        while True:
            ret, frame = self.camera.read()
            if not ret:
                break
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            enhanced = self._enhance_contrast(gray)
            
            # Get kernel size (must be odd)
            kernel_size = cv2.getTrackbarPos('Kernel Size', 'Blur Effect')
            if kernel_size % 2 == 0:
                kernel_size += 1
            
            # Apply blur and subtract
            blurred = cv2.GaussianBlur(enhanced, (kernel_size, kernel_size), 0)
            difference = cv2.subtract(enhanced, blurred)
            
            # Show comparison
            comparison = np.hstack([enhanced, blurred, difference])
            cv2.imshow('Blur Effect', comparison)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cv2.destroyAllWindows()
        print(f"✓ Optimal kernel size: {kernel_size}")
    
    def test_detection_threshold(self):
        """
        Test pixel difference threshold for defect detection
        """
        print("\n" + "="*60)
        print("TEST: Detection Threshold")
        print("="*60)
        print("Adjust threshold to detect scratches without false positives...")
        print("Press 'q' to quit\n")
        
        cv2.namedWindow('Threshold Detection')
        cv2.createTrackbar('Threshold', 'Threshold Detection', 50, 255, lambda x: None)
        
        while True:
            ret, frame = self.camera.read()
            if not ret:
                break
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            enhanced = self._enhance_contrast(gray)
            blurred = cv2.GaussianBlur(enhanced, (25, 25), 0)
            difference = cv2.subtract(enhanced, blurred)
            
            threshold = cv2.getTrackbarPos('Threshold', 'Threshold Detection')
            _, binary = cv2.threshold(difference, threshold, 255, cv2.THRESH_BINARY)
            
            cv2.imshow('Threshold Detection', binary)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cv2.destroyAllWindows()
        print(f"✓ Optimal threshold: {threshold}")
    
    def _enhance_contrast(self, gray: np.ndarray) -> np.ndarray:
        """Helper: enhance contrast using histogram stretching"""
        p_low = np.percentile(gray, 10)
        p_high = np.percentile(gray, 90)
        enhanced = ((gray - p_low) / (p_high - p_low) * 255).astype(np.uint8)
        return np.clip(enhanced, 0, 255)
    
    def _save_calibration_value(self, pixels_per_mm: float):
        """Save calibration value to config file"""
        with open('config/camera_config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        config['calibration']['pixels_per_mm'] = pixels_per_mm
        config['calibration']['min_defect_threshold_pixels'] = \
            int(config['calibration']['min_defect_threshold_mm'] * pixels_per_mm)
        
        with open('config/camera_config.yaml', 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        print("✓ Configuration saved!")
    
    def shutdown(self):
        """Clean up resources"""
        self.camera.release()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(
        description='Calibration tool for back cover fault detection'
    )
    parser.add_argument('--calibrate-pixels', action='store_true',
                       help='Calibrate pixel-to-mm conversion')
    parser.add_argument('--golden-image', action='store_true',
                       help='Create golden reference image')
    parser.add_argument('--test-contrast', action='store_true',
                       help='Test contrast enhancement settings')
    parser.add_argument('--test-blur', action='store_true',
                       help='Test blur kernel size for grain removal')
    parser.add_argument('--test-threshold', action='store_true',
                       help='Test detection threshold')
    parser.add_argument('--all', action='store_true',
                       help='Run all calibration steps')
    
    args = parser.parse_args()
    
    tool = CalibrationTool()
    
    try:
        if args.all or (not any(vars(args).values())):
            # Interactive menu
            print("\n" + "="*60)
            print("BACK COVER FAULT DETECTION - CALIBRATION TOOL")
            print("="*60)
            print("\n1. Calibrate pixel-to-mm conversion")
            print("2. Create golden reference image")
            print("3. Test contrast enhancement")
            print("4. Test blur kernel size")
            print("5. Test detection threshold")
            print("6. Run all tests")
            print("0. Exit\n")
            
            choice = input("Select option: ")
            
            if choice == '1':
                tool.calibrate_pixels_per_mm()
            elif choice == '2':
                tool.create_golden_image()
            elif choice == '3':
                tool.test_contrast_enhancement()
            elif choice == '4':
                tool.test_blur_kernel_size()
            elif choice == '5':
                tool.test_detection_threshold()
            elif choice == '6':
                tool.calibrate_pixels_per_mm()
                tool.create_golden_image()
                tool.test_contrast_enhancement()
                tool.test_blur_kernel_size()
                tool.test_detection_threshold()
        else:
            if args.calibrate_pixels:
                tool.calibrate_pixels_per_mm()
            if args.golden_image:
                tool.create_golden_image()
            if args.test_contrast:
                tool.test_contrast_enhancement()
            if args.test_blur:
                tool.test_blur_kernel_size()
            if args.test_threshold:
                tool.test_detection_threshold()
    
    finally:
        tool.shutdown()


if __name__ == "__main__":
    main()