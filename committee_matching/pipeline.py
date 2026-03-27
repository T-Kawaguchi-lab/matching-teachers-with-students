from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd

from .config import get_config
from .excel_io import ensure_input_files, load_student_excel, load_teacher_excel
from .field_assignment import FieldTaxonomyMatcher, merge_manual_and_generated
from .git_sync import git_add_if_available
from .models import load_embedding_model
from .similarity import compute_similarity, greedy_committee_selection
from .thesis_history import load_teacher_history_map
from .trios import enrich_teacher_from_trios
from .utils import normalize_name, normalize_text, save_json


OUTPUT_STATUS_FILE = 'generated/pipeline_status.json'


def _resolve_history_file(cfg: Dict[str, object], root_dir: Path) -> Path | None:
    candidates = [
        root_dir / str(cfg['teacher_history_excel']),
        root_dir / str(cfg['teacher_history_csv']),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _file_meta(path: Path) -> Dict[str, object]:
    stat = path.stat()
    return {
        'path': str(path),
        'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds'),
        'size_bytes': int(stat.st_size),
    }


def _matched_words(student_fields: List[str], teacher_fields: List[str]) -> List[str]:
    s_norm = {normalize_text(v).lower(): normalize_text(v) for v in student_fields if normalize_text(v)}
    t_norm = {normalize_text(v).lower(): normalize_text(v) for v in teacher_fields if normalize_text(v)}
    words: List[str] = []
    for key, value in s_norm.items():
        if key in t_norm:
            words.append(t_norm[key] or value)
    return words


def prepare_teacher_dataframe(
    teachers: pd.DataFrame,
    cfg: Dict[str, object],
    root_dir: Path,
    model,
) -> pd.DataFrame:
    history_file = _resolve_history_file(cfg, root_dir)
    history_map = load_teacher_history_map(history_file) if history_file else {}
    matcher = FieldTaxonomyMatcher(model)

    enriched_rows: List[Dict[str, object]] = []
    for _, row in teachers.iterrows():
        teacher_name = normalize_text(row['teacher_name'])
        trios_data = enrich_teacher_from_trios(
            name=teacher_name,
            base_url=str(cfg['trios_base_url']),
            cache_dir=root_dir / str(cfg['trios_cache_dir']),
            trios_url=normalize_text(row.get('trios_url', '')),
        )
        thesis_titles = history_map.get(normalize_name(teacher_name), [])
        generated_fields = matcher.suggest_fields(
            [teacher_name, *trios_data.get('research_topics', []), *trios_data.get('papers', []), *thesis_titles],
            top_k=int(cfg['top_k_fields']),
        )
        final_fields = merge_manual_and_generated(
            row.get('manual_research_fields', ''),
            generated_fields,
            top_k=int(cfg['top_k_fields']),
        )

        enriched_rows.append({
            'teacher_name': teacher_name,
            'department': normalize_text(row.get('department', '')),
            'position': normalize_text(row.get('position', '')),
            'trios_url': normalize_text(row.get('trios_url', '')) or normalize_text(trios_data.get('matched_url', '')),
            'trios_status': normalize_text(trios_data.get('status', '')),
            'trios_topics': trios_data.get('research_topics', []),
            'trios_topics_text': ' / '.join(trios_data.get('research_topics', [])),
            'trios_papers': trios_data.get('papers', []),
            'trios_papers_text': ' / '.join(trios_data.get('papers', [])),
            'past_thesis_titles': thesis_titles,
            'past_thesis_titles_text': ' / '.join(thesis_titles),
            'research_fields': final_fields,
            'research_fields_text': ' / '.join(final_fields),
        })

    return pd.DataFrame(enriched_rows)


