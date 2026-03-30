import torch
import librosa
from piano_transcription_inference import PianoTranscription, sample_rate

def midi_to_note_name(midi_pitch):
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (int(midi_pitch) // 12) - 1
    return f"{notes[int(midi_pitch) % 12]}{octave}"

def note_name_to_midi(note_name):
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    name = note_name[:-1]
    octave = int(note_name[-1])
    return (octave + 1) * 12 + notes.index(name)

def transcribe_polyphonic(audio_path, noise_gate=30, min_duration=0.05, max_duration=1.0):
    print(f"Igniting High-Res Piano AI on {audio_path}...")
    
    audio, _ = librosa.load(audio_path, sr=sample_rate, mono=True)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    transcriptor = PianoTranscription(device=device)
    ai_output = transcriptor.transcribe(audio, midi_path=None)
    
    note_list = []
    if isinstance(ai_output, dict) and 'est_note_events' in ai_output:
        note_list = ai_output['est_note_events']
    elif isinstance(ai_output, list):
        note_list = ai_output
        
    transcription = []
    
    for raw_note in note_list:
        try:
            if hasattr(raw_note, '__dict__'): note = vars(raw_note)
            elif hasattr(raw_note, '_asdict'): note = raw_note._asdict()
            elif isinstance(raw_note, dict): note = raw_note
            else: continue
            
            pitch, start, end, velocity = None, None, None, 127
            
            for k, v in note.items():
                k_str = str(k).lower()
                if 'pitch' in k_str or 'note' in k_str or 'midi' in k_str: pitch = float(v)
                elif 'start' in k_str or 'onset' in k_str or 'begin' in k_str or 'time' == k_str: start = float(v)
                elif 'end' in k_str or 'offset' in k_str or 'stop' in k_str: end = float(v)
                elif 'vel' in k_str or 'amp' in k_str: velocity = float(v)
                    
            if end is None and start is not None:
                for k, v in note.items():
                    if 'duration' in str(k).lower() or 'len' in str(k).lower(): end = start + float(v)
                        
            if 0.0 < velocity <= 1.0: velocity = velocity * 127
                
            if pitch is not None and start is not None and end is not None:
                duration = end - start

                if duration > max_duration:
                    end = start + max_duration
                    duration = max_duration
                
                if 21 <= pitch <= 108 and velocity >= noise_gate and duration >= min_duration:
                    transcription.append({
                        'Note': midi_to_note_name(pitch),
                        'Start Time (s)': round(start, 3),
                        'End Time (s)': round(end, 3)
                    })
        except Exception:
            continue
            
    return sorted(transcription, key=lambda x: x['Start Time (s)'])
