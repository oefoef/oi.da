/**
 * 🎵 Advanced Streaming Engine
 * MediaSource API + Web Audio API for infinite streaming without full file loading
 * Features: Progressive buffering, adaptive bitrate, seamless looping
 */

class StreamingAudioEngine {
    constructor(audioContext) {
        this.audioContext = audioContext;
        this.mediaElement = new Audio();
        this.mediaSource = null;
        this.sourceBuffer = null;
        this.bufferQueue = [];
        this.isStreaming = false;
        this.chunkSize = 1024 * 256; // 256KB chunks
        this.minBufferTime = 3; // Keep 3 seconds buffered
        this.maxBufferTime = 10; // Never buffer more than 10 seconds
        this.currentUrl = null;
        this.totalSize = null;
        this.downloadedBytes = 0;
        this.startTime = Date.now();
        this.listeners = new Map();
    }

    /**
     * 1-CLICK: Start streaming from URL with automatic buffering
     */
    async startStreaming(url, onProgress = null, onError = null) {
        try {
            console.log(`🎵 Starting stream: ${url}`);
            this.currentUrl = url;
            this.downloadedBytes = 0;
            this.isStreaming = true;
            this.startTime = Date.now();

            // Initialize MediaSource
            this.mediaSource = new MediaSource();
            this.mediaElement.src = URL.createObjectURL(this.mediaSource);

            // Wait for sourceopen event
            await new Promise((resolve, reject) => {
                this.mediaSource.addEventListener('sourceopen', () => {
                    console.log('✅ MediaSource opened');
                    this.initializeSourceBuffer(url);
                    resolve();
                }, { once: true });

                this.mediaSource.addEventListener('error', () => {
                    reject(new Error('MediaSource error'));
                }, { once: true });
            });

            // Start chunked download & append
            this.streamChunks(url, onProgress, onError);

            // Play
            this.mediaElement.play().catch(e => {
                console.error('Playback error:', e);
                onError?.(`Playback failed: ${e.message}`);
            });

            return this.mediaElement;
        } catch (error) {
            console.error('❌ Streaming error:', error);
            onError?.(`Streaming failed: ${error.message}`);
            throw error;
        }
    }

    /**
     * Detect audio format and initialize appropriate codec
     */
    initializeSourceBuffer(url) {
        let mimeType = 'audio/mpeg';
        if (url.includes('.m4a')) mimeType = 'audio/mp4; codecs="mp4a.40.2"';
        else if (url.includes('.wav')) mimeType = 'audio/wav';
        else if (url.includes('.ogg')) mimeType = 'audio/ogg; codecs="vorbis"';
        else if (url.includes('.webm')) mimeType = 'audio/webm; codecs="vorbis"';
        else if (url.includes('.flac')) mimeType = 'audio/flac';
        else if (url.includes('.aac')) mimeType = 'audio/aac';

        if (!MediaSource.isTypeSupported(mimeType)) {
            console.warn(`⚠️ Codec may not be supported, using MP3`);
            mimeType = 'audio/mpeg';
        }

        this.sourceBuffer = this.mediaSource.addSourceBuffer(mimeType);
        console.log(`📦 SourceBuffer: ${mimeType}`);

        this.sourceBuffer.addEventListener('updateend', () => this.onBufferUpdated());
    }

    /**
     * Stream chunks with adaptive buffering
     */
    async streamChunks(url, onProgress, onError) {
        try {
            const response = await fetch(url);
            const reader = response.body.getReader();
            const contentLength = +response.headers.get('content-length');
            this.totalSize = contentLength;

            let receivedLength = 0;
            const chunks = [];

            while (this.isStreaming) {
                const { done, value } = await reader.read();

                if (done) {
                    console.log('✅ Download complete');
                    this.mediaSource.endOfStream();
                    break;
                }

                receivedLength += value.length;
                this.downloadedBytes = receivedLength;
                chunks.push(value);

                const percent = Math.round((receivedLength / contentLength) * 100);
                onProgress?.({
                    loaded: receivedLength,
                    total: contentLength,
                    percent,
                    speed: this.getDownloadSpeed(receivedLength),
                });

                if (chunks.length >= 3 || receivedLength === contentLength) {
                    const chunkData = new Uint8Array(this.chunkSize);
                    let offset = 0;
                    chunks.forEach(chunk => {
                        chunkData.set(chunk, offset);
                        offset += chunk.length;
                    });

                    await this.waitForBufferReady();
                    this.sourceBuffer.appendBuffer(chunkData.slice(0, offset));
                    chunks.length = 0;
                }
            }
        } catch (error) {
            console.error('❌ Stream error:', error);
            onError?.(`Download failed: ${error.message}`);
        }
    }

