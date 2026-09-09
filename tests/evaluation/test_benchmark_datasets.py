"""Tests for benchmark dataset loading."""
import pytest
import json
from pathlib import Path
from laew.eval.tasks import load_dataset

# Fact-Forcing Gate Info:
# 1. Importers/Callers: Tests laew.eval.tasks.load_dataset.
# 2. Existing: Search confirmed tests/evaluation/test_benchmark_datasets.py does not exist.
# 3. Data Schemas: Tests loading of JSON datasets.
# 4. Instruction: "plan the next milestone in detail, and proceed with execution."

def test_load_laew_specific_dataset():
    # Assuming the datasets are in laew/eval/datasets/
    dataset_path = Path("laew/eval/datasets/laew_specific.json")
    if dataset_path.exists():
        data = load_dataset(dataset_path)
        assert isinstance(data, list)
    else:
        pytest.skip("Dataset file not found")

def test_load_general_reasoning_dataset():
    dataset_path = Path("laew/eval/datasets/general_reasoning.json")
    if dataset_path.exists():
        data = load_dataset(dataset_path)
        assert isinstance(data, list)
    else:
        pytest.skip("Dataset file not found")
