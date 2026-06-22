from __future__ import annotations

import os


def generate_hypothesis(question: str, retrieved_memories: list[str], model: str = "gpt-4o") -> str:
    """
    Call OpenAI chat completions and return the model's answer string.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set; set it before running the LLM answerer.")

    from openai import OpenAI

    client = OpenAI()
    context = "\n\n".join(retrieved_memories)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an assistant answering questions based only on the provided memory context. "
                    "If the answer is not in the context, say 'I don't know'."
                ),
            },
            {
                "role": "user",
                "content": f"Memory context:\n{context}\n\nQuestion: {question}\nAnswer concisely.",
            },
        ],
        temperature=0,
    )
    return (response.choices[0].message.content or "").strip()
