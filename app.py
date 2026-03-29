import os
import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
import base64
import io
import mido

def create_midi_bytes(transcription_data):
    """Converts the cleaned AI transcription into a downloadable MIDI file."""
    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    ticks_per_second = 960 
    
    events = []
    for item in transcription_data:
        pitch = note_name_to_midi(item['Note'])
        events.append({'time': item['Start Time (s)'], 'type': 'note_on', 'note': pitch, 'vel': 85})
        events.append({'time': item['End Time (s)'], 'type': 'note_off', 'note': pitch, 'vel': 0})

    events.sort(key=lambda x: x['time'])

    current_time = 0
    for evt in events:
        delta_ticks = int((evt['time'] - current_time) * ticks_per_second)
        track.append(mido.Message(evt['type'], note=evt['note'], velocity=evt['vel'], time=delta_ticks))
        current_time = evt['time']

    midi_buffer = io.BytesIO()
    mid.save(file=midi_buffer)
    return midi_buffer.getvalue()

from src.polyphonic_engine import transcribe_polyphonic, note_name_to_midi

st.set_page_config(page_title="Piano Learning Lab", layout="wide")

st.title("🎹 Piano Learning Lab: Pro Edition")
st.write("Upload your performance (.wav or .mp3) to generate an interactive, synchronized tutorial.")

uploaded_file = st.file_uploader("Upload .wav or .mp3 performance", type=["wav", "mp3"])

with st.sidebar:
    st.header("🎛️ AI Tuning Engine")
    st.write("Tune the neural network to filter out acoustic echoes and MP3 compression artifacts.")
    
    noise_slider = st.slider(
        "Noise Gate (Velocity)", 
        min_value=0, max_value=80, value=40, step=5,
        help="Higher values aggressively delete quiet notes."
    )
    
    duration_slider = st.slider(
        "Minimum Note Length (s)", 
        min_value=0.01, max_value=0.20, value=0.05, step=0.01,
        help="Higher values delete lightning-fast 'glitch' notes."
    )
    
    # ADD THIS NEW SLIDER
    max_duration_slider = st.slider(
        "Pedal Override (Max Length)", 
        min_value=0.2, max_value=4.0, value=1.0, step=0.1,
        help="Forces long, sustained notes to 'release' visually so the keyboard doesn't stay green forever."
    )
    
    st.markdown("---")

