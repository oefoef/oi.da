# 🎛️ Endless Mix - Web Audio API Documentation

## Overview

This implementation provides a **professional-grade Web Audio API engine** with:
- ✅ Real browser audio output (not simulation)
- ✅ Multi-source integration (Suno, Google Drive, Local Files)
- ✅ Real-time visualization (waveform/spectrum)
- ✅ DSP chain (EQ, Compressor, Panner)
- ✅ Automatic crossfading & harmonic mixing
- ✅ 3D spatial audio positioning

---

## Architecture

### 1. **AudioSourceManager** (endless-mix-audio-engine.js)

Handles audio loading and playback from multiple sources.

#### Key Methods:

```javascript
// Load from URL
await audioEngine.loadAudioFromURL(url, sourceId)

// Load Suno playlist
await audioEngine.loadFromSunoPlaylist(playlistUrl)
// URL: https://suno.com/playlist/a6bb7b74-4801-4907-befb-c532aeede1f5

// Load from Google Drive folder
await audioEngine.loadFromGoogleDrive(folderId)
// Extract ID from: https://drive.google.com/drive/folders/1dkv84ghTxADtyKhErXFrKfG5QkUVGPOi

// Load local file
await audioEngine.loadLocalFile(file)

// Control playback
audioEngine.setVolume(70)        // 0-100
audioEngine.setSpatialPosition(45) // -90 to +90 degrees
audioEngine.setEQBand(0, 6)       // Band index, gain in dB
```

#### DSP Effects Chain:
```
[Input] → [EQ (3-Band)] → [Compressor] → [Stereophonic Panner] → [Output]
  Bass        Mids         Dynamics         3D Spatial
  100Hz      1kHz          Control         Audio
```

---

### 2. **DJMixingEngine** (endless-mix-audio-engine.js)

Automated mixing with harmonic analysis and crossfading.

```javascript
const mixer = new DJMixingEngine(audioEngine);

// Queue tracks for continuous playback
mixer.queueTracks(trackArray);

// Play with automatic crossfading
await mixer.playWithCrossfade();

// Harmonic compatibility ranking
const sorted = mixer.rankByHarmony(tracks, referenceTrack);
```

#### Features:
- **Automatic BPM Detection**: Analyzes onset frequency
- **Harmonic Key Detection**: Uses chroma features
- **Intelligent Sequencing**: Ranks by compatibility score
- **Crossfading**: Smooth transitions (adjustable 2-15s)

---

### 3. **AudioVisualizer** (endless-mix-audio-engine.js)

Real-time audio visualization.

```javascript
const viz = new AudioVisualizer(canvasElement, audioEngine);

// Start visualization
viz.start('waveform');  // or 'spectrum'
viz.stop();
```

---

## Integration Guide

### Setup (Minimal)

```html
<script src="endless-mix-audio-engine.js"></script>
<script>
    // Initialize on user interaction
    let audioEngine = new AudioSourceManager();
    audioEngine.resumeContext(); // Required by browser policy
</script>
```

### Load Suno Playlist

```javascript
const url = 'https://suno.com/playlist/a6bb7b74-4801-4907-befb-c532aeede1f5';
const tracks = await audioEngine.loadFromSunoPlaylist(url);
// Returns: [{ title, artist, duration, bpm, key, buffer }, ...]
```

**Note**: Requires CORS workaround. Engine uses fallback proxies:
1. Direct fetch
2. cors-anywhere.herokuapp.com
3. allorigins.win

### Load Google Drive Folder

```javascript
const folderId = '1dkv84ghTxADtyKhErXFrKfG5QkUVGPOi';
const tracks = await audioEngine.loadFromGoogleDrive(folderId);
// Requires: Google Drive API key configured in engine
```

**Setup Google Drive API:**
1. Enable Google Drive API in Google Cloud Console
2. Create Service Account or OAuth credential
3. Set `audioEngine.googleApiKey = 'YOUR_KEY'`

### Load Local Files

```javascript
const file = document.getElementById('fileInput').files[0];
const track = await audioEngine.loadLocalFile(file);
// Works with: MP3, WAV, OGG, FLAC, AAC
```

---

## Features Breakdown

### Real-Time Audio Output

❌ **Before** (Simulation):
```javascript
function simulatePlayback() {
    playbackTime += 0.1;
    document.getElementById('trackProgress').style.width = progress + '%';
}
// ⚠️ No actual audio signal to speaker
```

✅ **Now** (Web Audio API):
```javascript
const source = audioContext.createBufferSource();
source.buffer = audioBuffer;
source.connect(masterGain);
source.start(audioContext.currentTime);
// 🔊 Real audio output to speakers
```

### Multi-Source Support

| Source | Method | Example URL |
|--------|--------|-------------|
| **Suno** | `loadFromSunoPlaylist()` | https://suno.com/playlist/a6bb7b74... |
| **Google Drive** | `loadFromGoogleDrive()` | Folder ID: 1dkv84ghTxADtyKhErXFrKfG5QkUVGPOi |
| **Local** | `loadLocalFile()` | File picker input |
| **Direct URL** | `loadAudioFromURL()` | Any accessible MP3/WAV/OGG |

### DSP Effects

#### 3-Band EQ
```javascript
audioEngine.setEQBand(0, 6);   // Bass +6dB
audioEngine.setEQBand(1, 0);   // Mids flat
audioEngine.setEQBand(2, -3);  // Treble -3dB
```

