"""
Ragas Evaluation Script for Advanced RAG Pipeline
=================================================
"""
import sys, io
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import os
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy
from langchain_anthropic import ChatAnthropic
from langchain_huggingface import HuggingFaceEmbeddings

# Import from our advanced pipeline
import rag_advanced
from rag_advanced import load_indices, build_retriever, rag_query, build_embeddings

def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY must be set to run Ragas evaluation.")
        return

    print("Setting up Ragas evaluation...")
    embeddings = build_embeddings()
    faiss_vs, bm25_retriever = load_indices(embeddings)
    faiss_vs, bm25_retriever, cross_encoder = build_retriever(faiss_vs, bm25_retriever)
    
    questions = [
        "PDPA คืออะไร",
        "การกระทำความผิดเกี่ยวกับคอมพิวเตอร์มีโทษอย่างไร",
    ]
    
    answers = []
    contexts = []
    
    for q in questions:
        print(f"\n--- Running pipeline for: {q}")
        res = rag_query(faiss_vs, bm25_retriever, cross_encoder, q)
        answers.append(res["answer"])
        # Format contexts as list of strings
        context_strs = [doc.page_content.replace("passage: ", "", 1) for doc in res["docs"]]
        contexts.append(context_strs)
        
    data = {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
    }
    dataset = Dataset.from_dict(data)
    
    # Ragas configuration
    print("\nConfiguring Ragas with Anthropic Claude and HuggingFace Embeddings...")
    llm = ChatAnthropic(model_name="claude-3-haiku-20240307", temperature=0) # Use claude-3-haiku for evaluation for speed
    embed_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2") # Fast embeddings for evaluation
    
    print("Evaluating metrics (Faithfulness, Answer Relevancy)...")
    try:
        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy],
            llm=llm,
            embeddings=embed_model,
            raise_exceptions=False,
        )
        print("\n" + "="*50)
        print("RAGAS EVALUATION RESULTS")
        print("="*50)
        print(result)
        
        # Display individual scores
        df = result.to_pandas()
        print("\nDetailed Scores:")
        for idx, row in df.iterrows():
            print(f"\nQ: {row['question']}")
            print(f"Faithfulness: {row.get('faithfulness', 'N/A')}")
            print(f"Answer Relevancy: {row.get('answer_relevancy', 'N/A')}")
            
    except Exception as e:
        print(f"\nEvaluation failed: {e}")

if __name__ == "__main__":
    main()
