import speech_recognition as sr
import requests
import subprocess
import os
import winsound
import threading
import queue
import re
import time


FAST_API_URL = "http://127.0.0.1:8000/chat"
PIPER_MODEL = "en_GB-semaine-medium.onnx"   # Model

audio_queue = queue.Queue()
is_donny_speaking = False
abort_stream_event = threading.Event()
current_request_id = 0



def listen(recognizer, microphone, timeout=None, phrase_time_limit=None, show_text=False):
    """Listen for audio and convert its through default windows microphone"""
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        if timeout is not None:
            print("\nListening")
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            return "TIMEOUT"
    try:
        text = recognizer.recognize_whisper(audio, model="tiny.en") #tiny.en (smallest), small.en (small)
        if text.strip() and show_text:
            print(f"Recognized: {text}")
        return text
    except sr.UnknownValueError:
        print("Whisper could not understand audio")
        return None

def speak_streaming():
    """Use Piper to convert text to speech and play it through the default windows speaker"""
    while True:
        item = audio_queue.get()  # Wait for text to be available
        if item is None: break
        req_id, text = item

        # If this text belongs to an old interrupted prompt, throw it away
        if req_id != current_request_id:
            audio_queue.task_done()
            continue

        try:
            subprocess.run(["piper/piper.exe", "--model", PIPER_MODEL, "--speaker", "1", "--output_file", "../reply.wav"],
                input=text.encode(), check=True, cwd = "piper",
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL # Suppress Piper terminal log output
        ) 
            if req_id == current_request_id and os.path.exists("reply.wav") and not abort_stream_event.is_set():
                print("Playing reply.wav")
                winsound.PlaySound("reply.wav", winsound.SND_FILENAME)
    
        except Exception as e:
            if not abort_stream_event.is_set():
                print(f"Piper Error: {str(e)}")
        
        audio_queue.task_done()

threading.Thread(target=speak_streaming, daemon=True).start()

def stop_speaking():
    """Stop the current speech output immediately"""
    global is_donny_speaking
    abort_stream_event.set()  # Signal the speaking thread to stop
    while not audio_queue.empty():
        try:
            audio_queue.get_nowait()
            audio_queue.task_done() # This brings the counter down to 0
        except queue.Empty:
            break
    winsound.PlaySound(None, winsound.SND_PURGE)  # Stop any currently playing sound
    is_donny_speaking = False
    print("\n[System: Donny interrupted]")


def background_api_stream(user_input, req_id):
    """Runs the API request in the background so the microphone can keep looping."""
    global is_donny_speaking
    is_donny_speaking = True
    abort_stream_event.clear()

    try:
        response = requests.post(FAST_API_URL, json={"message": user_input}, stream=True)
        if response.status_code == 200:
            buffer = ""
            print("Donny: ", end="", flush=True) 
            for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                if abort_stream_event.is_set() or req_id != current_request_id:
                    return  # Stop processing if an interrupt signal is received
                if chunk:
                    buffer += chunk
                    print(chunk, end="", flush=True)
                    if "{" in buffer or "}" in buffer: # Prevent printing of raw JSON data
                        print("\n[System: Blocked JSON leak]")
                        buffer = ""
                        continue  # Skip processing this chunk
                    if re.search(r'[.!?]\s+', buffer):  # Check for sentence-ending punctuation
                        cleaned_sentence = buffer.strip()
                        cleaned_sentence = re.sub(r'[*#_~`\\]', '', cleaned_sentence)  # Remove markdown and special characters
                        if cleaned_sentence:
                            audio_queue.put((req_id, cleaned_sentence))  # Send the complete sentence to the audio queue
                        buffer = ""  # Clear the buffer after sending
            if buffer.strip():  
                audio_queue.put((req_id, buffer.strip()))  # Send any remaining text in the buffer
                print()  # Move to the next line after the final output
            if not abort_stream_event.is_set():
                audio_queue.join()  # Wait until all audio has been processed
        else:
            print(f"API Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Request Error: {str(e)}")
    
    finally:
        if req_id == current_request_id:
            is_donny_speaking = False


def main():
    global is_donny_speaking, current_request_id
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 1.4 #Time waited after user stops talking before processing the audio
    microphone = sr.Microphone()

    is_awake = False
    idle_timeout = 10  # Seconds of silence before Donny goes back to sleep
    last_active_time = time.time()

    print("DONNY SYSTEM READY")

    while True:
        if not is_awake: #STATE: SLEEPING
            user_input = listen(recognizer, microphone, phrase_time_limit=3)
            if user_input and user_input != "TIMEOUT":
                clean_text = re.sub(r'[^\w\s]', '', user_input.lower())
                if "donny" in clean_text or "donnie" in clean_text:
                    winsound.MessageBeep(winsound.MB_ICONASTERISK)
                    is_awake = True
                    last_active_time = time.time()
                    print("\n[DONNY: AWAKE]")
                    
                    # Chop the sentence at "donny" and keep what comes after
                    parts = re.split(r'(?i)donny|donnie', user_input, maxsplit=1)
                    if len(parts) > 1 and parts[-1].strip():
                        command = parts[-1].strip()
                        command = re.sub(r'^[^a-zA-Z0-9]+', '', command)
                    
                        if command:
                            print(f"Recognized: {command}")
                            current_request_id += 1
                            threading.Thread(target=background_api_stream, args=(command, current_request_id), daemon=True).start()
        else: #STATE: AWAKE
            user_input = listen(recognizer, microphone, timeout=3, show_text=True)
            if user_input and user_input != "TIMEOUT":
                if re.search(r'[a-zA-Z0-9]', user_input):
                    print(f"[System: Processing valid input: {user_input}]")
                    
                    if is_donny_speaking:
                        stop_speaking()  # Interrupt Donny if he's currently speaking
                        time.sleep(0.4)  # Brief pause to ensure the speaking thread has stopped
                    current_request_id += 1  # Increment request ID for the new prompt
                    last_active_time = time.time()  # Reset idle timer if user spoke something before timeout
                    threading.Thread(target=background_api_stream, args=(user_input, current_request_id), daemon=True).start()


            if is_donny_speaking and not abort_stream_event.is_set():
                last_active_time = time.time()  # Reset idle timer while Donny is speaking

            elapsed_time = time.time() - last_active_time

            if (elapsed_time > idle_timeout):
                if not is_donny_speaking and audio_queue.empty():
                    print("\n[DONNY: IDLE]")
                    is_awake = False    


if __name__ == "__main__":
    main()

    