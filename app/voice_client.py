import speech_recognition as sr
import requests
import subprocess
import os
import winsound

FAST_API_URL = "http://127.0.0.1:8000/chat"
PIPER_MODEL = "en_GB-semaine-medium.onnx"   # Model


def listen(recognizer, microphone):
    """Listen for audio and convert its through default windows microphone"""
    with microphone as source:
        print("Listening")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
    try:
        text = recognizer.recognize_whisper(audio, model="tiny.en")
        print(f"Recognized: {text}")
        return text
    except sr.UnknownValueError:
        print("Whisper could not understand audio")


def speak(text):
    """Use Piper to convert text to speech and play it through the default windows speaker"""
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
                    print(f"API Response: {response.json()}")
                    donny_reply = response.json().get("response", "I'm sorry, I couldn't formulate a response.")
                    speak(donny_reply)
                else:
                    print(f"API Error: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"Request Error: {str(e)}")


if __name__ == "__main__":
    main()

    