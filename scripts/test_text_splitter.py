#!/usr/bin/env python3

from langchain_text_splitters import RecursiveCharacterTextSplitter

def test_text_splitter():
    """Test the langchain text splitter with a sample text"""
    text = """This is a test opinion document. It contains multiple sentences and paragraphs.

This is a second paragraph. It should be split into chunks.

This is a third paragraph with more content to ensure we have enough text to create multiple chunks.
The RecursiveCharacterTextSplitter will try to split on natural boundaries like paragraphs and sentences.

Let's add some more text to make sure we get multiple chunks."""

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=100,
        chunk_overlap=20,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    
    chunks = text_splitter.split_text(text)
    
    print(f"Split text into {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i+1} ({len(chunk)} chars): {chunk}")

if __name__ == "__main__":
    test_text_splitter()
