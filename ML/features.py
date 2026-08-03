"""Feature/label contract shared across the ML module.

will be file contain CSV columns produced by the team when assembling the dataset:
  - filepath : path to a .wav recording
  - person   : who is speaking (e.g. "person_a")
  - command  : one of COMMAND_LABELS
"""

SAMPLE_RATE = 16000
N_MFCC = 40

FILEPATH_COLUMN = "filepath"
PERSON_COLUMN = "person"
COMMAND_COLUMN = "command"

COMMAND_LABELS = ["light_on", "light_off", "music_on", "music_off"]

MIN_REQUIRED_F1 = 0.85