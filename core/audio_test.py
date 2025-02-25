# test_audio_devices.py
import sounddevice as sd
import pygame.mixer

def list_audio_devices():
    print("\n=== SOUNDDEVICE INPUT DEVICES ===")
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            print(f"ID {i}: {device['name']} (Channels: {device['max_input_channels']})")
    
    print("\n=== SOUNDDEVICE OUTPUT DEVICES ===")
    for i, device in enumerate(devices):
        if device['max_output_channels'] > 0:
            print(f"ID {i}: {device['name']} (Channels: {device['max_output_channels']})")
    
    print("\n=== PYGAME OUTPUT DEVICES ===")
    try:
        pygame.mixer.init()
        # Get the current audio device
        current_device = pygame.mixer.get_init()
        if current_device:
            freq, size, channels = current_device
            print(f"Current PyGame Audio Device:")
            print(f"- Frequency: {freq}Hz")
            print(f"- Size: {size}bit")
            print(f"- Channels: {channels}")
    except Exception as e:
        print(f"Could not initialize PyGame mixer: {e}")

    # Print default devices
    print("\n=== DEFAULT DEVICES ===")
    try:
        default_input = sd.default.device[0]
        default_output = sd.default.device[1]
        print(f"Default Input Device: ID {default_input} - {devices[default_input]['name']}")
        print(f"Default Output Device: ID {default_output} - {devices[default_output]['name']}")
    except Exception as e:
        print(f"Could not determine default devices: {e}")

if __name__ == "__main__":
    list_audio_devices()