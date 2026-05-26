"""
Tests for RFC §3.4 — ToolOutputValidator.

Covers:
  1. Valid output for each of the 5 registered schemas passes through unchanged.
  2. Malformed output (wrong type for a key field) -> logs ERROR, returns
     empty-but-valid dict, does NOT raise.
  3. Unknown tool name -> passes through unchanged.
  4. Empty dict as output -> returns empty-but-valid (no crash).
"""
import pytest
from unittest.mock import patch, MagicMock

from app.services.tool_validator import (
    ToolOutputValidator,
    ProductSearchOutput,
    ProductComposeOutput,
    TravelSearchHotelsOutput,
    TravelSearchFlightsOutput,
    ProductNormalizeOutput,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_valid(schema):
    """Return the empty-but-valid dict for a given schema class."""
    return schema().model_dump()


# ---------------------------------------------------------------------------
# product_search
# ---------------------------------------------------------------------------

class TestProductSearchValidator:
    TOOL = "product_search"

    VALID = {
        "product_names": ["Nike Air Max 90", "Adidas Ultra Boost 22"],
        "success": True,
    }

    def test_valid_output_passes_through(self):
        result = ToolOutputValidator.validate(self.TOOL, self.VALID)
        assert result["product_names"] == self.VALID["product_names"]
        assert result["success"] is True

    def test_valid_output_with_error_field_passes_through(self):
        output = {"product_names": [], "success": False, "error": "timeout"}
        result = ToolOutputValidator.validate(self.TOOL, output)
        assert result["product_names"] == []
        assert result["error"] == "timeout"

    def test_malformed_product_names_string_returns_empty_valid(self):
        """product_names must be a list; a string value should be quarantined."""
        output = {"product_names": "this is a string not a list", "success": True}
        with patch("app.services.tool_validator.logger") as mock_logger:
            result = ToolOutputValidator.validate(self.TOOL, output)
        mock_logger.error.assert_called_once()
        assert isinstance(result["product_names"], list)

    def test_malformed_query_int_returns_empty_valid(self):
        """An int where a list is expected triggers a Pydantic ValidationError."""
        output = {"product_names": 99, "success": True}
        with patch("app.services.tool_validator.logger") as mock_logger:
            result = ToolOutputValidator.validate(self.TOOL, output)
        mock_logger.error.assert_called_once()
        assert isinstance(result.get("product_names", []), list)

    def test_empty_dict_returns_empty_valid(self):
        with patch("app.services.tool_validator.logger"):
            result = ToolOutputValidator.validate(self.TOOL, {})
        assert isinstance(result["product_names"], list)
        assert result["product_names"] == []


# ---------------------------------------------------------------------------
# product_compose
# ---------------------------------------------------------------------------

class TestProductComposeValidator:
    TOOL = "product_compose"

    VALID = {
        "assistant_text": "Here are some great options for you.",
        "ui_blocks": [{"type": "ebay_products", "data": []}],
        "citations": ["https://ebay.com/itm/123"],
        "last_search_context": {"category": "laptops"},
        "search_history": [],
        "success": True,
    }

    def test_valid_output_passes_through(self):
        result = ToolOutputValidator.validate(self.TOOL, self.VALID)
        assert result["assistant_text"] == self.VALID["assistant_text"]
        assert result["ui_blocks"] == self.VALID["ui_blocks"]
        assert result["citations"] == self.VALID["citations"]
        assert result["success"] is True

    def test_malformed_ui_blocks_string_returns_empty_valid(self):
        output = {**self.VALID, "ui_blocks": "should be a list"}
        with patch("app.services.tool_validator.logger") as mock_logger:
            result = ToolOutputValidator.validate(self.TOOL, output)
        mock_logger.error.assert_called_once()
        assert isinstance(result["ui_blocks"], list)

    def test_malformed_citations_int_returns_empty_valid(self):
        output = {**self.VALID, "citations": 42}
        with patch("app.services.tool_validator.logger") as mock_logger:
            result = ToolOutputValidator.validate(self.TOOL, output)
        mock_logger.error.assert_called_once()
        assert isinstance(result["citations"], list)

    def test_empty_dict_returns_empty_valid(self):
        with patch("app.services.tool_validator.logger"):
            result = ToolOutputValidator.validate(self.TOOL, {})
        assert isinstance(result["ui_blocks"], list)
        assert isinstance(result["citations"], list)
        assert result["assistant_text"] == ""

    def test_follow_up_question_preserved(self):
        """Regression for the 2026-05-26 prod-verification gap: the
        composer emits ``follow_up_question`` (per
        ``backend/mcp_server/tools/product_compose.py:1461``) and chat.py
        emits a dedicated SSE event for it. If this field isn't declared
        on the Pydantic schema, ``model_dump()`` silently strips it and
        the SSE event never fires, regardless of any downstream
        passthrough fix. Lock in that a real value survives validation."""
        output = {
            **self.VALID,
            "follow_up_question": "Want me to compare these on noise cancellation?",
        }
        result = ToolOutputValidator.validate(self.TOOL, output)
        assert result.get("follow_up_question") == (
            "Want me to compare these on noise cancellation?"
        )

    def test_follow_up_question_defaults_to_none(self):
        """Composer didn't emit a follow-up — validator should still
        present the key (so downstream ``.get()`` is unambiguous)."""
        result = ToolOutputValidator.validate(self.TOOL, self.VALID)
        assert "follow_up_question" in result
        assert result["follow_up_question"] is None


# ---------------------------------------------------------------------------
# travel_search_hotels
# ---------------------------------------------------------------------------

class TestTravelSearchHotelsValidator:
    TOOL = "travel_search_hotels"

    VALID = {
        "hotels": [
            {
                "type": "plp_link",
                "provider": "expedia",
                "destination": "Paris",
                "search_url": "https://expedia.com/search",
                "title": "Hotels in Paris",
            }
        ],
        "citations": ["https://expedia.com/search"],
        "success": True,
    }

    def test_valid_output_passes_through(self):
        result = ToolOutputValidator.validate(self.TOOL, self.VALID)
        assert len(result["hotels"]) == 1
        assert result["hotels"][0]["destination"] == "Paris"
        assert result["success"] is True

    def test_malformed_hotels_string_returns_empty_valid(self):
        output = {"hotels": "error string instead of list", "citations": [], "success": False}
        with patch("app.services.tool_validator.logger") as mock_logger:
            result = ToolOutputValidator.validate(self.TOOL, output)
        mock_logger.error.assert_called_once()
        assert isinstance(result["hotels"], list)

    def test_malformed_citations_dict_returns_empty_valid(self):
        output = {**self.VALID, "citations": {"bad": "type"}}
        with patch("app.services.tool_validator.logger") as mock_logger:
            result = ToolOutputValidator.validate(self.TOOL, output)
        mock_logger.error.assert_called_once()
        assert isinstance(result["citations"], list)

    def test_empty_dict_returns_empty_valid(self):
        with patch("app.services.tool_validator.logger"):
            result = ToolOutputValidator.validate(self.TOOL, {})
        assert isinstance(result["hotels"], list)
        assert result["hotels"] == []


# ---------------------------------------------------------------------------
# travel_search_flights
# ---------------------------------------------------------------------------

class TestTravelSearchFlightsValidator:
    TOOL = "travel_search_flights"

    VALID = {
        "flights": [
            {
                "type": "plp_link",
                "provider": "expedia",
                "origin": "London",
                "destination": "Tokyo",
                "search_url": "https://expedia.com/flights",
                "title": "Round-trip flights from London to Tokyo",
            }
        ],
        "citations": ["https://expedia.com/flights"],
        "success": True,
    }

    def test_valid_output_passes_through(self):
        result = ToolOutputValidator.validate(self.TOOL, self.VALID)
        assert len(result["flights"]) == 1
        assert result["success"] is True

    def test_malformed_flights_string_returns_empty_valid(self):
        output = {"flights": "error string", "citations": [], "success": False}
        with patch("app.services.tool_validator.logger") as mock_logger:
            result = ToolOutputValidator.validate(self.TOOL, output)
        mock_logger.error.assert_called_once()
        assert isinstance(result["flights"], list)

    def test_malformed_citations_integer_returns_empty_valid(self):
        output = {**self.VALID, "citations": 99}
        with patch("app.services.tool_validator.logger") as mock_logger:
            result = ToolOutputValidator.validate(self.TOOL, output)
        mock_logger.error.assert_called_once()
        assert isinstance(result["citations"], list)

    def test_empty_dict_returns_empty_valid(self):
        with patch("app.services.tool_validator.logger"):
            result = ToolOutputValidator.validate(self.TOOL, {})
        assert isinstance(result["flights"], list)
        assert result["flights"] == []


# ---------------------------------------------------------------------------
# product_normalize
# ---------------------------------------------------------------------------

class TestProductNormalizeValidator:
    TOOL = "product_normalize"

    VALID = {
        "normalized_products": [
            {
                "id": "product_0",
                "name": "MacBook Pro 14",
                "url": "ai://product/1/macbook-pro-14",
                "snippet": "Product suggestion from OpenAI: MacBook Pro 14",
                "score": 0.95,
                "pros": ["great display"],
                "cons": ["expensive"],
                "best_offer": None,
                "badges": [],
            }
        ],
        "success": True,
    }

    def test_valid_output_passes_through(self):
        result = ToolOutputValidator.validate(self.TOOL, self.VALID)
        assert len(result["normalized_products"]) == 1
        assert result["normalized_products"][0]["name"] == "MacBook Pro 14"
        assert result["success"] is True

    def test_malformed_normalized_products_string_returns_empty_valid(self):
        output = {"normalized_products": "this should be a list", "success": True}
        with patch("app.services.tool_validator.logger") as mock_logger:
            result = ToolOutputValidator.validate(self.TOOL, output)
        mock_logger.error.assert_called_once()
        assert isinstance(result["normalized_products"], list)

    def test_malformed_normalized_products_dict_returns_empty_valid(self):
        """A plain dict instead of a list should be quarantined."""
        output = {"normalized_products": {"name": "Sony WH-1000XM5"}, "success": True}
        with patch("app.services.tool_validator.logger") as mock_logger:
            result = ToolOutputValidator.validate(self.TOOL, output)
        mock_logger.error.assert_called_once()
        assert isinstance(result["normalized_products"], list)

    def test_empty_dict_returns_empty_valid(self):
        with patch("app.services.tool_validator.logger"):
            result = ToolOutputValidator.validate(self.TOOL, {})
        assert isinstance(result["normalized_products"], list)
        assert result["normalized_products"] == []


# ---------------------------------------------------------------------------
# Unknown tool — pass-through
# ---------------------------------------------------------------------------

class TestUnknownToolPassthrough:
    def test_unknown_tool_passes_through_unchanged(self):
        output = {"anything": "goes", "random_key": 42}
        result = ToolOutputValidator.validate("unknown_tool", output)
        assert result == output

    def test_unregistered_tool_no_schema_check(self):
        output = {"search_results": "this would fail product_search schema"}
        result = ToolOutputValidator.validate("general_search", output)
        assert result == output

    def test_empty_tool_name_passes_through(self):
        output = {"foo": "bar"}
        result = ToolOutputValidator.validate("", output)
        assert result == output


# ---------------------------------------------------------------------------
# Edge-cases that must never raise
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_none_values_in_output_do_not_raise(self):
        output = {"product_names": None, "success": None}
        # None is valid for Optional fields
        result = ToolOutputValidator.validate("product_search", output)
        assert "product_names" in result

    def test_extra_keys_in_output_are_dropped_gracefully(self):
        """Pydantic by default ignores extra fields."""
        output = {
            "product_names": ["SomePhone"],
            "success": True,
            "extra_unexpected_key": "whatever",
        }
        result = ToolOutputValidator.validate("product_search", output)
        assert result["product_names"] == ["SomePhone"]

    def test_validate_does_not_raise_on_completely_wrong_type(self):
        """Even if the whole output is a string (not a dict), must not raise."""
        # This tests the except (TypeError, AttributeError) branch in validate().
        # product_search(**"not a dict") raises TypeError, which is caught and
        # quarantined.  pytest itself will report any unexpected exception as a
        # test failure — no explicit try/except wrapper needed.
        with patch("app.services.tool_validator.logger") as mock_logger:
            result = ToolOutputValidator.validate("product_search", "not a dict")  # type: ignore[arg-type]
        mock_logger.error.assert_called_once()
        assert isinstance(result.get("product_names", []), list)
