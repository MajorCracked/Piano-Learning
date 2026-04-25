import warnings
warnings.filterwarnings("ignore")
import os
import sys
import shutil
import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
import base64
import io
import mido
import music21 as m21
import subprocess
from src.polyphonic_engine import transcribe_polyphonic, note_name_to_midi

if "pipeline_complete" not in st.session_state:
    st.session_state.pipeline_complete = False
if "transcription_data" not in st.session_state:
    st.session_state.transcription_data = None
if "midi_data" not in st.session_state:
    st.session_state.midi_data = None
if "xml_data" not in st.session_state:
    st.session_state.xml_data = None
if "original_audio_b64" not in st.session_state:
    st.session_state.original_audio_b64 = None
if "processed_audio_b64" not in st.session_state:
    st.session_state.processed_audio_b64 = None
if "mime_type" not in st.session_state:
    st.session_state.mime_type = None


def isolate_piano_stem(audio_path):
    """Runs Facebook's Demucs AI to strip vocals, bass, and drums from a pop song."""
    out_dir = "separated_stems"
    os.makedirs(out_dir, exist_ok=True)
    
    command = [
        sys.executable, "-m", "demucs.separate",
        "-n", "htdemucs",
        "--out", out_dir,
        audio_path
    ]
    subprocess.run(command, check=True)
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    piano_stem_path = os.path.join(out_dir, "htdemucs", base_name, "other.wav")
    return piano_stem_path

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

def create_musicxml_bytes(transcription_data):
    """Converts AI data into a Piano Grand Staff and runs automated Chord Analysis."""
    score = m21.stream.Score()

    try:
        all_pitches = [note_name_to_midi(item['Note']) for item in transcription_data]
        unique_pitches = list(set(all_pitches))
        dynamic_split = sum(unique_pitches) / len(unique_pitches) if unique_pitches else 60
    except Exception:
        dynamic_split = 60

    right_part = m21.stream.Part()
    right_part.partName = 'Piano (RH)'
    right_part.insert(0, m21.clef.TrebleClef())
    right_part.insert(0, m21.meter.TimeSignature('4/4'))
    
    left_part = m21.stream.Part()
    left_part.partName = 'Piano (LH)'
    left_part.insert(0, m21.clef.BassClef())
    left_part.insert(0, m21.meter.TimeSignature('4/4'))
    
    staff_group = m21.layout.StaffGroup([right_part, left_part], name='Piano', symbol='brace')
    score.insert(0, staff_group)

    for item in transcription_data:
        start_time = item['Start Time (s)']
        duration_sec = item['End Time (s)'] - start_time
        if duration_sec < 0.05:
            continue

        duration_beats = max(0.25, round(duration_sec / 0.5 * 4) / 4)
        offset_beats = round(start_time / 0.5 * 4) / 4
        
        try:
            n = m21.note.Note(item['Note'])
            n.quarterLength = duration_beats
            if n.pitch.midi >= dynamic_split:
                right_part.insert(offset_beats, n)
            else:
                left_part.insert(offset_beats, n)
        except Exception:
            continue 

    score.insert(0, right_part)
    score.insert(0, left_part)

    try:
        chords = score.chordify()
        for c in chords.recurse().getElementsByClass('Chord'):
            if len(c.pitches) >= 2: # Only label 2+ note chords
                chord_name = c.pitchedCommonName
                if chord_name:
                    chord_symbol = m21.expressions.TextExpression(chord_name)
                    chord_symbol.placement = 'above'
                    right_part.insert(c.offset, chord_symbol)
    except Exception as e:
        print(f"Chord analysis skipped: {e}")

    exporter = m21.musicxml.m21ToXml.GeneralObjectExporter(score)
    return exporter.parse()

st.set_page_config(page_title="Piano Learning Lab", page_icon="🎹", layout="wide")

st.title("🎹 Piano Learning Lab")
st.write("Upload your performance (.wav or .mp3) to generate an interactive, synchronized tutorial.")

uploaded_file = st.file_uploader("Upload .wav or .mp3 performance", type=["wav", "mp3"])
isolate_stems = st.toggle("🎧 Advanced: Strip Vocals & Drums (Turn on for full pop songs)")

with st.sidebar:
    st.header("🎛️ AI Tuning Engine")
    st.write("Tune the neural network to filter out acoustic echoes and MP3 compression artifacts.")
    noise_slider = st.slider("Noise Gate (Velocity)", min_value=0, max_value=80, value=40, step=5)
    duration_slider = st.slider("Minimum Note Length (s)", min_value=0.01, max_value=0.20, value=0.05, step=0.01)
    max_duration_slider = st.slider("Pedal Override (Max Length)", min_value=0.2, max_value=4.0, value=1.0, step=0.1)
    st.markdown("---")


