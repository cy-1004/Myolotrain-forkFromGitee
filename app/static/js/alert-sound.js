/**
 * 报警声音生成器
 * 使用Web Audio API生成报警声音
 */
class AlertSoundGenerator {
    constructor() {
        // 检查浏览器是否支持Web Audio API
        this.audioContext = null;
        try {
            window.AudioContext = window.AudioContext || window.webkitAudioContext;
            this.audioContext = new AudioContext();
        } catch (e) {
            console.error('Web Audio API不受支持。', e);
        }
        
        // 创建音频缓冲区
        this.alertBuffer = null;
        this.generateAlertSound();
    }
    
    /**
     * 生成报警声音
     */
    generateAlertSound() {
        if (!this.audioContext) return;
        
        // 创建2秒的音频缓冲区
        const sampleRate = this.audioContext.sampleRate;
        const duration = 2;
        const bufferSize = sampleRate * duration;
        const buffer = this.audioContext.createBuffer(1, bufferSize, sampleRate);
        const data = buffer.getChannelData(0);
        
        // 生成警报声音 - 交替的高低音调
        const highFreq = 880; // A5
        const lowFreq = 440;  // A4
        
        for (let i = 0; i < bufferSize; i++) {
            // 每0.2秒切换一次频率
            const freq = (Math.floor(i / (sampleRate * 0.2)) % 2 === 0) ? highFreq : lowFreq;
            // 正弦波
            data[i] = Math.sin(2 * Math.PI * freq * i / sampleRate);
            // 添加衰减以避免爆音
            if (i < sampleRate * 0.1) {
                // 淡入
                data[i] *= (i / (sampleRate * 0.1));
            } else if (i > bufferSize - sampleRate * 0.1) {
                // 淡出
                data[i] *= ((bufferSize - i) / (sampleRate * 0.1));
            }
        }
        
        this.alertBuffer = buffer;
    }
    
    /**
     * 播放报警声音
     */
    play() {
        if (!this.audioContext || !this.alertBuffer) return;
        
        // 创建音源
        const source = this.audioContext.createBufferSource();
        source.buffer = this.alertBuffer;
        
        // 连接到输出
        source.connect(this.audioContext.destination);
        
        // 播放
        source.start();
    }
}

// 创建全局实例
window.alertSoundGenerator = new AlertSoundGenerator();
