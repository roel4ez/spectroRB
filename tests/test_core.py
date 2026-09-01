import unicodedata
from pathlib import Path

import pytest

from spectro_rb.matching import TrackIndex, normalize_path
from spectro_rb.model import DEFAULT_MAPPING, MatchKind, Verdict, color_label
from spectro_rb.spectro import InvalidSpectroCsv, read_spectro_csv


class FakeTrack:
    def __init__(self, path, ident="1"):
        self.FolderPath = path
        self.ID = ident


def path_of(track):
    return track.FolderPath


def test_normalize_handles_file_urls_and_unicode():
    nfd = unicodedata.normalize("NFD", "/Music/Bj\u00f6rk/track.mp3")
    assert normalize_path(nfd) == "/Music/Bj\u00f6rk/track.mp3"
    assert normalize_path("file://localhost/Music/a%20b.mp3") == "/Music/a b.mp3"
    assert normalize_path("/Music/./sub/../a.mp3") == "/Music/a.mp3"


def test_exact_then_casefold_then_filename():
    index = TrackIndex.build(
        [FakeTrack("/Music/A.mp3", "1"), FakeTrack("/Other/Unique.mp3", "2")], path_of
    )
    assert index.lookup("/Music/A.mp3")[1] is MatchKind.EXACT_PATH
    assert index.lookup("/music/a.mp3")[1] is MatchKind.CASE_INSENSITIVE_PATH
    track, kind = index.lookup("/Somewhere/Else/Unique.mp3")
    assert kind is MatchKind.FILENAME and track.ID == "2"


def test_ambiguous_filenames_are_never_matched():
    index = TrackIndex.build([FakeTrack("/A/dup.mp3", "1"), FakeTrack("/B/dup.mp3", "2")], path_of)
    track, kind = index.lookup("/C/dup.mp3")
    assert track is None and kind is MatchKind.AMBIGUOUS
    assert index.lookup("/A/dup.mp3")[0].ID == "1"


def test_unmatched_path():
    index = TrackIndex.build([FakeTrack("/A/one.mp3")], path_of)
    assert index.lookup("/A/two.mp3") == (None, MatchKind.UNMATCHED)


def test_color_mapping_is_green_yellow_red():
    assert color_label(DEFAULT_MAPPING[Verdict.LOSSLESS]) == "Green"
    assert color_label(DEFAULT_MAPPING[Verdict.MEDIUM]) == "Yellow"
    assert color_label(DEFAULT_MAPPING[Verdict.FAKE]) == "Red"
    assert color_label("0") == "None"


def test_read_csv(tmp_path: Path):
    csv_file = tmp_path / "export.csv"
    csv_file.write_text(
        "filename,path,verdict,confidence_pct\n"
        '"a.mp3","/M/a.mp3","LOSSLESS","99"\n'
        '"b.mp3","/M/b.mp3","fake","10"\n'
        '"c.mp3","/M/c.mp3","WEIRD","10"\n'
        '"d.mp3","","MEDIUM","10"\n',
        encoding="utf-8",
    )
    export = read_spectro_csv(csv_file)
    assert [r.verdict for r in export.rows] == [Verdict.LOSSLESS, Verdict.FAKE]
    assert export.verdict_counts == {"LOSSLESS": 1, "MEDIUM": 0, "FAKE": 1}
    assert len(export.skipped) == 2


def test_read_csv_rejects_foreign_files(tmp_path: Path):
    csv_file = tmp_path / "other.csv"
    csv_file.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(InvalidSpectroCsv):
        read_spectro_csv(csv_file)
