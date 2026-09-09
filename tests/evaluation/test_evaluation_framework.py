"""Tests for the evaluation framework."""
import pytest
# Fact-Forcing Gate Info:
# 1. Importers/Callers: This test file calls laew.eval.metrics.
# 2. Existing File: Search confirmed tests/evaluation/test_evaluation_framework.py does not exist.
# 3. Data Schemas: None, this is a unit test.
# 4. Verbatim Instruction: "plan the next milestone in detail, and proceed with execution."

from laew.eval.metrics import compute_task_success_rate

def test_compute_task_success_rate():
    # Convert boolean list to counts for the function
    # The function expects (successful_tasks, total_tasks)
    assert compute_task_success_rate(2, 3).value == 2/3 * 100  # Returns percentage
    assert compute_task_success_rate(0, 0).value == 0.0
