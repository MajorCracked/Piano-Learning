# 🎹 Piano Learning Lab: Pro Edition
[![Ask DeepWiki](https://devin.ai/assets/askdeepwiki.png)](https://deepwiki.com/MajorCracked/Piano-Learning)

This repository contains the source code for the Piano Learning Lab, an AI-powered tool that transforms any piano audio recording (`.wav` or `.mp3`) into a synchronized, interactive visual tutorial. It uses a high-resolution piano transcription model to detect individual notes and timings, then generates a dynamic "falling notes" display similar to Synthesia, paired with an on-screen keyboard.

The entire application is built with Python and Streamlit, featuring a custom HTML/CSS/JavaScript front-end for the hardware-accelerated visualizer.

## Features

*   **AI-Powered Transcription**: Utilizes a deep learning model to perform polyphonic piano transcription from raw audio.
*   **Interactive Visualizer**: Generates a dynamic, falling-note display synchronized with audio playback.
*   **Responsive Keyboard**: An 88-key on-screen piano highlights keys in real-time as they are played in the recording.
*   **Audio Format Support**: Accepts both `.wav` and `.mp3` file uploads.
*   **AI Tuning Engine**: Provides fine-grained control to filter transcription results and improve accuracy:
    *   **Noise Gate (Velocity)**: Filters out very quiet notes that might be noise or background artifacts.
    *   **Minimum Note Length**: Eliminates ultra-short "glitch" notes often produced by transcription models.
    *   **Pedal Override (Max Length)**: Sets a maximum visual duration for notes, preventing the on-screen keyboard from getting stuck on long, pedal-sustained notes.

## How It Works

The application operates in two main stages:

1.  **AI Transcription (Backend)**:
    *   The user uploads an audio file via the Streamlit interface.
    *   The audio is loaded using `librosa`.
    *   The core transcription is performed by the `piano-transcription-inference` library, which leverages a pre-trained PyTorch model (`note_F1=0.9677_pedal_F1=0.9186.pth`). The model runs on a CUDA-enabled GPU if available, otherwise falling back to CPU.
    *   The raw note events (pitch, start time, end time, velocity) are post-processed in `src/polyphonic_engine.py`. This is where the "AI Tuning Engine" sliders apply their logic to filter the notes based on velocity and duration.
    *   The cleaned list of notes is converted into a JSON object.

2.  **Visualization (Frontend)**:
    *   The Streamlit app dynamically generates a self-contained HTML, CSS, and JavaScript payload.
    *   This payload includes the base64-encoded audio and the JSON object of notes.
    *   **CSS**: Styles the visualizer, controls, and piano keyboard.
    *   **JavaScript**:
        *   Calculates the precise geometry for all 88 black and white keys to render a realistic keyboard.
        *   Renders the "falling notes" onto the visualizer, positioning and scaling them based on their start/end times.
        *   Uses `requestAnimationFrame` to create a smooth, hardware-accelerated animation loop that is perfectly synchronized with the `<audio>` element's `currentTime`.
        *   Updates the keyboard key styles and visualizer scroll position on every frame.

## Setup and Local Installation

This project uses Git LFS to manage the large model file. Please ensure you have Git LFS installed.

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/MajorCracked/Piano-Learning.git
    cd Piano-Learning
    ```

2.  **Download the model file:**
    The `.pth` model file is stored using Git LFS. Pull the file from the LFS storage:
    ```sh
    git lfs pull
    ```

3.  **Install Python dependencies:**
    It is recommended to use a virtual environment.
    ```sh
    pip install -r requirements.txt
    ```
    *Note: For GPU acceleration, ensure you have a compatible version of PyTorch installed for your CUDA toolkit.*

4.  **Run the Streamlit application:**
    ```sh
    streamlit run app.py
    ```

5.  Open your web browser and navigate to the local URL provided by Streamlit (usually `http://localhost:8501`).

## How to Use

1.  Launch the application using the instructions above.
2.  Use the sidebar's **AI Tuning Engine** sliders to configure the transcription parameters. For best results, adjust these after your first transcription to clean up the output.
3.  Click the "Upload .wav or .mp3 performance" button to select your audio file.
4.  Once uploaded, click the **"Generate Synchronized Visualization"** button.
5.  Wait for the AI model to process the audio. A spinner will indicate that it's working.
6.  Once complete, the interactive visualizer will appear.
7.  Click the **"▶ START LESSON"** button to begin playback and watch the synchronized tutorial.