#### Dynamic Range Compression
```
Threshold: -30 dB
Ratio: 12:1
Attack: 3ms
Release: 250ms
```
Prevents clipping and maximizes loudness.

#### Stereophonic Panning
```javascript
audioEngine.setSpatialPosition(-45); // 45° to the left
audioEngine.setSpatialPosition(0);   // Center
audioEngine.setSpatialPosition(90);  // 90° to the right
```

### Visualization

#### Spectrum Analyzer
- Real-time FFT-based frequency display
- 512-bin frequency resolution
- HSL color gradient mapping

#### Waveform Display
- Time-domain waveform rendering
- 2048-sample FFT buffer
- Amber color (#f59e0b)

---

## Troubleshooting

### No Audio Output

1. **Check browser console** for errors
2. **Verify** `audioContext.state === 'running'`
3. **Resume context** after user interaction:
   ```javascript
   audioEngine.audioContext.resume();
   ```
4. **Check volume** slider not at 0%
5. **Test** system audio is not muted

### CORS Errors Loading Remote Audio

**Solution**: Engine automatically falls back to CORS proxies. If still failing:

```javascript
// Use direct proxy URL
const proxyUrl = `https://api.allorigins.win/get?url=${encodeURIComponent(audioUrl)}`;
await audioEngine.loadAudioFromURL(proxyUrl, sourceId);
```

### Suno Playlist Returns Empty

1. Verify playlist is public
2. Check URL format: `https://suno.com/playlist/[PLAYLIST_ID]`
3. Try alternative CORS proxy

### Google Drive Fails

1. **Ensure folder is shared** (public or with proper permissions)
2. **Get API Key**:
   - Go to Google Cloud Console
   - Enable Drive API
   - Create Service Account
3. **Set in code**:
   ```javascript
   audioEngine.googleApiKey = 'YOUR_API_KEY_HERE';
   ```

---

## Performance Optimization

### Memory
- AudioBuffers cached in `audioEngine.sources` Map
- Use `.stop()` on sources to free memory
- Consider file size: 3MB MP3 ≈ 30s @ 320kbps

### CPU
- EQ uses biquad filters (O(1))
- Compressor uses efficient peak detection
- Visualization runs at 60fps (requestAnimationFrame)

### Latency
- Min: ~50ms (Web Audio API)
- Crossfade: Configurable 2-15 seconds
- No network delay for local files

---

## Browser Support

| Feature | Chrome | Firefox | Safari | Edge |
|---------|--------|---------|--------|------|
| Web Audio API | ✅ | ✅ | ✅ | ✅ |
| File Input | ✅ | ✅ | ✅ | ✅ |
| Fetch API | ✅ | ✅ | ✅ | ✅ |
| AudioContext | ✅ | ✅ | ✅ (webkit) | ✅ |

---

## API Reference

### AudioSourceManager

```typescript
class AudioSourceManager {
    audioContext: AudioContext
    masterGain: GainNode
    
    loadAudioFromURL(url: string, sourceId: string): Promise<AudioBuffer>
    loadFromSunoPlaylist(playlistUrl: string): Promise<Track[]>
    loadFromGoogleDrive(folderId: string): Promise<Track[]>
    loadLocalFile(file: File): Promise<Track>
    
    playBuffer(buffer: AudioBuffer, startTime?: number): AudioBufferSourceNode
    setVolume(value: number): void  // 0-100
    setSpatialPosition(azimuth: number): void  // -90 to 90
    setEQBand(bandIndex: number, gainDb: number): void
    
    getFrequencyData(): Uint8Array
    getWaveformData(): Uint8Array
    resumeContext(): void
}
```

### DJMixingEngine

```typescript
class DJMixingEngine {
    queueTracks(tracks: Track[]): void
    playWithCrossfade(): Promise<void>
    performCrossfade(duration: number): void
    detectBPM(buffer: AudioBuffer): number
    analyzeHarmony(buffer: AudioBuffer): string
    rankByHarmony(tracks: Track[], referenceTrack: Track): Track[]
    pause(): void
    stop(): void
}
```

### AudioVisualizer

```typescript
class AudioVisualizer {
    drawSpectrum(): void
    drawWaveform(): void
    start(mode: 'spectrum' | 'waveform'): void
    stop(): void
}
```

---

## Examples

### Complete Playlist Mixer

```javascript
// 1. Initialize
const audioEngine = new AudioSourceManager();
const mixer = new DJMixingEngine(audioEngine);

// 2. Load from Suno
const sunoTracks = await audioEngine.loadFromSunoPlaylist(
    'https://suno.com/playlist/a6bb7b74-4801-4907-befb-c532aeede1f5'
);

// 3. Load from Google Drive
const driveTracks = await audioEngine.loadFromGoogleDrive(
    '1dkv84ghTxADtyKhErXFrKfG5QkUVGPOi'
);

// 4. Combine and sort by harmony
const allTracks = [...sunoTracks, ...driveTracks];
const sorted = mixer.rankByHarmony(allTracks, sunoTracks[0]);

// 5. Queue and play
mixer.queueTracks(sorted);
await mixer.playWithCrossfade();
```

---

## Future Enhancements

- [ ] LUFS metering (ITU-R BS.1770-4)
- [ ] Advanced HRTF 3D binaural rendering
- [ ] Real-time pitch detection (Yin algorithm)
- [ ] Beat-synced effects (delay, reverb)
- [ ] Vinyl turntable emulation
- [ ] Deck automation recording

---

**Made with ❤️ for the Oidasheim crowd 🎵**
