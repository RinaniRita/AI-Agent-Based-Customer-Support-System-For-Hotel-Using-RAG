import re
from pathlib import Path
from typing import List, Dict
import tiktoken

# -------- CONFIG -------- #
CHUNK_SIZE = 500
CHUNK_OVERLAP = 80
ENCODING_MODEL = "cl100k_base"
# ------------------------ #

encoding = tiktoken.get_encoding(ENCODING_MODEL)


def count_tokens(text: str) -> int:
    return len(encoding.encode(text))


def split_by_headings(content: str) -> List[str]:
    """
    Split markdown content by ## headings.
    Keeps the heading with its section.
    """
    sections = re.split(r"\n## ", content)
    cleaned_sections = []

    for i, section in enumerate(sections):
        if i == 0:
            # first section may include intro before first heading
            cleaned_sections.append(section.strip())
        else:
            cleaned_sections.append("## " + section.strip())

    return [s for s in cleaned_sections if s.strip()]


def chunk_with_overlap(text: str) -> List[str]:
    tokens = encoding.encode(text)
    chunks = []

    start = 0
    while start < len(tokens):
        end = start + CHUNK_SIZE
        chunk_tokens = tokens[start:end]
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)

        start += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks


def extract_metadata(content: str) -> Dict:
    """
    Extract YAML front-matter metadata.
    """
    metadata = {}
    match = re.search(r"---(.*?)---", content, re.DOTALL)

    if match:
        yaml_block = match.group(1)
        lines = yaml_block.strip().split("\n")
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()

    return metadata


def remove_metadata_block(content: str) -> str:
    return re.sub(r"---(.*?)---", "", content, flags=re.DOTALL).strip()


def process_markdown_file(filepath: Path, base_path: Path) -> List[Dict]:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    metadata = extract_metadata(content)
    clean_content = remove_metadata_block(content)

    sections = split_by_headings(clean_content)

    all_chunks = []
    chunk_id = 0

    # Add folder info to metadata
    folder_path = filepath.parent.relative_to(base_path)
    metadata["folder"] = str(folder_path)

    for section in sections:
        token_count = count_tokens(section)

        if token_count <= CHUNK_SIZE:
            all_chunks.append({
                "id": f"{filepath.stem}_{chunk_id}",
                "text": section,
                "metadata": {
                    **metadata,
                    "file_name": filepath.name,
                    "section_source": "direct",
                }
            })
            chunk_id += 1
        else:
            split_chunks = chunk_with_overlap(section)
            for chunk in split_chunks:
                all_chunks.append({
                    "id": f"{filepath.stem}_{chunk_id}",
                    "text": chunk,
                    "metadata": {
                        **metadata,
                        "file_name": filepath.name,
                        "section_source": "split",
                    }
                })
                chunk_id += 1

    return all_chunks


def process_kb_folder(folder_path: str) -> List[Dict]:
    base_path = Path(folder_path)
    all_documents = []

    # Collect all .md files
    md_files = list(base_path.rglob("*.md"))
    print(f"Found {len(md_files)} markdown files in {folder_path}")

    for md_file in md_files:
        print(f"Processing: {md_file}")
        chunks = process_markdown_file(md_file, base_path)
        all_documents.extend(chunks)
        print(f"  -> Generated {len(chunks)} chunks")

    print(f"Total chunks from all files: {len(all_documents)}")
    return all_documents


if __name__ == "__main__":
    kb_path = "data/knowledge_base/Apollo_Hotel_KB"
    documents = process_kb_folder(kb_path)

    print(f"\nTotal Chunks Created: {len(documents)}")

    # Debug preview
    for doc in documents[:2]:
        print("\n---")
        print("ID:", doc["id"])
        print("Metadata:", doc["metadata"])
        print("Text Preview:", doc["text"][:200])
