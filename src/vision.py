import cv2
import numpy as np
from PIL import Image

def load_points(image_path):
    # Load the image
    img = Image.open(image_path).convert('RGBA')
    img_array = np.array(img)
    
    # Create dictionaries to store points by RGB values
    a_points = {}  # Alpha = 255
    b_points = {}  # Alpha < 255
    
    # Iterate through each pixel
    height, width = img_array.shape[:2]
    for y in range(height):
        for x in range(width):
            r, g, b, a = img_array[y, x]
            rgb_key = (r, g, b)
            
            # Skip transparent pixels (could adjust this threshold if needed)
            if a == 0:
                continue
                
            # Store points based on alpha value
            if a == 255:
                a_points[rgb_key] = (x, y)
            else:
                b_points[rgb_key] = (x, y)
    
    # Prepare the result arrays
    a_coords = []
    b_coords = []
    
    # For each A point, find corresponding B point or use A point if no match
    for rgb_key, a_coord in a_points.items():
        a_coords.append(a_coord)
        if rgb_key in b_points:
            b_coords.append(b_points[rgb_key])
        else:
            b_coords.append(a_coord)  # Use A coordinates if no B match
    
    return np.array(a_coords), np.array(b_coords)


def build_transformation(a_points, b_points):
    # Need at least 4 point pairs
    assert len(a_points) >= 4, "Need at least 4 point pairs"
    
    # Convert to numpy arrays
    a_points = np.array(a_points, dtype=np.float32)
    b_points = np.array(b_points, dtype=np.float32)
    
    # Calculate homography matrix
    H, _ = cv2.findHomography(a_points, b_points)
    
    def transform_point(img_point):
        px, py = img_point
        point = np.array([px, py, 1])
        transformed = np.dot(H, point)
        # Normalize by dividing by the third component
        return transformed[0]/transformed[2], transformed[1]/transformed[2]
    
    return transform_point

def detect_walls(img):
    # Load the image
    # add a filter  to the image
    # Load calibration data from .npz file
    # calibration_data = np.load("camera_calibration.npz")
    # mtx = calibration_data['camera_matrix'].copy()
    # dist = calibration_data['dist_coeffs'].copy()
    # h = img.shape[0]
    # w = img.shape[1]
    # print(h, w)
    # newcameramtx, roi = cv2.getOptimalNewCameraMatrix(mtx, dist, (w, h), 1, (w, h))
    # # undistort the image
    # # Undistort the image using the calibration data
    # img = cv2.undistort(img, mtx, dist, None, newcameramtx)

    original_size = img.shape
    original_size = (640,360)
    print("shape", img.shape)
    new_size = (1920, 1080)
    scale_factor = (
        original_size[1] / new_size[0], original_size[0] / new_size[1]
    )

    img = cv2.resize(img, new_size)

    lower_red1 = np.array([0, 100, 100])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 100, 100])
    upper_red2 = np.array([180, 255, 255])

    # Convert the image to HSV color space
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask = cv2.bitwise_or(mask1, mask2)

    # Create a mask for the specified color range

    # Find contours in the mask
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter contours based on area
    min_area = 1000  # Adjust this value as needed
    filtered_contours = [
        contour for contour in contours if cv2.contourArea(contour) > min_area
    ]

    polygons = []
    # Draw rectangles around the detected areas
    for contour in filtered_contours:
        x, y, w, h = cv2.boundingRect(contour)
        cv2.rectangle(
            img, (x, y), (x + w, y + h), (0, 255, 0), 2
        )  # Draw rectangles in green

    # detect lines in the image
    lines = cv2.HoughLinesP(
        mask, 1, np.pi / 180, threshold=120, minLineLength=100, maxLineGap=1.5
    )
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            cv2.line(img, (x1, y1), (x2, y2), (255, 0, 0), 2)  # Draw lines in blue
            polygons.append([x1, y1, x2, y2])

    output_img = np.zeros(img.shape, dtype=np.uint8)
    # Make it so the first point is always the top left corner and the last point is always the bottom right corner
    for i in range(len(polygons)):
        if polygons[i][0] > polygons[i][2]:
            polygons[i][0], polygons[i][2] = polygons[i][2], polygons[i][0]
        if polygons[i][1] > polygons[i][3]:
            polygons[i][1], polygons[i][3] = polygons[i][3], polygons[i][1]

    new_polys = []
    for p in polygons:
        if not any(
            abs(p[0] - up[0]) < 100
            and abs(p[1] - up[1]) < 100
            and abs(p[2] - up[2]) < 100
            and abs(p[3] - up[3]) < 100
            for up in new_polys 
        ):
            new_polys.append(p)

    polygons = new_polys

    # draw polygons on output image
    for p in polygons:
        cv2.rectangle(
            output_img, (p[0], p[1]), (p[2], p[3]), (0, 0, 255), 2
        )  # Draw rectangles in red
        cv2.circle(output_img, (p[0], p[1]), 5, (255, 0, 0), -1)
        cv2.circle(output_img, (p[2], p[3]), 5, (0, 255, 0), -1)

    cv2.imwrite("/agent/walls1.jpg", img)
    cv2.imwrite("/agent/walls2.jpg", output_img)

    # show output image
    # cv2.imshow('Output Image', output_img)
    # cv2.imshow('Image', img)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    # Resize polygons by the scale factor
    polygons = [
        [
            int(p[0] * scale_factor[0]),
            int(p[1] * scale_factor[1]),
            int(p[2] * scale_factor[0]),
            int(p[3] * scale_factor[1]),
        ]
        for p in polygons
    ]

    return polygons