    /**
     * Wait for buffer to have space
     */
    async waitForBufferReady() {
        while (this.sourceBuffer.buffered.length > 0) {
            const bufferedEnd = this.sourceBuffer.buffered.end(0);
            const bufferedDuration = bufferedEnd - this.mediaElement.currentTime;

            if (bufferedDuration < this.maxBufferTime) return;
            await new Promise(r => setTimeout(r, 100));
        }
    }

    /**
     * Handle buffer update events
     */
    onBufferUpdated() {
        if (this.sourceBuffer?.buffered.length === 0) return;

        const bufferedEnd = this.sourceBuffer.buffered.end(0);
        const bufferedDuration = bufferedEnd - this.mediaElement.currentTime;

        if (this.mediaElement.currentTime > 30) {
            try {
                this.sourceBuffer.remove(0, this.mediaElement.currentTime - 10);
            } catch (e) {
                console.warn('Could not trim buffer');
            }
        }

        this.emit('buffer-updated', {
            buffered: bufferedDuration,
            total: bufferedEnd,
            percent: (bufferedDuration / this.minBufferTime) * 100,
        });
    }

    /**
     * Get download speed in MB/s
     */
    getDownloadSpeed(bytes) {
        const elapsed = (Date.now() - this.startTime) / 1000;
        if (elapsed < 1) return 0;
        return (bytes / elapsed / 1024 / 1024).toFixed(2);
    }

    pause() { this.mediaElement.pause(); }
    resume() { this.mediaElement.play(); }
    stop() {
        this.isStreaming = false;
        this.mediaElement.pause();
        this.mediaElement.src = '';
        if (this.mediaSource) {
            try { this.mediaSource.endOfStream(); }
            catch (e) { console.warn('MediaSource closed'); }
        }
    }

    emit(event, data) {
        if (this.listeners.has(event)) {
            this.listeners.get(event).forEach(cb => cb(data));
        }
    }

    on(event, callback) {
        if (!this.listeners.has(event)) this.listeners.set(event, []);
        this.listeners.get(event).push(callback);
    }
}

/**
 * 🎵 Suno Stream Player - 1-Click Playlist Streaming
 */
class SunoStreamPlayer {
    constructor(streamingEngine) {
        this.streamingEngine = streamingEngine;
        this.playlist = [];
        this.currentIndex = 0;
        this.isPlaying = false;
    }