def prepare_student_dataframe(
    students: pd.DataFrame,
    cfg: Dict[str, object],
    model,
) -> pd.DataFrame:
    matcher = FieldTaxonomyMatcher(model)
    enriched_rows: List[Dict[str, object]] = []

    for _, row in students.iterrows():
        thesis_title = normalize_text(row['thesis_title'])
        generated_fields = matcher.suggest_fields(
            [thesis_title],
            top_k=int(cfg.get('student_top_k_fields', 3)),
            min_score=float(cfg.get('student_field_min_score', 0.32)),
            additional_min_score=float(cfg.get('student_additional_field_min_score', 0.30)),
            relative_score_floor=float(cfg.get('student_relative_score_floor', 0.92)),
        )
        final_fields = merge_manual_and_generated(
            row.get('manual_research_fields', ''),
            generated_fields,
            top_k=int(cfg.get('student_top_k_fields', 3)),
        )

        enriched_rows.append({
            'student_name': normalize_text(row['student_name']),
            'department': normalize_text(row.get('department', '')),
            'thesis_title': thesis_title,
            'research_fields': final_fields,
            'research_fields_text': ' / '.join(final_fields),
        })

    return pd.DataFrame(enriched_rows)


def _export_frame_to_excel(df: pd.DataFrame, path: Path) -> None:
    export_df = df.copy()
    for col in ['research_fields', 'trios_topics', 'trios_papers', 'past_thesis_titles']:
        if col in export_df.columns:
            export_df[col] = export_df[col].map(
                lambda xs: ' ; '.join(xs) if isinstance(xs, list) else xs
            )
    export_df.to_excel(path, index=False)


def write_partial_outputs(
    root_dir: Path,
    teachers: pd.DataFrame | None = None,
    students: pd.DataFrame | None = None,
) -> Dict[str, str]:
    generated_dir = root_dir / 'generated'
    generated_dir.mkdir(parents=True, exist_ok=True)

    outputs: Dict[str, str] = {}

    if teachers is not None:
        teacher_out = generated_dir / 'teachers_enriched.xlsx'
        _export_frame_to_excel(teachers, teacher_out)
        outputs['teachers_enriched'] = str(teacher_out)

    if students is not None:
        student_out = generated_dir / 'students_enriched.xlsx'
        _export_frame_to_excel(students, student_out)
        outputs['students_enriched'] = str(student_out)

    return outputs


