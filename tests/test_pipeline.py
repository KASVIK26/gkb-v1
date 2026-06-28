from pathlib import Path

from curator.loader import build_load_query
from curator.run_pipeline import load_dataset_registry, select_downloaded_datasets


def test_build_load_query_uses_merge_only():
    query = build_load_query()
    assert "MERGE (g:Gene" in query
    assert "CREATE" not in query


def test_select_downloaded_datasets_filters_registry(tmp_path: Path):
    registry_path = tmp_path / "datasets.yaml"
    registry_path.write_text(
        """
datasets:
  - id: wheat_iwgsc_gff3
    status: downloaded
  - id: soybean_wm82_v6
    status: not_downloaded
""".strip(),
        encoding="utf-8",
    )

    registry = load_dataset_registry(registry_path)
    downloaded = select_downloaded_datasets(registry)

    assert [dataset["id"] for dataset in downloaded] == ["wheat_iwgsc_gff3"]