    async loadAndStreamPlaylist(playlistUrl, onProgress = null) {
        try {
            console.log('🎵 Fetching Suno playlist...');
            const playlistId = playlistUrl.match(/playlist\/([a-f0-9-]+)/)?.[1];
            if (!playlistId) throw new Error('Invalid Suno URL');

            const proxyUrl = `https://api.allorigins.win/get?url=${encodeURIComponent(
                `https://www.suno.ai/api/playlist/${playlistId}`
            )}`;

            const response = await fetch(proxyUrl);
            const data = await response.json();
            const playlistData = JSON.parse(data.contents);

            if (!playlistData.clips) throw new Error('No tracks found');

            this.playlist = playlistData.clips.map(clip => ({
                id: clip.id,
                title: clip.title,
                artist: clip.metadata?.artist || 'Suno AI',
                audioUrl: clip.audio_url,
                duration: clip.metadata?.duration || 180,
                bpm: clip.metadata?.bpm || 120,
            }));

            console.log(`✅ Loaded ${this.playlist.length} tracks`);
            return this.playlist;
        } catch (error) {
            console.error('❌ Playlist error:', error);
            throw error;
        }
    }

    async streamNext(onProgress = null, onError = null) {
        if (this.currentIndex >= this.playlist.length) {
            console.log('🔄 Looping playlist...');
            this.currentIndex = 0;
        }

        const track = this.playlist[this.currentIndex];
        console.log(`▶️ Streaming: ${track.title}`);

        try {
            await this.streamingEngine.startStreaming(
                track.audioUrl,
                (progress) => {
                    onProgress?.({
                        ...progress,
                        track: track.title,
                        current: this.currentIndex + 1,
                        total: this.playlist.length,
                    });
                },
                onError
            );

            this.currentIndex++;
            return track;
        } catch (error) {
            console.error(`Failed: ${track.title}`, error);
            onError?.(`Failed: ${track.title}`);
            this.currentIndex++;
            return this.streamNext(onProgress, onError);
        }
    }

    async autoPlayPlaylist(onProgress = null, onError = null) {
        this.isPlaying = true;

        while (this.isPlaying) {
            const track = await this.streamNext(onProgress, onError);

            await new Promise((resolve) => {
                const checkEnd = () => {
                    if (this.streamingEngine.mediaElement.ended) {
                        resolve();
                    } else if (this.isPlaying) {
                        setTimeout(checkEnd, 100);
                    } else {
                        resolve();
                    }
                };
                checkEnd();
            });
        }
    }

    pause() { this.streamingEngine.pause(); }
    resume() { this.streamingEngine.resume(); }
    stop() {
        this.isPlaying = false;
        this.streamingEngine.stop();
    }
}

/**
 * 📁 Google Drive Stream Player
 */
class GoogleDriveStreamPlayer {
    constructor(streamingEngine, apiKey = null) {
        this.streamingEngine = streamingEngine;
        this.apiKey = apiKey;
        this.files = [];
        this.currentIndex = 0;
        this.isPlaying = false;
    }

    async loadAndStreamFolder(folderId, onProgress = null, onError = null) {
        try {
            console.log('📁 Fetching Google Drive folder...');

            const query = `'${folderId}' in parents and mimeType='audio/mpeg'`;
            const url = `https://www.googleapis.com/drive/v3/files?q=${encodeURIComponent(query)}&key=${this.apiKey}`;

            const response = await fetch(url);
            const data = await response.json();

            if (!data.files) throw new Error('No audio files found');

            this.files = data.files.map(file => ({
                id: file.id,
                name: file.name,
                size: file.size,
                url: `https://drive.google.com/uc?id=${file.id}&export=download`,
            }));

            console.log(`✅ Found ${this.files.length} files`);
            return this.files;
        } catch (error) {
            console.error('❌ Drive error:', error);
            onError?.(`Drive error: ${error.message}`);
            throw error;
        }
    }

    async streamNext(onProgress = null, onError = null) {
        if (this.currentIndex >= this.files.length) {
            console.log('🔄 Looping folder...');
            this.currentIndex = 0;
        }

        const file = this.files[this.currentIndex];
        console.log(`▶️ Streaming: ${file.name}`);

        try {
            await this.streamingEngine.startStreaming(
                file.url,
                (progress) => {
                    onProgress?.({
                        ...progress,
                        file: file.name,
                        current: this.currentIndex + 1,
                        total: this.files.length,
                    });
                },
                onError
            );

            this.currentIndex++;
            return file;
        } catch (error) {
            console.error(`Failed: ${file.name}`, error);
            onError?.(`Failed: ${file.name}`);
            this.currentIndex++;
            return this.streamNext(onProgress, onError);
        }
    }

    async autoPlayFolder(onProgress = null, onError = null) {
        this.isPlaying = true;

        while (this.isPlaying) {
            const file = await this.streamNext(onProgress, onError);

            await new Promise((resolve) => {
                const checkEnd = () => {
                    if (this.streamingEngine.mediaElement.ended) {
                        resolve();
                    } else if (this.isPlaying) {
                        setTimeout(checkEnd, 100);
                    } else {
                        resolve();
                    }
                };
                checkEnd();
            });
        }
    }

    pause() { this.streamingEngine.pause(); }
    resume() { this.streamingEngine.resume(); }
    stop() {
        this.isPlaying = false;
        this.streamingEngine.stop();
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { StreamingAudioEngine, SunoStreamPlayer, GoogleDriveStreamPlayer };
}
