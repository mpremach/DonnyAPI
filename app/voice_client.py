import speech_recognition as sr
import requests
import subprocess
import os
import winsound
import threading
import queue
import re


FAST_API_URL = "http://127.0.0.1:8000/chat"
PIPER_MODEL = "en_GB-semaine-medium.onnx"   # Model


def listen(recognizer, microphone):
    """Listen for audio and convert its through default windows microphone"""
    with microphone as source:
        print("\nListening")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
    try:
        text = recognizer.recognize_whisper(audio, model="tiny.en")
        print(f"Recognized: {text}")
        return text
    except sr.UnknownValueError:
        print("Whisper could not understand audio")

audio_queue = queue.Queue()
def speak_streaming():
    """Use Piper to convert text to speech and play it through the default windows speaker"""
    while True:
        text = audio_queue.get()  # Wait for text to be available
        if text is None: break
        
        try:
            subprocess.run(["piper/piper.exe", "--model", PIPER_MODEL, "--speaker", "1", "--output_file", "../reply.wav"],
                input=text.encode(), check=True, cwd = "piper",
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL # Suppress Piper terminal log output
        ) 
            if os.path.exists("reply.wav"):
                print("Playing reply.wav")
                winsound.PlaySound("reply.wav", winsound.SND_FILENAME)
    
        except Exception as e: 
            print(f"Piper Error: {str(e)}")
        
        audio_queue.task_done()

threading.Thread(target=speak_streaming, daemon=True).start()
        

def main():
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 1.25
    microphone = sr.Microphone()

    while True:
        user_input = listen(recognizer, microphone)
        if user_input:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
            try:
                response = requests.post(FAST_API_URL, json={"message": user_input})
                if response.status_code == 200:
                    buffer = ""
                    print("Donny: ", end="", flush=True) 
                    for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                        if chunk:
                            buffer += chunk
                            print(chunk, end="", flush=True)
                            if "{" in buffer or "}" in buffer: # Prevent printing of raw JSON data
                                print("\n[System: Blocked JSON leak]")
                                buffer = ""
                                continue  # Skip processing this chunk
                            if re.search(r'[.!?]\s*', buffer):  # Check for sentence-ending punctuation
                                cleaned_sentence = buffer.strip()
                                if cleaned_sentence:
                                    audio_queue.put(cleaned_sentence)  # Send the complete sentence to the audio queue
                                buffer = ""  # Clear the buffer after sending
                    if buffer.strip():  
                        audio_queue.put(buffer.strip())  # Send any remaining text in the buffer
                        print()  # Move to the next line after the final output
                        audio_queue.join()  # Wait until all audio has been processed
                else:
                    print(f"API Error: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"Request Error: {str(e)}")


if __name__ == "__main__":
    main()

    