# Everything below this line MUST be indented!
if uploaded_file is not None:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    mime_type = "audio/mpeg" if file_ext == "mp3" else "audio/wav"
    
    audio_bytes = uploaded_file.read()
    audio_b64 = base64.b64encode(audio_bytes).decode()
    
    # Ensure the data folder exists so it doesn't crash on saving
    os.makedirs("data", exist_ok=True)
    
    temp_audio_path = os.path.join("data", f"temp_upload.{file_ext}")
    with open(temp_audio_path, "wb") as f:
        f.write(audio_bytes)

    if st.button("Generate Synchronized Visualization"):
        with st.spinner("AI is listening to your audio"):
            
            data = transcribe_polyphonic(
                temp_audio_path, 
                noise_gate=noise_slider, 
                min_duration=duration_slider,
                max_duration=max_duration_slider
            )

            st.success("Transcription Complete! Rendering visualizer...")
            
            if data:
                df = pd.DataFrame(data)
                df['MIDI'] = df['Note'].apply(note_name_to_midi)
                notes_json = df.to_json(orient='records')
                
                html_code = f"""
                <style>
                    /* THIS IS THE SILVER BULLET: Forces borders inside the width so the math doesn't break */
                    * {{ box-sizing: border-box; }}
                    
                    body {{ background: #0b0b0b; margin: 0; font-family: 'Inter', sans-serif; color: white; overflow: hidden; }}
                    #main-wrapper {{ display: flex; flex-direction: column; height: 850px; background: #000; border: 1px solid #333; }}
                    
                    #visualizer {{ flex-grow: 1; position: relative; overflow: hidden; background: #000; }}
                    #impact-bar {{ position: absolute; bottom: 0; width: 100%; height: 4px; background: #00ff00; box-shadow: 0 0 20px #00ff00; z-index: 100; }}

                    #keyboard-container {{ position: relative; height: 180px; background: #111; border-top: 2px solid #333; }}
                    
                    .white-key {{ 
                        position: absolute; height: 100%; background: linear-gradient(#ddd, #fff); 
                        border: 1px solid #777; border-radius: 0 0 5px 5px; z-index: 1;
                        box-shadow: inset 0 -5px 10px rgba(0,0,0,0.1); transition: background 0.05s, transform 0.05s;
                    }}
                    .black-key {{ 
                        position: absolute; height: 60%; background: linear-gradient(#333, #000); 
                        z-index: 2; border-radius: 0 0 4px 4px; border: 1px solid #111;
                        box-shadow: 2px 4px 8px rgba(0,0,0,0.6); transition: background 0.05s, transform 0.05s;
                    }}

                    #controls {{ padding: 20px; background: #1a1a1a; display: flex; align-items: center; justify-content: space-between; border-top: 1px solid #333; }}
                    #play-btn {{ padding: 15px 40px; background: #00ff00; color: #000; font-weight: 900; border: none; border-radius: 8px; cursor: pointer; text-transform: uppercase; }}
                    #play-btn:hover {{ background: #00cc00; }}
                    #status {{ font-family: monospace; color: #00ff00; font-size: 1.5rem; }}
                </style>

                <div id="main-wrapper">
                    <div id="visualizer"><div id="note-stream"></div><div id="impact-bar"></div></div>
                    <div id="keyboard-container"><div id="keyboard-target"></div></div>
                    <div id="controls">
                        <button id="play-btn">▶ START LESSON</button>
                        <div id="status">0.00s</div>
                        <audio id="audio-engine" src="data:{mime_type};base64,{audio_b64}"></audio>
                    </div>
                </div>

                <script>
                    const notes = {notes_json};
                    const audio = document.getElementById('audio-engine');
                    const playBtn = document.getElementById('play-btn');
                    const status = document.getElementById('status');
                    const piano = document.getElementById('keyboard-target');
                    const PIXELS_PER_SEC = 250;

                    // 1. TRUE CENTER GEOMETRY ENGINE
                    const geometry = {{}};
                    const WHITE_KEY_WIDTH = 100 / 52;
                    let wIndex = 0;

                    // Pass A: Calculate White Keys & their exact centers
                    for (let i = 21; i <= 108; i++) {{
                        const isBlack = [1, 3, 6, 8, 10].includes(i % 12);
                        if (!isBlack) {{
                            const left = wIndex * WHITE_KEY_WIDTH;
                            const center = left + (WHITE_KEY_WIDTH / 2);
                            geometry[i] = {{ left: left, width: WHITE_KEY_WIDTH, center: center, isBlack: false }};
                            wIndex++;
                        }}
                    }}
                    // Pass B: Calculate Black Keys perfectly on the seams
                    for (let i = 21; i <= 108; i++) {{
                        if (!geometry[i]) {{
                            const leftWhite = geometry[i - 1];
                            const bWidth = WHITE_KEY_WIDTH * 0.65;
                            const center = leftWhite.left + leftWhite.width; // The exact seam between keys
                            const left = center - (bWidth / 2);
                            geometry[i] = {{ left: left, width: bWidth, center: center, isBlack: true }};
                        }}
                    }}

                    // 2. RENDER KEYBOARD
                    for (let i = 21; i <= 108; i++) {{
                        const key = document.createElement('div');
                        key.id = 'key-' + i;
                        key.className = geometry[i].isBlack ? 'black-key' : 'white-key';
                        key.style.width = geometry[i].width + '%';
                        key.style.left = geometry[i].left + '%';
                        piano.appendChild(key);
                    }}

                    // 3. RENDER FALLING NOTES (Bound strictly to True Centers)
                    const noteElements = notes.map(n => {{
                        const el = document.createElement('div');
                        const geo = geometry[n.MIDI];
                        const noteWidth = geo.isBlack ? 0.8 : 1.2; // Notes are slightly thinner than the keys
                        
                        el.style.position = 'absolute';
                        el.style.width = noteWidth + '%';
                        // Center math: Left edge = center point - half the width
                        el.style.left = 'calc(' + geo.center + '% - ' + (noteWidth / 2) + '%)';
                        
                        el.style.background = 'linear-gradient(to top, #10b981, #047857)';
                        el.style.border = '1px solid #000';
                        el.style.boxShadow = '0 0 10px rgba(16, 185, 129, 0.6)';
                        el.style.borderRadius = '3px';
                        
                        const height = (n['End Time (s)'] - n['Start Time (s)']) * PIXELS_PER_SEC;
                        el.style.height = height + 'px';
                        
                        const initialBottom = n['Start Time (s)'] * PIXELS_PER_SEC;
                        el.style.bottom = initialBottom + 'px';
                        
                        document.getElementById('note-stream').appendChild(el);
                        return {{ el, start: n['Start Time (s)'], end: n['End Time (s)'], midi: n.MIDI, initialBottom }};
                    }});

                    // 4. HARDWARE ACCELERATED SYNC
                    playBtn.onclick = () => {{
                        if (audio.paused) {{ audio.play(); playBtn.innerText = '⏸ PAUSE'; }}
                        else {{ audio.pause(); playBtn.innerText = '▶ START LESSON'; }}
                    }};

                    function animate() {{
                        const t = audio.currentTime;
                        status.innerText = t.toFixed(2) + 's';

                        const activeMidis = new Set();
                        const scrollOffset = t * PIXELS_PER_SEC;

                        noteElements.forEach(n => {{
                            n.el.style.transform = 'translateY(' + scrollOffset + 'px)';
                            if (t >= n.start && t <= n.end) activeMidis.add(n.midi);
                        }});

                        for (let i = 21; i <= 108; i++) {{
                            const k = document.getElementById('key-' + i);
                            if (!k) continue;

                            if (activeMidis.has(i)) {{
                                k.style.background = '#00ff00';
                                k.style.boxShadow = '0 0 20px #00ff00';
                                k.style.transform = 'translateY(2px)';
                            }} else {{
                                k.style.background = geometry[i].isBlack ? 'linear-gradient(#333, #000)' : 'linear-gradient(#ddd, #fff)';
                                k.style.boxShadow = 'none';
                                k.style.transform = 'none';
                            }}
                        }}
                        requestAnimationFrame(animate);
                    }}
                    animate();
                </script>
                """
                components.html(html_code, height=900)
                st.markdown("---")
                st.subheader("💾 Export Transcription")
                st.write("Download the AI-filtered notes as a playable MIDI file.")
                
                midi_data = create_midi_bytes(data)
                
                st.download_button(
                    label="🎵 Download MIDI File",
                    data=midi_data,
                    file_name="cleaned_transcription.mid",
                    mime="audio/midi"
                )

        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)