def detect_cubes_camera_agent(img):
    # resize the image to 1024x576
    original_size = img.shape
    original_size = (640,360)
    new_size = (1920, 1080)
    scale_factor = (
        original_size[1] / new_size[0], original_size[0] / new_size[1]
    )
    img = cv2.resize(img, new_size)
    # Convert the image to HSV color space
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    kernel = np.ones((3, 3), np.uint8)

    # Define the HSV range for black
    lower_black = np.array([0, 0, 0])
    upper_black = np.array([180, 255, 100])
    mask = cv2.inRange(hsv, lower_black, upper_black)

    # Add a mask to find white cubes
    lower_white = np.array([0, 0, 200])
    upper_white = np.array([180, 255, 255])
    mask2 = cv2.inRange(hsv, lower_white, upper_white)

    # Combine the masks
    mask = cv2.bitwise_or(mask, mask2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # Invert the mask to make black areas white
    inverted_mask = cv2.bitwise_not(mask)

    # Create a blank white image
    white_background = np.ones_like(img) * 255

    # Find contours in the mask
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # Filter contours based on area
    min_area = 20  # Adjust this value as needed
    max_area = 500
    filtered_contours = [contour for contour in contours if min_area < cv2.contourArea(contour) < max_area]
    # Draw all contours except the first
    final_contours = []
    for contour in filtered_contours:  # Skip the first contour
        epsilon = 0.08 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)

        # Filter for quadrilateral shapes
        if len(approx) == 4 and cv2.isContourConvex(approx):
            final_contours.append(approx)
            cv2.drawContours(white_background, [approx], -1, (0, 255, 0), 3)
    polygons = []
    #
    for contour in final_contours:
        x, y, w, h = cv2.boundingRect(contour)
        cv2.rectangle(white_background, (x, y), (x + w, y + h), (255, 0, 0), 2)  # Draw rectangles in blue    
        polygons.append([x, y, x + w, y + h])
    # Apply scale factor
    polygons = [
        [
            int(p[0] * scale_factor[0]),
            int(p[1] * scale_factor[1]),
            int(p[2] * scale_factor[0]),
            int(p[3] * scale_factor[1]),
        ]
        for p in polygons
    ]
    return polygons