@st.cache_data(show_spinner=False)
def run_cached_pipeline(file_name, file_bytes, isolate, noise, min_dur, max_dur):
    """The Vault: Runs AI, extracts audio, and wipes the server instantly."""
    os.makedirs("data", exist_ok=True)
    temp_path = os.path.join("data", f"temp_{file_name}")
    with open(temp_path, "wb") as f:
        f.write(file_bytes)

    if isolate:
        processing_path = isolate_piano_stem(temp_path)
    else:
        processing_path = temp_path

    with open(processing_path, "rb") as f:
        processed_bytes = f.read()
        
    transcription_data = transcribe_polyphonic(
        processing_path, noise_gate=noise, min_duration=min_dur, max_duration=max_dur
    )

    # Clean up server
    if os.path.exists(temp_path):
        os.remove(temp_path)
    if os.path.exists("separated_stems"):
        shutil.rmtree("separated_stems")
        
    return transcription_data, processed_bytes


if uploaded_file is not None:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    mime_type = "audio/mpeg" if file_ext == "mp3" else "audio/wav"
    audio_bytes = uploaded_file.read()

    if st.button("Generate Transcription", use_container_width=True):
        
        status_container = st.status("🤖 AI Pipeline Active...", expanded=True)
        status_container.write("1️⃣ Processing audio (Isolating stems & extracting notes)...")
        
        # Run Vault
        data, processed_bytes = run_cached_pipeline(
            uploaded_file.name, audio_bytes, isolate_stems, noise_slider, duration_slider, max_duration_slider
        )
        
        status_container.write("2️⃣ Transcoding MIDI & Sheet Music...")

        st.session_state.transcription_data = data
        st.session_state.original_audio_b64 = base64.b64encode(audio_bytes).decode()
        st.session_state.processed_audio_b64 = base64.b64encode(processed_bytes).decode()
        st.session_state.mime_type = mime_type
        
        st.session_state.midi_data = create_midi_bytes(data)
        st.session_state.xml_data = create_musicxml_bytes(data)
        st.session_state.pipeline_complete = True
        
        status_container.update(label="✅ Multi-Stage AI Pipeline Complete!", state="complete", expanded=False)
        st.rerun()

