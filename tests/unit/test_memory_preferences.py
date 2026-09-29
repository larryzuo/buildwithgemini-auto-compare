import pytest
from unittest.mock import AsyncMock, MagicMock
from app.user_preferences import remember_car_preference, get_remembered_car_preferences

@pytest.mark.asyncio
async def test_remember_car_preference_via_tool_context():
    mock_context = MagicMock()
    mock_context.add_memory = AsyncMock()

    res = await remember_car_preference(
        preference="Prefers electric SUVs under $70,000",
        category="powertrain",
        tool_context=mock_context,
    )

    assert res["status"] == "success"
    assert "electric SUVs" in res["message"]
    mock_context.add_memory.assert_called_once()
    saved_entries = mock_context.add_memory.call_args.kwargs["memories"]
    assert len(saved_entries) == 1
    text = saved_entries[0].content.parts[0].text
    assert "User car preference (powertrain): Prefers electric SUVs under $70,000" == text

@pytest.mark.asyncio
async def test_get_remembered_car_preferences_via_tool_context():
    mock_context = MagicMock()
    mock_response = MagicMock()
    mock_memory = MagicMock()
    mock_part = MagicMock()
    mock_part.text = "User car preference (brand): Prefers BMW and Porsche"
    mock_memory.content.parts = [mock_part]
    mock_response.memories = [mock_memory]
    mock_context.search_memory = AsyncMock(return_value=mock_response)

    res = await get_remembered_car_preferences(
        query="brand preferences",
        tool_context=mock_context,
    )

    assert res["status"] == "success"
    assert res["preferences_count"] == 1
    assert "Prefers BMW and Porsche" in res["preferences"][0]
