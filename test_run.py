import os
from src.feature_extraction import process_audio, plot_spectrogram, slice_and_save_spectrograms

AUDIO_FILE = os.path.join("data", "raw_audio", "sample_piano.wav")

def main():
    if not os.path.exists(AUDIO_FILE):
        print(f"Error: Could not find {AUDIO_FILE}. Please add a .wav file!")
        return

    # 1. Process the audio
    y, sample_rate, spectrogram_data, onsets = process_audio(AUDIO_FILE)
    
    # 2. Slice and save the images for the CNN
    slice_and_save_spectrograms(y, sample_rate, onsets)
    
    # 3. Plot the main result so you can still see the overview
    print("\nClose the graph window to end the script.")
    plot_spectrogram(spectrogram_data, sample_rate, onsets)

if __name__ == "__main__":
    main()