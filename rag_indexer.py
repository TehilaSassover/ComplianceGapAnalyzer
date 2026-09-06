import os
import re
from typing import List, Dict, Any
import chromadb
from chromadb.utils import embedding_functions
from pypdf import PdfReader
from docx import Document


class StandardPolicyIndexer:
    def __init__(self, db_path: str = "./chroma_db", collection_name: str = "security_standards"):
        # חיבור ל-ChromaDB מקומי
        self.client = chromadb.PersistentClient(path=db_path)
        
        # מודל Embedding מקומי ויעיל (מתאים לטקסטים טכניים באנגלית)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn
        )

    def extract_text_from_file(self, file_path: str) -> str:
        """חילוץ טקסט גולמי מקובץ PDF או Word."""
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == ".pdf":
            reader = PdfReader(file_path)
            return "\n".join([page.extract_text() or "" for page in reader.pages])
        
        elif ext in [".docx", ".doc"]:
            doc = Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs if p.text])
        
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    def chunk_by_controls(self, raw_text: str) -> List[Dict[str, Any]]:
        """
        פירוק הטקסט לפי בקרות (SEC-ISO-X.X או SEC-XXX).
        מחלץ את המזהה, רמת החומרה, והסעיף התואם לתוך Metadata.
        """
        # ביטוי רגולרי לזיהוי כותרת של בקרה
        control_pattern = r"(SEC-[A-Z]+-\d+\.?\d*)"
        splits = re.split(control_pattern, raw_text)
        
        chunks = []
        
        # אם הטקסט מתחיל לפני הבקרה הראשונה, נדלג על ההקדמה או נשמור ככללי
        for i in range(1, len(splits), 2):
            control_id = splits[i].strip()
            control_content = splits[i+1].strip()
            
            full_chunk_text = f"{control_id} {control_content}"
            
            # חילוץ מטא-דאטה מובנה מהטקסט
            severity = "Medium"
            if re.search(r"Severity:\s*Critical|חומרה:\s*קריטי", full_chunk_text, re.IGNORECASE):
                severity = "Critical"
            elif re.search(r"Severity:\s*High|חומרה:\s*גבוה", full_chunk_text, re.IGNORECASE):
                severity = "High"

            clause_match = re.search(r"ISO\s*27001\s*(?:Clause\s*)?([A-Z0-9\.\/]+)", full_chunk_text, re.IGNORECASE)
            clause = clause_match.group(0) if clause_match else "N/A"

            chunks.append({
                "id": control_id,
                "text": full_chunk_text,
                "metadata": {
                    "control_id": control_id,
                    "severity": severity,
                    "standard_clause": clause,
                    "doc_type": "security_standard"
                }
            })
            
        return chunks

    def index_document(self, file_path: str):
        """טעינה, חלוקה ואינדוקס ב-ChromaDB."""
        print(f"[+] Processing file: {file_path}")
        raw_text = self.extract_text_from_file(file_path)
        chunks = self.chunk_by_controls(raw_text)
        
        if not chunks:
            print("[-] No controls identified with matching regex. Fallback to standard chunking needed.")
            return

        documents = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        ids = [f"{c['id']}_{idx}" for idx, c in enumerate(chunks)]

        # הוספה או עדכון ב-Collection
        self.collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"[✓] Successfully indexed {len(chunks)} controls into ChromaDB.")

    def query_control(self, query: str, n_results: int = 2, filter_severity: str = None) -> Dict[str, Any]:
        """שאילתת בדיקה לווקטורים."""
        where_clause = {"severity": filter_severity} if filter_severity else None
        
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_clause
        )
        return results