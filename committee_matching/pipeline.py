from __future__ import annotations

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
    candidates = [root_dir / str(cfg['teacher_history_excel']), root_dir / str(cfg['teacher_history_csv'])]
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


def prepare_teacher_dataframe(teachers: pd.DataFrame, cfg: Dict[str, object], root_dir: Path, model) -> pd.DataFrame:
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
        final_fields = merge_manual_and_generated(row.get('manual_research_fields', ''), generated_fields, top_k=int(cfg['top_k_fields']))
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


def prepare_student_dataframe(students: pd.DataFrame, cfg: Dict[str, object], model) -> pd.DataFrame:
    matcher = FieldTaxonomyMatcher(model)
    enriched_rows: List[Dict[str, object]] = []
    for _, row in students.iterrows():
        thesis_title = normalize_text(row['thesis_title'])
        generated_fields = matcher.suggest_fields(
            [row['student_name'], thesis_title, normalize_text(row.get('department', ''))],
            top_k=int(cfg['top_k_fields']),
        )
        final_fields = merge_manual_and_generated(row.get('manual_research_fields', ''), generated_fields, top_k=int(cfg['top_k_fields']))
        enriched_rows.append({
            'student_name': normalize_text(row['student_name']),
            'department': normalize_text(row.get('department', '')),
            'thesis_title': thesis_title,
            'research_fields': final_fields,
            'research_fields_text': ' / '.join(final_fields),
        })
    return pd.DataFrame(enriched_rows)


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

    teacher_export = teachers.copy()
    student_export = students.copy()
    for df in [teacher_export, student_export]:
        for col in ['research_fields', 'trios_topics', 'trios_papers', 'past_thesis_titles']:
            if col in df.columns:
                df[col] = df[col].map(lambda xs: ' ; '.join(xs) if isinstance(xs, list) else xs)

    teacher_export.to_excel(teacher_out, index=False)
    student_export.to_excel(student_out, index=False)

    teacher_names = teachers['teacher_name'].tolist()
    long_rows: List[Dict[str, object]] = []
    committee_rows: List[Dict[str, object]] = []
    for i, student in students.iterrows():
        main_name, sub1_name, sub2_name, selected_idxs = greedy_committee_selection(
            student_index=i,
            teacher_names=teacher_names,
            total_score=similarity.total_score,
            teacher_teacher_similarity=similarity.teacher_teacher_similarity,
            diversity_penalty_weight=0.12,
        )
        sorted_idx = similarity.total_score[i].argsort()[::-1]
        for rank, teacher_idx in enumerate(sorted_idx, start=1):
            long_rows.append({
                'student_name': student['student_name'],
                'thesis_title': student['thesis_title'],
                'teacher_name': teacher_names[int(teacher_idx)],
                'rank': rank,
                'total_score': float(similarity.total_score[i, teacher_idx]),
                'theme_score': float(similarity.theme_score[i, teacher_idx]),
                'field_score': float(similarity.field_score[i, teacher_idx]),
                'lexical_score': float(similarity.lexical_score[i, teacher_idx]),
                'exact_bonus': float(similarity.exact_bonus[i, teacher_idx]),
                'calibrated_score': float(similarity.calibrated_score[i, teacher_idx]),
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
    teacher_teacher_df = pd.DataFrame(similarity.teacher_teacher_similarity, index=teacher_names, columns=teacher_names)

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


def run_pipeline() -> Dict[str, object]:
    cfg = get_config()
    root_dir = Path(cfg['root_dir'])
    teacher_path, student_path = ensure_input_files(
        root_dir / str(cfg['incoming_teacher_excel']),
        root_dir / str(cfg['incoming_student_excel']),
    )
    model = load_embedding_model(str(cfg['embedding_model']))

    teachers = load_teacher_excel(teacher_path)
    students = load_student_excel(student_path)
    teachers_prepared = prepare_teacher_dataframe(teachers, cfg, root_dir, model)
    students_prepared = prepare_student_dataframe(students, cfg, model)
    similarity = compute_similarity(students_prepared, teachers_prepared, model, cfg)
    outputs = write_outputs(root_dir, teachers_prepared, students_prepared, similarity)

    status = {
        'teacher_count': int(len(teachers_prepared)),
        'student_count': int(len(students_prepared)),
        'embedding_model': cfg['embedding_model'],
        'input_files': {
            'teacher': _file_meta(teacher_path),
            'student': _file_meta(student_path),
        },
        'outputs': outputs,
    }
    if bool(cfg.get('enable_git_add', False)):
        status['git_add'] = git_add_if_available(root_dir, ['generated', 'incoming', 'data_sources', 'sample_inputs'])
    save_json(root_dir / OUTPUT_STATUS_FILE, status)
    return status


if __name__ == '__main__':
    result = run_pipeline()
    print(result)
