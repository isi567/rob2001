# find.py
#
# A headless version of the blob detection code from trilo_blob.py
#
# Simon Parsons
# University of Lincoln
# 26-03-13

# import vision package
import cv2

def find_color_centers(image, color_ranges):
    """
    Find the centers of the largest contours for the colour blobs defined
    in color_ranges.
    
    Args:
        image: BGR image from camera (numpy array)
    
    Returns:
        dict: Dictionary with color names as keys and (x, y) tuples as values.
              Returns None for colors where no contour is found.
              Example: {'red': (120, 340), 'green': None}
    """
    # Convert BGR to HSV
    hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # Store centers
    centers = {}
    
    # Process each color
    for color_name, color_info in color_ranges.items():
        # Create mask for this color
        mask = cv2.inRange(hsv_image, color_info['lower'], color_info['upper'])
        
        # Find contours in the mask
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            # Find the largest contour by area
            largest_contour = max(contours, key=cv2.contourArea)
            
            # Calculate moments to find the center
            M = cv2.moments(largest_contour)
            
            if M["m00"] != 0:
                # Calculate center coordinates
                center_x = int(M["m10"] / M["m00"])
                center_y = int(M["m01"] / M["m00"])
                centers[color_name] = (center_x, center_y)
            else:
                centers[color_name] = None
        else:
            centers[color_name] = None
    
    return centers
