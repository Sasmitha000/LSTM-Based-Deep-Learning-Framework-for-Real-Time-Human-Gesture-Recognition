# SignBridge — LSTM-Based Deep Learning Framework for Real-Time Human Gesture Recognition

![Python](https://img.shields.io/badge/Python-3.12-blue)
![TensorFlow](https://img.shields.io/badge/TensorFlow-2.x-orange)
![MediaPipe](https://img.shields.io/badge/MediaPipe-Holistic-green)
![Flask](https://img.shields.io/badge/Flask-SocketIO-lightgrey)

> BSc (Hons) Computer Science — Final Year Project
> Module: PUSL3190 | Plymouth University
> Student: Kannangara K Kannangara | Index: 10953387
> Supervisor: Ms. Hirushi Dilpriya

---

## Overview

SignBridge is a real-time American Sign Language (ASL) detection and translation system powered by deep learning. Using a 3-layer LSTM neural network trained on MediaPipe Holistic keypoints, the system achieves 98.3% test accuracy and delivers gesture predictions in under 200ms via WebSocket streaming.

---

## Features

- Real-Time Detection — WebSocket streaming with LSTM inference
- 98.3% Accuracy — 3-layer LSTM trained on 300 sequences
- Multilingual Translation — English, Spanish, French, Arabic, Hindi, Japanese
- Presentation Mode — Screen share friendly overlay for Zoom and Meet
- Admin Dashboard — Full analytics, RBAC, model retraining with model library
- Developer API — REST API with JWT-style authentication and API key management
- PWA — Installable on desktop and mobile
- Dark/Light Mode — Full theme support
- Multilingual UI — Interface in 6 languages
- Crowdsourced Learning — User contributions improve model accuracy over time

---

## Model Architecture

Input: 30 frames x 1662 MediaPipe Holistic keypoints
- LSTM(64, return_sequences=True)
- LSTM(128, return_sequences=True)
- LSTM(64, return_sequences=False)
- Dense(64, relu)
- Dense(32, relu)
- Dense(2, softmax) outputs: thanks, i love you

Optimizer: Adam lr=0.0001
Loss: Categorical Crossentropy
Epochs: 2000
Test Accuracy: 98.3%

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| ML Model | TensorFlow/Keras LSTM |
| Keypoint Extraction | MediaPipe Holistic |
| Backend | Flask + Flask-SocketIO |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Frontend | HTML5, CSS3, JavaScript |
| Real-time | WebSocket (Socket.IO) |
| PWA | Service Worker + Web Manifest |
| Auth | bcrypt + Session Tokens |

---

## Installation

### Prerequisites
- Python 3.12
- Anaconda recommended

### Backend Setup
cd backend
pip install -r requirements.txt
python app.py

### Frontend Setup
cd frontend
python3 -m http.server 8080

### Access
http://127.0.0.1:8080                     Main app
http://127.0.0.1:8080/dashboard.html      Admin dashboard
http://127.0.0.1:8080/get-api-key.html    Developer portal

---

## Project Structure
sign-language-translator/
├── backend/
│   ├── app.py                Flask + SocketIO server
│   ├── database.py           SQLite/PostgreSQL dual support
│   ├── model/
│   │   └── action.keras      Trained LSTM model
│   └── requirements.txt
└── frontend/
├── index.html            Home page
├── detection.html        Live detection
├── learning.html         Learning module
├── dashboard.html        Admin dashboard
├── api-docs.html         API documentation
├── get-api-key.html      Developer portal
├── user-dashboard.html   User API dashboard
├── manifest.json         PWA manifest
├── service-worker.js     PWA service worker
├── css/style.css         Global styles
└── js/
├── detection.js      Detection logic
├── main.js           Navigation
└── i18n.js           Multilingual UI

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/health | Server status |
| GET | /api/gestures | Supported gestures |
| POST | /api/translate | Translate gesture text |
| POST | /api/contribute | Submit keypoint data |
| GET | /api/analytics | Session analytics |
| POST | /api/auth/register | Register developer account |
| POST | /api/auth/login | Login to developer account |
| WebSocket | /frame | Real-time gesture detection |

---

## Results

| Metric | Value |
|--------|-------|
| Test Accuracy | 98.3% |
| Thanks Precision | 97% |
| Thanks Recall | 100% |
| I Love You Precision | 100% |
| I Love You Recall | 97% |
| F1 Score | 98% |
| Inference Speed | under 200ms |
| Training Sequences | 300 (150 per class) |
| Keypoints per Frame | 1662 |

---

## Future Work

- Expand gesture vocabulary beyond 2 classes
- Neutral class classifier to reduce false positives on non-sign hand positions
- Mobile native application using React Native
- Real-time sentence construction with grammar rules
- Direct integration with video conferencing platforms via browser extension
- Transfer learning from larger sign language datasets

---

## Academic Context

This system was developed as a final year project investigating the application of deep learning for assistive communication technology. The research demonstrates that LSTM networks trained on MediaPipe Holistic keypoints can achieve high accuracy real-time gesture recognition without specialized hardware, making sign language translation accessible to any device with a standard webcam.

---

License

This project is submitted as part of PUSL3190 Final Year Project at Plymouth University. All rights reserved.

SignBridge — Breaking barriers with Sign Language AI