def write_outputs(
    root_dir: Path,
    teachers: pd.DataFrame,
    students: pd.DataFrame,
    similarity,
) -> Dict[str, str]:
    generated_dir = root_dir / 'generated'
    generated_dir.mkdir(parents=True, exist_ok=True)

    teacher_out = generated_dir / 'teachers_enriched.xlsx'
    student_out = generated_dir / 'students_enriched.xlsx'
    committee_out = generated_dir / 'committee_recommendations.xlsx'
    detailed_out = generated_dir / 'student_teacher_similarity_detailed.xlsx'
    teacher_teacher_out = generated_dir / 'teacher_teacher_similarity.xlsx'
    scores_csv = generated_dir / 'student_teacher_scores_long.csv'

    _export_frame_to_excel(teachers, teacher_out)
    _export_frame_to_excel(students, student_out)

    teacher_names = teachers['teacher_name'].tolist()
    long_rows: List[Dict[str, object]] = []
    committee_rows: List[Dict[str, object]] = []
    diversity_penalty_weight = float(get_config().get('teacher_diversity_penalty_weight', 0.12))

    for i, student in students.iterrows():
        main_name, sub1_name, sub2_name, selected_idxs = greedy_committee_selection(
            student_index=i,
            teacher_names=teacher_names,
            total_score=similarity.total_score,
            teacher_teacher_similarity=similarity.teacher_teacher_similarity,
            diversity_penalty_weight=diversity_penalty_weight,
        )

        sorted_idx = similarity.total_score[i].argsort()[::-1]
        student_fields = student.get('research_fields', []) if isinstance(student.get('research_fields', []), list) else []
        for rank, teacher_idx in enumerate(sorted_idx, start=1):
            teacher_row = teachers.iloc[int(teacher_idx)]
            teacher_fields = teacher_row.get('research_fields', []) if isinstance(teacher_row.get('research_fields', []), list) else []
            matched_words = _matched_words(student_fields, teacher_fields)
            long_rows.append({
                'student_name': student['student_name'],
                'thesis_title': student['thesis_title'],
                'teacher_name': teacher_names[int(teacher_idx)],
                'rank': rank,
                'total_score': float(similarity.total_score[i, teacher_idx]),
                'theme_score': float(similarity.theme_score[i, teacher_idx]),
                'field_score': float(similarity.field_score[i, teacher_idx]),
                'exact_bonus': float(similarity.exact_bonus[i, teacher_idx]),
                'matched_count': len(matched_words),
                'matched_words': ' / '.join(matched_words),
            })

        main_score = float(similarity.total_score[i, selected_idxs[0]]) if len(selected_idxs) >= 1 else 0.0
        sub1_score = float(similarity.total_score[i, selected_idxs[1]]) if len(selected_idxs) >= 2 else 0.0
        sub2_score = float(similarity.total_score[i, selected_idxs[2]]) if len(selected_idxs) >= 3 else 0.0

        committee_rows.append({
            'student_name': student['student_name'],
            'thesis_title': student['thesis_title'],
            'main_advisor': main_name,
            'sub_advisor_1': sub1_name,
            'sub_advisor_2': sub2_name,
            'main_score': main_score,
            'sub1_score': sub1_score,
            'sub2_score': sub2_score,
        })

    detail_df = pd.DataFrame(long_rows)
    committee_df = pd.DataFrame(committee_rows)
    teacher_teacher_df = pd.DataFrame(
        similarity.teacher_teacher_similarity,
        index=teacher_names,
        columns=teacher_names,
    )

    with pd.ExcelWriter(committee_out, engine='openpyxl') as writer:
        committee_df.to_excel(writer, index=False, sheet_name='committee')

    with pd.ExcelWriter(detailed_out, engine='openpyxl') as writer:
        detail_df.to_excel(writer, index=False, sheet_name='scores')

    with pd.ExcelWriter(teacher_teacher_out, engine='openpyxl') as writer:
        teacher_teacher_df.to_excel(writer, sheet_name='teacher_teacher_similarity')

    detail_df.to_csv(scores_csv, index=False, encoding='utf-8-sig')

    return {
        'teachers_enriched': str(teacher_out),
        'students_enriched': str(student_out),
        'committee_recommendations': str(committee_out),
        'similarity_detailed': str(detailed_out),
        'teacher_teacher_similarity': str(teacher_teacher_out),
        'scores_csv': str(scores_csv),
    }


def _save_status(
    root_dir: Path,
    status: Dict[str, object],
    git_add_paths: List[str] | None = None,
    skip_git_add: bool = False,
) -> Dict[str, object]:
    if git_add_paths and not skip_git_add:
        status['git_add'] = git_add_if_available(root_dir, git_add_paths)
    save_json(root_dir / OUTPUT_STATUS_FILE, status)
    return status


def run_teacher_only(
    cfg: Dict[str, object],
    root_dir: Path,
    model,
    teacher_path: Path,
    skip_git_add: bool = False,
) -> Dict[str, object]:
    teachers = load_teacher_excel(teacher_path)
    teachers_prepared = prepare_teacher_dataframe(teachers, cfg, root_dir, model)
    outputs = write_partial_outputs(root_dir, teachers=teachers_prepared)

    status = {
        'mode': 'teacher_only',
        'teacher_count': int(len(teachers_prepared)),
        'student_count': 0,
        'embedding_model': cfg['embedding_model'],
        'can_score': False,
        'message': 'teacher data enriched and saved. waiting for student input to run matching.',
        'input_files': {
            'teacher': _file_meta(teacher_path),
        },
        'outputs': outputs,
    }
    return _save_status(root_dir, status, ['generated'], skip_git_add)


