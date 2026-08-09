"""Scans a folder of recordings and builds Data/recordings.csv automatically

Expected filename convention:
    <person>_<command>_<index>.wav
    e.g.  Muahmed_light_on_01.wav
          Rofaida_music_off_07.wav
          Salah_light_off_03.wav
Usage:
    python generate_csv.py --wav-dir Data/wavs --output Data/recordings.csv
"""

import argparse
import csv
import logging
from pathlib import Path

from features import COMMAND_LABELS

logger = logging.getLogger(__name__)


class FilenameParser:
    """Extracts (person, command) from a filename using the known command labels.

    Commands themselves contain underscores (e.g. "light_on"), so we can't
    just split on "_" blindly we match against the known label list instead,
    longest first and whatever's left before it is the person's name.
    """

    def __init__(self, command_labels: list[str]):
        # Longest first, so "music_off" is matched before a shorter false match.
        self.command_labels = sorted(command_labels, key=len, reverse=True)

    def parse(self, stem: str) -> tuple[str, str] | None:
        for command in self.command_labels:
            marker = f"_{command}_"
            if marker in stem:
                person, _, _rest = stem.partition(marker)
                if person:
                    return person, command
        return None


class DatasetCsvBuilder:
    """Walks a directory of .wav files and writes filepath/person/command rows."""

    def __init__(self, parser: FilenameParser):
        self.parser = parser

    def build(self, wav_dir: Path) -> list[tuple[str, str, str]]:
        rows = []
        skipped = []

        for wav_path in sorted(wav_dir.glob("*.wav")):
            parsed = self.parser.parse(wav_path.stem)
            if parsed is None:
                skipped.append(wav_path.name)
                continue
            person, command = parsed
            rows.append((str(wav_path), person, command))

        logger.info("DatasetCsvBuilder: matched %d files, skipped %d", len(rows), len(skipped))
        if skipped:
            logger.warning("Could not parse %d filenames (check the naming convention):", len(skipped))
            for name in skipped:
                logger.warning("  - %s", name)

        return rows


class CsvWriter:
    def __init__(self, output_path: Path):
        self.output_path = output_path

    def write(self, rows: list[tuple[str, str, str]]) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["filepath", "person", "command"])
            writer.writerows(rows)
        logger.info("CsvWriter: wrote %d rows to %s", len(rows), self.output_path)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    arg_parser = argparse.ArgumentParser(description=__doc__)
    arg_parser.add_argument("--wav-dir", type=Path, default=Path("Data/wavs"))
    arg_parser.add_argument("--output", type=Path, default=Path("Data/recordings.csv"))
    args = arg_parser.parse_args()

    if not args.wav_dir.exists():
        raise FileNotFoundError(f"wav directory not found: {args.wav_dir}")

    parser = FilenameParser(COMMAND_LABELS)
    builder = DatasetCsvBuilder(parser)
    rows = builder.build(args.wav_dir)

    if not rows:
        raise RuntimeError("No matching .wav files found — check the naming convention.")

    CsvWriter(args.output).write(rows)

    people = sorted({r[1] for r in rows})
    commands = sorted({r[2] for r in rows})
    print(f"\nDone: {len(rows)} recordings | people={people} | commands={commands}")


if __name__ == "__main__":
    main()