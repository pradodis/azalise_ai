from datetime import datetime
import matplotlib.pyplot as plt
import os
from config.settings import API_CONFIG, STT_CONFIG, TTS_CONFIG

class PerformanceMetrics:
    def __init__(self):
        self.recording_time = 0
        self.stt_time = 0
        self.ai_time = 0
        self.tts_time = 0
        self.model_info = {
            'stt_model': STT_CONFIG["engine"] + " - " + STT_CONFIG["whisper"]["model"] if STT_CONFIG["engine"] == "whisper" else STT_CONFIG["engine"], 
            'ai_model': 'GPT-3.5' if API_CONFIG["api_type"] == "openai" else API_CONFIG.get('local_api', {}).get('model', 'Unknown'),
            'tts_model': TTS_CONFIG["engine"]
        }
    
    def report(self):
        return f"""Performance Metrics:
        🗣️ STT Time: {self.stt_time:.2f}s
        🤖 AI Response Time: {self.ai_time:.2f}s
        🔊 TTS Processing Time: {self.tts_time:.2f}s
        ⌚ Total Processing Time: {(self.stt_time + self.ai_time + self.tts_time):.2f}s
        """
    
    def get_metrics_dict(self):
        return {
            'stt_time': self.stt_time,
            'ai_time': self.ai_time,
            'tts_time': self.tts_time,
            'total_time': self.stt_time + self.ai_time + self.tts_time,
            'models': self.model_info
        }

def save_performance_log(metrics_data, log_filename):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = (
        f"Timestamp: {timestamp}\n"
        f"STT Time ({metrics_data['models']['stt_model']}): {metrics_data['stt_time']:.2f}s\n"
        f"AI Time ({metrics_data['models']['ai_model']}): {metrics_data['ai_time']:.2f}s\n"
        f"TTS Processing Time ({metrics_data['models']['tts_model']}): {metrics_data['tts_time']:.2f}s\n"
        f"Total Processing Time: {metrics_data['total_time']:.2f}s\n"
        f"{'='*50}\n"
    )
    
    with open(log_filename, 'a', encoding='utf-8') as f:
        f.write(log_entry)

def generate_performance_chart(metrics_data):
    times = [metrics_data[k] for k in ['stt_time', 'ai_time', 'tts_time', 'total_time']]
    labels = [
        f'STT\n({metrics_data["models"]["stt_model"]})',
        f'AI\n({metrics_data["models"]["ai_model"]})',
        f'TTS\n({metrics_data["models"]["tts_model"]})',
        'Total\nTime'
    ]

    plt.figure(figsize=(12, 6))
    bars = plt.bar(labels, times)
    bars[-1].set_color('lightgray')
    
    plt.title('Performance Metrics by Component')
    plt.ylabel('Time (seconds)')
    plt.ylim(0, metrics_data['total_time'] * 1.1)

    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.2f}s', ha='center', va='bottom')

    output_dir = 'performance_charts'
    os.makedirs(output_dir, exist_ok=True)
    
    log_filename = os.path.join(output_dir, 'performance_log.txt')
    save_performance_log(metrics_data, log_filename)
    
    chart_filename = os.path.join(output_dir, f'performance_metrics_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jpg')
    plt.savefig(chart_filename, dpi=300, bbox_inches='tight')
    plt.close()
    
    return chart_filename
