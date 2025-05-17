import cv2
import numpy as np
import base64
import logging
from io import BytesIO
from PIL import Image

logger = logging.getLogger(__name__)

class TomatoDetector:
    """
    A class for detecting and classifying tomatoes in images.
    Uses OpenCV for basic image processing and color-based detection.
    """

    def __init__(self, config=None):
        """
        Initialize the tomato detector with configuration parameters.

        Args:
            config (dict): Configuration parameters for detection
        """
        self.config = config or {}

        # Default configuration values
        self.ripe_hue_min = self.config.get('ripe_threshold_min', 0)
        self.ripe_hue_max = self.config.get('ripe_threshold_max', 30)
        self.green_hue_min = self.config.get('green_threshold_min', 31)
        self.green_hue_max = self.config.get('green_threshold_max', 70)
        self.sensitivity = self.config.get('detection_sensitivity', 70)

        # Initialize OpenCV parameters
        self.min_contour_area = 1000  # Minimum contour area to consider
        self.blur_size = (5, 5)  # Gaussian blur kernel size

        # Tomato shape parameters
        self.min_circularity = 0.6  # Minimum circularity for tomato (1.0 is perfect circle)
        self.min_convexity = 0.8    # Minimum convexity for tomato shape

    def update_config(self, config):
        """Update detector configuration."""
        self.config.update(config)
        self.ripe_hue_min = self.config.get('ripe_threshold_min', 0)
        self.ripe_hue_max = self.config.get('ripe_threshold_max', 30)
        self.green_hue_min = self.config.get('green_threshold_min', 31)
        self.green_hue_max = self.config.get('green_threshold_max', 70)
        self.sensitivity = self.config.get('detection_sensitivity', 70)

    def detect_from_base64(self, base64_image):
        """
        Detect tomatoes from a base64 encoded image.

        Args:
            base64_image (str): Base64 encoded image string

        Returns:
            dict: Detection results
        """
        try:
            # Decode base64 image
            image_data = base64.b64decode(base64_image.split(',')[1] if ',' in base64_image else base64_image)
            image = Image.open(BytesIO(image_data))

            # Convert PIL image to OpenCV format
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

            # Process the image
            return self.detect(cv_image)

        except Exception as e:
            logger.error(f"Error processing base64 image: {str(e)}")
            return {"error": str(e)}

    def detect(self, image):
        """
        Detect and classify tomatoes in an image.

        Args:
            image (numpy.ndarray): OpenCV image in BGR format

        Returns:
            dict: Detection results with type and confidence
        """
        # Convert to HSV color space
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(hsv_image, self.blur_size, 0)

        # Create masks for red and green tomatoes
        # Red tomatoes (hue around 0-30)
        lower_red = np.array([self.ripe_hue_min, 100, 100])
        upper_red = np.array([self.ripe_hue_max, 255, 255])
        red_mask = cv2.inRange(blurred, lower_red, upper_red)

        # Green tomatoes (hue around 31-70)
        lower_green = np.array([self.green_hue_min, 100, 100])
        upper_green = np.array([self.green_hue_max, 255, 255])
        green_mask = cv2.inRange(blurred, lower_green, upper_green)

        # Find contours in the masks
        red_contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        green_contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter contours by size
        red_contours = [c for c in red_contours if cv2.contourArea(c) > self.min_contour_area]
        green_contours = [c for c in green_contours if cv2.contourArea(c) > self.min_contour_area]

        # Calculate total area of contours
        red_area = sum(cv2.contourArea(c) for c in red_contours)
        green_area = sum(cv2.contourArea(c) for c in green_contours)

        # Calculate image area
        image_area = image.shape[0] * image.shape[1]

        # Calculate percentages
        red_percent = (red_area / image_area) * 100 if image_area > 0 else 0
        green_percent = (green_area / image_area) * 100 if image_area > 0 else 0

        # Analyze shape to confirm it's a tomato
        red_shape_score = self._analyze_tomato_shape(red_contours)
        green_shape_score = self._analyze_tomato_shape(green_contours)

        # Combine color and shape scores
        red_score = red_percent * red_shape_score
        green_score = green_percent * green_shape_score

        # Determine tomato type based on combined scores and sensitivity threshold
        min_confidence = self.sensitivity / 10  # Convert sensitivity (0-100) to minimum confidence threshold

        if red_score > green_score and red_score > min_confidence:
            return {
                "type": "ripe",
                "confidence": red_score,
                "contours": len(red_contours),
                "is_tomato": red_shape_score > 0.5  # Threshold for tomato shape
            }
        elif green_score > red_score and green_score > min_confidence:
            return {
                "type": "green",
                "confidence": green_score,
                "contours": len(green_contours),
                "is_tomato": green_shape_score > 0.5  # Threshold for tomato shape
            }
        else:
            return {
                "type": None,
                "confidence": 0,
                "contours": 0,
                "is_tomato": False
            }

    def _analyze_tomato_shape(self, contours):
        """
        Analyze contours to determine if they resemble tomatoes.

        Args:
            contours (list): List of contours to analyze

        Returns:
            float: Shape score between 0 and 1, where 1 is most likely a tomato
        """
        if not contours:
            return 0.0

        # Find the largest contour (most likely to be the tomato)
        largest_contour = max(contours, key=cv2.contourArea)

        # Calculate circularity (how close to a circle)
        area = cv2.contourArea(largest_contour)
        perimeter = cv2.arcLength(largest_contour, True)
        circularity = 0.0
        if perimeter > 0:
            circularity = 4 * np.pi * area / (perimeter * perimeter)

        # Calculate convexity (how convex the shape is)
        hull = cv2.convexHull(largest_contour)
        hull_area = cv2.contourArea(hull)
        convexity = area / hull_area if hull_area > 0 else 0

        # Calculate aspect ratio (tomatoes are roughly circular)
        x, y, w, h = cv2.boundingRect(largest_contour)
        aspect_ratio = min(w, h) / max(w, h) if max(w, h) > 0 else 0

        # Calculate roundness score
        roundness_score = (circularity + convexity + aspect_ratio) / 3.0

        # Check if shape meets minimum requirements for a tomato
        if circularity < self.min_circularity or convexity < self.min_convexity:
            roundness_score *= 0.5  # Penalize non-tomato shapes

        return min(1.0, roundness_score)

    def draw_detection(self, image, detection_result):
        """
        Draw detection results on the image.

        Args:
            image (numpy.ndarray): OpenCV image
            detection_result (dict): Detection results

        Returns:
            numpy.ndarray: Image with detection visualization
        """
        output = image.copy()

        if detection_result["type"] == "ripe":
            color = (0, 0, 255)  # Red in BGR
            label = "Ripe Tomato" if detection_result.get("is_tomato", False) else "Red Object"
        elif detection_result["type"] == "green":
            color = (0, 255, 0)  # Green in BGR
            label = "Green Tomato" if detection_result.get("is_tomato", False) else "Green Object"
        else:
            return output  # No detection to draw

        # Draw a rectangle in the center of the image
        h, w = output.shape[:2]
        center_x, center_y = w // 2, h // 2
        rect_size = min(w, h) // 3

        cv2.rectangle(
            output,
            (center_x - rect_size, center_y - rect_size),
            (center_x + rect_size, center_y + rect_size),
            color,
            2
        )

        # Add text with confidence
        confidence = f"{label}: {detection_result['confidence']:.1f}%"
        cv2.putText(
            output,
            confidence,
            (center_x - rect_size, center_y - rect_size - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2
        )

        # Add tomato verification text
        if detection_result["type"] is not None:
            verification_text = "Verified Tomato" if detection_result.get("is_tomato", False) else "Not a Tomato"
            cv2.putText(
                output,
                verification_text,
                (center_x - rect_size, center_y - rect_size - 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255) if not detection_result.get("is_tomato", False) else (0, 255, 0),
                2
            )

        return output
