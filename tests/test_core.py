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


class FakeArtist:
    def __init__(self, name):
        self.Name = name


class FullTrack:
    def __init__(self, ident, path, color="0", title="", artist="A"):
        self.ID = ident
        self.FolderPath = path
        self.ColorID = color
        self.Title = title
        self.Artist = FakeArtist(artist)


class FakeCollection:
    def __init__(self, tracks):
        self._tracks = tracks
        self.committed = False

    def tracks(self):
        return self._tracks

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


def _export(tmp_path: Path, rows: str):
    csv_file = tmp_path / "e.csv"
    csv_file.write_text("filename,path,verdict\n" + rows, encoding="utf-8")
    return read_spectro_csv(csv_file)


def test_plan_reports_rows_missing_from_collection(tmp_path: Path):
    from spectro_rb.sync import build_plan

    export = _export(
        tmp_path,
        '"a.mp3","/M/a.mp3","FAKE"\n'
        '"ghost.mp3","/M/ghost.mp3","MEDIUM"\n'
        '"dup.mp3","/Z/dup.mp3","LOSSLESS"\n',
    )
    collection = FakeCollection(
        [
            FullTrack("1", "/M/a.mp3"),
            FullTrack("2", "/X/dup.mp3"),
            FullTrack("3", "/Y/dup.mp3"),
        ]
    )
    plan = build_plan(export, collection)

    assert [c.content_id for c in plan.changes] == ["1"]
    assert [r.path for r in plan.unmatched] == ["/M/ghost.mp3"]
    assert [r.path for r in plan.ambiguous] == ["/Z/dup.mp3"]
    assert plan.summary()["unmatched"] == 1
    assert plan.summary()["ambiguous"] == 1


def test_apply_only_touches_color(tmp_path: Path):
    from spectro_rb.sync import apply_plan, build_plan

    export = _export(tmp_path, '"a.mp3","/M/a.mp3","FAKE"\n')
    track = FullTrack("1", "/M/a.mp3", color="1", title="T")
    collection = FakeCollection([track])
    plan = build_plan(export, collection)

    assert apply_plan(plan, collection) == 1
    assert track.ColorID == "2"  # Red
    assert track.Title == "T" and track.FolderPath == "/M/a.mp3"
    assert collection.committed


def test_worst_verdict_wins_for_duplicate_rows(tmp_path: Path):
    from spectro_rb.sync import build_plan

    export = _export(
        tmp_path, '"a.mp3","/M/a.mp3","LOSSLESS"\n"a.mp3","/M/a.mp3","FAKE"\n'
    )
    collection = FakeCollection([FullTrack("1", "/M/a.mp3")])
    plan = build_plan(export, collection)
    assert len(plan.changes) == 1
    assert plan.changes[0].verdict is Verdict.FAKE


def test_report_lists_every_problem_row(tmp_path: Path):
    from spectro_rb.report import write_report
    from spectro_rb.sync import build_plan

    export = _export(tmp_path, '"g.mp3","/M/g.mp3","FAKE"\n"b.mp3","","MEDIUM"\n')
    plan = build_plan(export, FakeCollection([FullTrack("1", "/M/other.mp3")]))
    out = write_report(plan, tmp_path / "r.csv")
    text = out.read_text(encoding="utf-8")
    assert "not in collection" in text and "/M/g.mp3" in text
    assert "unreadable row" in text