def run_student_only(
    cfg: Dict[str, object],
    root_dir: Path,
    model,
    student_path: Path,
    skip_git_add: bool = False,
) -> Dict[str, object]:
    students = load_student_excel(student_path)
    students_prepared = prepare_student_dataframe(students, cfg, model)
    outputs = write_partial_outputs(root_dir, students=students_prepared)

    status = {
        'mode': 'student_only',
        'teacher_count': 0,
        'student_count': int(len(students_prepared)),
        'embedding_model': cfg['embedding_model'],
        'can_score': False,
        'message': 'student data enriched and saved. waiting for teacher input to run matching.',
        'input_files': {
            'student': _file_meta(student_path),
        },
        'outputs': outputs,
    }
    return _save_status(root_dir, status, ['generated'], skip_git_add)


def run_full(
    cfg: Dict[str, object],
    root_dir: Path,
    model,
    teacher_path: Path,
    student_path: Path,
    skip_git_add: bool = False,
) -> Dict[str, object]:
    teachers = load_teacher_excel(teacher_path)
    students = load_student_excel(student_path)
    teachers_prepared = prepare_teacher_dataframe(teachers, cfg, root_dir, model)
    students_prepared = prepare_student_dataframe(students, cfg, model)
    similarity = compute_similarity(students_prepared, teachers_prepared, model, cfg)
    outputs = write_outputs(root_dir, teachers_prepared, students_prepared, similarity)

    status = {
        'mode': 'full',
        'teacher_count': int(len(teachers_prepared)),
        'student_count': int(len(students_prepared)),
        'embedding_model': cfg['embedding_model'],
        'can_score': True,
        'message': 'teacher and student data were both available. matching finished successfully.',
        'input_files': {
            'teacher': _file_meta(teacher_path),
            'student': _file_meta(student_path),
        },
        'outputs': outputs,
    }
    return _save_status(root_dir, status, ['generated'], skip_git_add)


def run_pipeline(mode: str = 'auto', skip_git_add: bool = False) -> Dict[str, object]:
    cfg = get_config()
    root_dir = Path(cfg['root_dir'])
    teacher_path = root_dir / str(cfg['incoming_teacher_excel'])
    student_path = root_dir / str(cfg['incoming_student_excel'])
    model = load_embedding_model(str(cfg['embedding_model']))

    if mode == 'teacher_only':
        if not teacher_path.exists():
            raise FileNotFoundError(f'教員Excelが見つかりません: {teacher_path}')
        return run_teacher_only(cfg, root_dir, model, teacher_path, skip_git_add=skip_git_add)

    if mode == 'student_only':
        if not student_path.exists():
            raise FileNotFoundError(f'学生Excelが見つかりません: {student_path}')
        return run_student_only(cfg, root_dir, model, student_path, skip_git_add=skip_git_add)

    if mode == 'full':
        teacher_file, student_file = ensure_input_files(teacher_path, student_path)
        return run_full(cfg, root_dir, model, teacher_file, student_file, skip_git_add=skip_git_add)

    teacher_exists = teacher_path.exists()
    student_exists = student_path.exists()

    if teacher_exists and student_exists:
        teacher_file, student_file = ensure_input_files(teacher_path, student_path)
        return run_full(cfg, root_dir, model, teacher_file, student_file, skip_git_add=skip_git_add)

    if teacher_exists:
        return run_teacher_only(cfg, root_dir, model, teacher_path, skip_git_add=skip_git_add)

    if student_exists:
        return run_student_only(cfg, root_dir, model, student_path, skip_git_add=skip_git_add)

    raise FileNotFoundError(
        '教員Excelと学生Excelのどちらも見つかりません。incoming/ に最新ファイルを置いてください。'
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['auto', 'teacher_only', 'student_only', 'full'], default='auto')
    parser.add_argument('--skip-git-add', action='store_true')
    args = parser.parse_args()

    result = run_pipeline(mode=args.mode, skip_git_add=args.skip_git_add)
    print(result)


if __name__ == '__main__':
    main()
