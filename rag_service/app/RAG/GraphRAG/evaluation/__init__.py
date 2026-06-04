"""
RAG Evaluation Framework
=========================
Modular evaluation for retriever quality, generation quality (RAGAS),
and end-to-end GraphRAG pipeline performance.
"""

from .ground_truth import EvalSample, load_ground_truth, save_ground_truth
from .retriever_metrics import evaluate_retriever
from .generation_metrics import evaluate_generation
