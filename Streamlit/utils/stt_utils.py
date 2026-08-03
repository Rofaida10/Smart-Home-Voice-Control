import string
import speech_recognition as sr


def transcribe_audio(audio_path, language="en-US"):
    """
    Transcribe audio file using Google Speech Recognition API (strictly forced to English).
    """
    recognizer = sr.Recognizer()

    try:
        print(f"Processing audio file: {audio_path}")

        with sr.AudioFile(audio_path) as source:
            print("Reading audio file...")

            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.record(source)

            print("Sending audio to Google Speech-to-Text API...")

            text = recognizer.recognize_google(audio, language="en-US")


            clean_text = text.strip().lower().translate(str.maketrans('', '', string.punctuation))
            print(f"Transcription result: '{clean_text}'")
            return clean_text

    except sr.UnknownValueError:
        print("Google Speech Recognition could not understand the audio.")
        return ""
    except sr.RequestError as e:
        print(f"Google Speech Recognition service error: {e}")
        return ""
    except Exception as e:
        print(f"STT processing error: {str(e)}")
        return ""