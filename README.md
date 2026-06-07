# AttendanceIQ - Face Recognition & Gesture Based Attendance System

## Overview

AttendanceIQ is an AI-powered attendance management system that automates student attendance using Face Recognition and Hand Gesture Recognition. The system identifies registered students through a webcam and marks attendance when a specific gesture (Thumbs Up) is detected.

This project eliminates manual attendance processes and provides a modern, contactless attendance solution.

---

## Features

### Student Management

* Add new students
* Remove existing students
* Store student information securely
* View registered student list

### Face Recognition

* Capture and register student faces
* Automatic face detection using OpenCV
* Face embedding generation
* Student identification through webcam

### Gesture Recognition

* Hand tracking using MediaPipe
* Thumbs Up gesture detection
* Attendance confirmation through gesture
* Real-time gesture monitoring

### Attendance Management

* Mark students Present automatically
* Mark remaining students Absent
* Daily attendance records
* Attendance statistics dashboard

### Reports & Export

* View attendance history
* Export records to CSV
* Attendance analytics
* Present/Absent statistics

### User Interface

* Modern dark-themed GUI
* Real-time camera preview
* Live recognition status
* Interactive student cards

---

## Technologies Used

| Technology   | Purpose                            |
| ------------ | ---------------------------------- |
| Python       | Core Programming Language          |
| Tkinter      | GUI Development                    |
| OpenCV       | Face Detection & Camera Processing |
| MediaPipe    | Hand Gesture Recognition           |
| Pillow (PIL) | Image Processing                   |
| NumPy        | Numerical Operations               |
| CSV          | Data Export                        |
| JSON         | Data Storage                       |

---

## Project Structure

```text
AttendanceIQ/
│
├── main.py
│
├── modules/
│   ├── face_recognition_module.py
│   ├── gesture_module.py
│   └── attendance_module.py
│
├── data/
│   ├── students.json
│   └── attendance_records.json
│
├── faces/
│   └── stored_face_embeddings
│
└── exports/
    └── attendance_reports.csv
```

---

## Installation

### Clone or Download Project

```bash
git clone <repository-url>
cd AttendanceIQ
```

### Install Dependencies

```bash
pip install opencv-python
pip install mediapipe
pip install pillow
pip install numpy
```

Or install all at once:

```bash
pip install opencv-python mediapipe pillow numpy
```

---

## How to Run

Navigate to the project directory:

```bash
cd AttendanceIQ
```

Run the application:

```bash
python main.py
```

---

## Usage

### Step 1: Register Students

1. Open Student Registration page.
2. Enter student name and roll number.
3. Click "Add Student".

### Step 2: Capture Face

1. Select a student card.
2. Click "Capture Face".
3. Look directly at the camera.
4. Wait until face samples are collected.
5. Face data will be saved automatically.

### Step 3: Start Attendance

1. Open Attendance page.
2. Click "Start Camera".
3. Student stands in front of the webcam.
4. System recognizes the face.
5. Student shows 👍 Thumbs Up gesture.
6. Attendance is marked automatically.

### Step 4: View Records

1. Open Records page.
2. View attendance history.
3. Export records as CSV if required.

---

## Attendance Workflow

```text
Student Face
      ↓
Face Detection
      ↓
Face Recognition
      ↓
Gesture Detection
      ↓
Thumbs Up Detected
      ↓
Attendance Marked Present
```

---

## Future Enhancements

* Database integration (MySQL/PostgreSQL)
* Cloud storage support
* QR Code attendance backup
* Multi-classroom management
* Email attendance reports
* Mobile application support
* Admin authentication
* Attendance analytics dashboard

---

## Challenges Faced

| Challenge                 | Solution                                     |
| ------------------------- | -------------------------------------------- |
| Accurate face recognition | Used face embeddings and similarity matching |
| False attendance marking  | Added gesture confirmation                   |
| Real-time performance     | Optimized recognition intervals              |
| User-friendly interface   | Designed modern Tkinter dashboard            |

---

## Conclusion

AttendanceIQ provides an intelligent and automated attendance solution by combining Face Recognition and Gesture Recognition technologies. The system improves attendance accuracy, reduces manual effort, and offers a modern digital attendance experience.
