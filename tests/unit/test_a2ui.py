import json
import pytest
from google.genai import types
from google.adk.models.llm_response import LlmResponse
from app.a2ui_utils import a2ui_callback, _FALLBACK_TEXT

def test_a2ui_callback_plain_text():
    resp = LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text="Hello, here are some cars.")]
        )
    )
    result = a2ui_callback(None, resp)
    assert result is None

def test_a2ui_callback_valid_a2ui():
    a2ui_json = [
        {"beginRendering": {"surfaceId": "card1", "root": "root_card"}},
        {
            "surfaceUpdate": {
                "surfaceId": "card1",
                "components": [
                    {"id": "root_card", "component": {"Card": {"child": "col1"}}},
                    {"id": "col1", "component": {"Column": {"children": {"explicitList": ["t1"]}}}},
                    {"id": "t1", "component": {"Text": {"text": {"literalString": "2024 BMW M3"}, "usageHint": "h1"}}}
                ]
            }
        }
    ]
    resp = LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=json.dumps(a2ui_json))]
        )
    )
    result = a2ui_callback(None, resp)
    assert result is not None
    assert result.custom_metadata == {"a2a:response": "true"}
    assert len(result.content.parts) == 2
    # Verify wrapped blob format
    part_blob = result.content.parts[0].inline_data.data
    assert b"<a2a_datapart_json>" in part_blob

def test_a2ui_callback_broken_surface_fallback():
    # Surface where root is undefined
    broken_json = [
        {"beginRendering": {"surfaceId": "card1", "root": "non_existent_root"}},
        {
            "surfaceUpdate": {
                "surfaceId": "card1",
                "components": [
                    {"id": "t1", "component": {"Text": {"text": {"literalString": "test"}}}}
                ]
            }
        }
    ]
    resp = LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=json.dumps(broken_json))]
        )
    )
    result = a2ui_callback(None, resp)
    assert result is not None
    assert result.content.parts[0].text == _FALLBACK_TEXT