if st.session_state.pipeline_complete:
    
    # 1. AUDIO COMPARISON
    st.subheader("🎧 Acoustic Evaluation (Original vs AI)")
    col_aud1, col_aud2 = st.columns(2)
    with col_aud1:
        st.markdown("**Original Upload**")
        st.audio(base64.b64decode(st.session_state.original_audio_b64), format=st.session_state.mime_type)
    with col_aud2:
        st.markdown("**Isolated Piano Stem** (AI Output)")
        # If stems weren't isolated, this just plays the original file again
        audio_format = "audio/wav" if isolate_stems else st.session_state.mime_type
        st.audio(base64.b64decode(st.session_state.processed_audio_b64), format=audio_format)

    st.markdown("---")

    # 2. VISUALIZER
    df = pd.DataFrame(st.session_state.transcription_data)
    df['MIDI'] = df['Note'].apply(note_name_to_midi)
    notes_json = df.to_json(orient='records')
    
    # Render visualizer using the PROCESSED audio so they hear the clean piano!
    html_code = f"""
    <style>
        * {{ box-sizing: border-box; }}
        body {{ background: #0b0b0b; margin: 0; font-family: 'Inter', sans-serif; color: white; overflow: hidden; }}
        #main-wrapper {{ display: flex; flex-direction: column; height: 850px; background: #000; border: 1px solid #333; }}
        #visualizer {{ flex-grow: 1; position: relative; overflow: hidden; background: #000; }}
        #impact-bar {{ position: absolute; bottom: 0; width: 100%; height: 4px; background: #00ff00; box-shadow: 0 0 20px #00ff00; z-index: 100; }}
        #keyboard-container {{ position: relative; height: 180px; background: #111; border-top: 2px solid #333; }}
        
        .white-key {{ position: absolute; height: 100%; background: linear-gradient(#ddd, #fff); border: 1px solid #777; border-radius: 0 0 5px 5px; z-index: 1; box-shadow: inset 0 -5px 10px rgba(0,0,0,0.1); transition: background 0.05s, transform 0.05s; }}
        .black-key {{ position: absolute; height: 60%; background: linear-gradient(#333, #000); z-index: 2; border-radius: 0 0 4px 4px; border: 1px solid #111; box-shadow: 2px 4px 8px rgba(0,0,0,0.6); transition: background 0.05s, transform 0.05s; }}

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
            <audio id="audio-engine" src="data:audio/wav;base64,{st.session_state.processed_audio_b64}"></audio>
        </div>
    </div>

    <script>
        const notes = {notes_json};
        const audio = document.getElementById('audio-engine');
        const playBtn = document.getElementById('play-btn');
        const status = document.getElementById('status');
        const piano = document.getElementById('keyboard-target');
        const PIXELS_PER_SEC = 250;
        const geometry = {{}};
        const WHITE_KEY_WIDTH = 100 / 52;
        let wIndex = 0;

        for (let i = 21; i <= 108; i++) {{
            const isBlack = [1, 3, 6, 8, 10].includes(i % 12);
            if (!isBlack) {{
                const left = wIndex * WHITE_KEY_WIDTH;
                const center = left + (WHITE_KEY_WIDTH / 2);
                geometry[i] = {{ left: left, width: WHITE_KEY_WIDTH, center: center, isBlack: false }};
                wIndex++;
            }}
        }}
        for (let i = 21; i <= 108; i++) {{
            if (!geometry[i]) {{
                const leftWhite = geometry[i - 1];
                const bWidth = WHITE_KEY_WIDTH * 0.65;
                const center = leftWhite.left + leftWhite.width;
                const left = center - (bWidth / 2);
                geometry[i] = {{ left: left, width: bWidth, center: center, isBlack: true }};
            }}
        }}
        for (let i = 21; i <= 108; i++) {{
            const key = document.createElement('div');
            key.id = 'key-' + i;
            key.className = geometry[i].isBlack ? 'black-key' : 'white-key';
            key.style.width = geometry[i].width + '%';
            key.style.left = geometry[i].left + '%';
            piano.appendChild(key);
        }}

        const noteElements = notes.map(n => {{
            const el = document.createElement('div');
            const geo = geometry[n.MIDI];
            const noteWidth = geo.isBlack ? 0.8 : 1.2; 
            el.style.position = 'absolute';
            el.style.width = noteWidth + '%';
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
    st.subheader("💾 Export & View Sheet Music (With Chord Analysis)")
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="🎵 Download MIDI File",
            data=st.session_state.midi_data,
            file_name="ai_transcription.mid",
            mime="audio/midi",
            use_container_width=True
        )  
    with col2:
        st.download_button(
            label="🎼 Download Source XML",
            data=st.session_state.xml_data,
            file_name="ai_sheet_music.xml",
            mime="application/vnd.recordare.musicxml",
            use_container_width=True
        )
        
    st.markdown("### 📄 Live Viewer & PDF Export")
    b64_xml = base64.b64encode(st.session_state.xml_data).decode('utf-8')
    
    sheet_music_html = f"""
    <script src="https://cdn.jsdelivr.net/npm/opensheetmusicdisplay@1.8.8/build/opensheetmusicdisplay.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    
    <div style="text-align: right; margin-bottom: 15px;">
        <button id="download-pdf" style="background-color: #FF4B4B; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-family: sans-serif; font-size: 14px; font-weight: 600; cursor: pointer; box-shadow: 0px 2px 5px rgba(0,0,0,0.2);">
            📑 Download as PDF
        </button>
    </div>

    <div id="sheet-music" style="background-color: white; padding: 30px; border-radius: 10px;"></div>
    
    <script>
    var osmd = new opensheetmusicdisplay.OpenSheetMusicDisplay("sheet-music", {{
        drawingParameters: "compacttight",
        drawTitle: false
    }});
    var xmlString = atob("{b64_xml}");
    osmd.load(xmlString).then(function() {{
        osmd.render();
    }});
    document.getElementById('download-pdf').addEventListener('click', function() {{
        var element = document.getElementById('sheet-music');
        var opt = {{
            margin:       0.5,
            filename:     'AI_Transcription.pdf',
            image:        {{ type: 'jpeg', quality: 0.98 }},
            html2canvas:  {{ scale: 2 }},
            jsPDF:        {{ unit: 'in', format: 'letter', orientation: 'portrait' }}
        }};
        this.innerText = "⏳ Generating PDF...";
        
        html2pdf().set(opt).from(element).save().then(() => {{
            this.innerText = "📑 Download as PDF";
        }});
    }});
    </script>
    """
    components.html(sheet_music_html, height=750, scrolling=True)