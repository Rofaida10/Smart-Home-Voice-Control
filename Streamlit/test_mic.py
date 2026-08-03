import os
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import speech_recognition as sr
import string


def test_microphone():
    duration = 4
    fs = 16000
    file_name = "test_audio.wav"

    print("🎤 Speak clearly into your mic: 'open doors'")
    print(f"Recording for {duration} seconds...")

    # 1. التسجيل
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='float32')
    sd.wait()

    # 2. فحص مستوى الصوت (Volume level)
    max_amp = np.max(np.abs(recording))
    print(f"📊 Audio max amplitude: {max_amp:.4f}")

    if max_amp < 0.01:
        print("❌ Audio is TOO QUIET! Check your microphone.")
        print("🔧 Fix: Go to Sound Settings -> Input -> Increase volume")
        return

    # 3. تحويل آمن وحفظ الصوت
    recording_clipped = np.clip(recording, -1.0, 1.0)
    recording_int16 = (recording_clipped * 32767).astype(np.int16)
    wav.write(file_name, fs, recording_int16)

    print("✅ Audio recorded successfully. Testing recognition...")

    # 4. اختيار وتجربة Google STT
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(file_name) as source:
            # تقليل الضوضاء المحيطة قبل القراءة
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.record(source)

            print("🌐 Processing with Google STT...")
            raw_text = recognizer.recognize_google(audio, language="en-US")

            # تنظيف علامات الترقيم
            clean_text = raw_text.strip().lower().translate(str.maketrans('', '', string.punctuation))

            print(f"✅ Raw Text heard: '{raw_text}'")
            print(f"🎯 Cleaned Result: '{clean_text}'")

            if clean_text == "open doors":
                print("🎉 SUCCESS! Passphrase matched successfully!")
            else:
                print(f"⚠️ Passphrase mismatch (Expected: 'open doors', Got: '{clean_text}')")

    except sr.UnknownValueError:
        print("❌ Google could not understand the speech. Try speaking clearer or louder.")
    except sr.RequestError as e:
        print(f"❌ Could not request results from Google STT service; {e}")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
    finally:
        # مسح ملف الاختبار المؤقت
        if os.path.exists(file_name):
            os.remove(file_name)
            print("🧹 Cleaned up temporary test file.")


if __name__ == "__main__":
    test_microphone()