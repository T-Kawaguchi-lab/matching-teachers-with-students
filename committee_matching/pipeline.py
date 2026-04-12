from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict

import pandas as pd

from .config import get_config
from .excel_io import ensure_input_files, load_generic_table, load_student_excel, load_teacher_excel
from .field_assignment import FieldTaxonomyMatcher
from .models import load_embedding_model
from .mpps_mse_processing import GROUPS, load_master_title, merge_master_title, prepare_students, prepare_teachers
from .similarity import compute_similarity, top_matches_for_group
from .trios import enrich_teacher_from_trios
from .utils import normalize_name, save_json

OUTPUT_STATUS_FILE = "generated/pipeline_status.json"


def _file_meta(path: Path) -> Dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path),
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "size_bytes": int(stat.st_size),
    }


def _export_excel(path: Path, sheets: Dict[str, pd.DataFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)


def _save_temp_copy(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)
    return path


def update_master_title_file(root_dir: Path, append_path: str | Path | None = None) -> Path:
    cfg = get_config()
    master_path = root_dir / str(cfg["master_title_excel"])
    base_df = load_master_title(master_path)

    if append_path:
        extra_df = load_generic_table(append_path)
        extra_df = load_master_title(
            _save_temp_copy(extra_df, root_dir / "generated" / "_tmp_master_append.xlsx")
        )
        base_df = merge_master_title(base_df, extra_df)

    master_path.parent.mkdir(parents=True, exist_ok=True)
    base_df.to_excel(master_path, index=False)
    return master_path


def build_trios_lookup(teachers_df: pd.DataFrame, root_dir: Path) -> Dict[str, Dict[str, object]]:
    cfg = get_config()
    lookup: Dict[str, Dict[str, object]] = {}
    unique_names = teachers_df["指導教員"].dropna().astype(str).tolist()

    for name in unique_names:
        norm = normalize_name(name)
        if norm in lookup:
            continue
        result = enrich_teacher_from_trios(
            name=str(name),
            base_url=str(cfg["trios_base_url"]),
            cache_dir=root_dir / str(cfg["trios_cache_dir"]),
            trios_url="",
        )
        result.setdefault("teacher_name", str(name))
        lookup[norm] = result

    return lookup


def run_pipeline(
    root_dir: str | Path | None = None,
    teacher_path: str | Path | None = None,
    student_path: str | Path | None = None,
    history_path: str | Path | None = None,
    append_master_title_path: str | Path | None = None,
) -> Dict[str, object]:
    root = Path(root_dir) if root_dir else Path(__file__).resolve().parents[1]
    cfg = get_config()

    teacher_file = Path(teacher_path) if teacher_path else root / str(cfg["incoming_teacher_excel"])
    student_file = Path(student_path) if student_path else root / str(cfg["incoming_student_excel"])
    history_file = Path(history_path) if history_path else root / str(cfg["master_title_excel"])

    teacher_file, student_file, _ = ensure_input_files(teacher_file, student_file, history_file)

    teachers_raw = load_teacher_excel(teacher_file)
    students_raw = load_student_excel(student_file)

    if append_master_title_path:
        update_master_title_file(root, append_master_title_path)
    elif not history_file.exists():
        legacy = root / "data_sources" / "source_history.xlsx"
        if legacy.exists():
            load_master_title(legacy).to_excel(history_file, index=False)

    master_df = load_master_title(history_file)
    trios_lookup = build_trios_lookup(teachers_raw, root)

    model = load_embedding_model(str(cfg["embedding_model"]))

    students = prepare_students(students_raw)
    teachers = prepare_teachers(teachers_raw, master_df, trios_lookup)
    generated_dir = root / str(cfg["generated_dir"])
    generated_dir.mkdir(parents=True, exist_ok=True)

    score_frames = []
    recommendation_frames = []

    for group in GROUPS:
        group_students = students[students["group"] == group].reset_index(drop=True)
        group_teachers = (
            teachers[teachers["group"] == group]
            .drop_duplicates(subset=["teacher_name", "group"])
            .reset_index(drop=True)
        )

        if group_students.empty or group_teachers.empty:
            continue

        similarity = compute_similarity(
            group_students,
            group_teachers,
            model,
            {
                "field_similarity_weight": float(cfg["field_similarity_weight"]),
                "content_similarity_weight": float(cfg["content_similarity_weight"]),
            },
        )

        scores_df, _ = top_matches_for_group(
            group_students,
            group_teachers,
            similarity,
            top_k=None,
        )

        _, rec_df = top_matches_for_group(
            group_students,
            group_teachers,
            similarity,
            top_k=int(cfg["top_k_rerank"]),
        )

        score_frames.append(scores_df)
        recommendation_frames.append(rec_df)

    scores_all = pd.concat(score_frames, ignore_index=True) if score_frames else pd.DataFrame()
    rec_all = pd.concat(recommendation_frames, ignore_index=True) if recommendation_frames else pd.DataFrame()

    students_out = generated_dir / "students_enriched.xlsx"
    teachers_out = generated_dir / "teachers_enriched.xlsx"
    rec_out = generated_dir / "committee_recommendations.xlsx"
    score_out = generated_dir / "student_teacher_similarity_detailed.xlsx"
    scores_csv = generated_dir / "student_teacher_scores_long.csv"

    _export_excel(
        students_out,
        {g: students[students["group"] == g] for g in GROUPS if not students[students["group"] == g].empty},
    )
    _export_excel(
        teachers_out,
        {g: teachers[teachers["group"] == g] for g in GROUPS if not teachers[teachers["group"] == g].empty},
    )
    _export_excel(
        rec_out,
        {g: rec_all[rec_all["group"] == g] for g in GROUPS if not rec_all[rec_all["group"] == g].empty},
    )
    _export_excel(
        score_out,
        {g: scores_all[scores_all["group"] == g] for g in GROUPS if not scores_all[scores_all["group"] == g].empty},
    )
    scores_all.to_csv(scores_csv, index=False)

    lookup_summary = {
        "total": int(len(trios_lookup)),
        "by_status": {},
        "by_source": {},
        "missing_teachers": [],
    }
    for raw in trios_lookup.values():
        status_key = str(raw.get("status", ""))
        source_key = str(raw.get("profile_source", ""))
        lookup_summary["by_status"][status_key] = int(lookup_summary["by_status"].get(status_key, 0)) + 1
        lookup_summary["by_source"][source_key] = int(lookup_summary["by_source"].get(source_key, 0)) + 1
        has_any = any(raw.get(key) for key in ["research_topics", "research_fields", "research_keywords", "papers"])
        if not has_any:
            lookup_summary["missing_teachers"].append(str(raw.get("teacher_name", "")))

    status = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "teacher_input": _file_meta(teacher_file),
        "student_input": _file_meta(student_file),
        "master_title_input": _file_meta(history_file) if history_file.exists() else {},
        "students_count": int(len(students)),
        "teachers_count": int(len(teachers)),
        "scores_count": int(len(scores_all)),
        "recommendations_count": int(len(rec_all)),
        "lookup_summary": lookup_summary,
        "groups": {
            g: {
                "students": int((students["group"] == g).sum()),
                "teachers": int((teachers["group"] == g).sum()),
            }
            for g in GROUPS
        },
        "note": "TRIOS取得は実行環境のネットワーク状況に依存します。失敗時はキャッシュまたは空欄で継続します。",
    }
    save_json(root / OUTPUT_STATUS_FILE, status)
    return status


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher-path", default=None)
    parser.add_argument("--student-path", default=None)
    parser.add_argument("--history-path", default=None)
    parser.add_argument("--append-master-title-path", default=None)
    args = parser.parse_args()

    print(
        run_pipeline(
            teacher_path=args.teacher_path,
            student_path=args.student_path,
            history_path=args.history_path,
            append_master_title_path=args.append_master_title_path,
        )
    )