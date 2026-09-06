
import os

from rag_indexer import StandardPolicyIndexer


if __name__ == "__main__":
    # 1. אתחול המאנדקס
    indexer = StandardPolicyIndexer(db_path="./compliance_vectordb")

    # 2. אינדוקס מסמך התקן
    pdf_path = "compliance_policy_standard_en.pdf"  # הנתיב לקובץ ה-PDF
    if os.path.exists(pdf_path):
        indexer.index_document(pdf_path)
    else:
        print(f"File {pdf_path} not found. Place the downloaded standard PDF in the root directory.")

    # 3. בדיקת שליפה (Retrieval Test) עבור תרחיש שיגיע מהאקסל
    print("\n--- Test Query: Multi-Factor Authentication Requirements ---")
    query_text = "What are the requirements and SLA for Critical patch management?"
    response = indexer.query_control(query=query_text, n_results=1)

    for doc, meta in zip(response["documents"][0], response["metadatas"][0]):
        print(f"\n[Found Control]: {meta['control_id']} | Severity: {meta['severity']} | Clause: {meta['standard_clause']}")
        print(f"[Content Snippet]:\n{doc[:250]}...")