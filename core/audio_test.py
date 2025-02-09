# test_audio_devices.py
import sounddevice as sd
import pygame

def list_audio_devices():
    print("\nSOUNDDEVICE OUTPUT DEVICES:")
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if device['max_output_channels'] > 0:
            print(f"ID {i}: {device['name']}")
    
    print("\nPYGAME OUTPUT DEVICES:")
    pygame.init()
    pygame.mixer.init()
    for i in range(pygame.mixer.get_num_devices()):
        print(f"ID {i}: {pygame.mixer.get_device_name(i)}")

if __name__ == "__main__":
    list_audio_devices()