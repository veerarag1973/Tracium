# llm.guard — Safety Classifier

> **Auto-documented module:** `tracium.namespaces.guard`

## Field reference

| Field | Type | Description |
|-------|------|-------------|
| `blocked` | `bool` | `True` if the content was blocked by the safety classifier. |
| `classifier` | `str` | Classifier identifier (e.g. `"openai-moderation"`, `"llama-guard-2"`). |
| `categories` | `dict[str, float]` | Map of harm category to confidence score. |
| `flagged_categories` | `list[str]` | Categories that exceeded the block threshold. |
| `threshold` | `float \| None` | Block threshold applied. |

## Example

```python
from tracium.namespaces.guard import GuardPayload

payload = GuardPayload(
    blocked=True,
    classifier="llama-guard-2",
    categories={"violence": 0.03, "self-harm": 0.91},
    flagged_categories=["self-harm"],
    threshold=0.8,
)
```
