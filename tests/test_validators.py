"""
Tests for src/utils/validators.py

Covers:
- validate_asin: valid B0-prefixed ASINs, invalid formats, empty, None
- validate_upc: valid 12/13-digit codes, invalid lengths, non-numeric
- validate_price: positive Decimal, zero, negative, non-Decimal, boundaries
- validate_quantity: positive int, zero, negative, non-int
- sanitize_string: truncation, None, empty, whitespace stripping
- generate_po_id: format, uniqueness across calls
"""

import time
from decimal import Decimal

import pytest

from src.utils.validators import (
    validate_asin,
    validate_upc,
    validate_price,
    validate_quantity,
    sanitize_string,
    generate_po_id,
)


# ============================================================================
# validate_asin tests
# ============================================================================
class TestValidateAsin:
    """Tests for ASIN validation (10 chars, starts with B0, alphanumeric)."""

    def test_valid_asin_uppercase(self):
        assert validate_asin("B0ABCD1234") is True

    def test_valid_asin_lowercase_converted(self):
        """Lowercase input should be uppercased internally and still match."""
        assert validate_asin("b0abcd1234") is True

    def test_valid_asin_mixed_case(self):
        assert validate_asin("B0aBcD1234") is True

    def test_valid_asin_all_digits_after_b0(self):
        assert validate_asin("B012345678") is True

    def test_valid_asin_all_letters_after_b0(self):
        assert validate_asin("B0ABCDEFGH") is True

    def test_invalid_asin_wrong_prefix(self):
        """ASINs must start with B0."""
        assert validate_asin("A0ABCD1234") is False

    def test_invalid_asin_too_short(self):
        assert validate_asin("B0ABC") is False

    def test_invalid_asin_too_long(self):
        assert validate_asin("B0ABCD12345") is False

    def test_invalid_asin_special_characters(self):
        assert validate_asin("B0ABCD12#$") is False

    def test_invalid_asin_spaces(self):
        assert validate_asin("B0ABCD 234") is False

    def test_invalid_asin_empty_string(self):
        assert validate_asin("") is False

    def test_invalid_asin_none(self):
        assert validate_asin(None) is False

    def test_invalid_asin_numeric_input(self):
        """Non-string input should return False."""
        assert validate_asin(1234567890) is False

    def test_invalid_asin_only_b0(self):
        assert validate_asin("B0") is False

    def test_invalid_asin_starts_with_b1(self):
        assert validate_asin("B1ABCD1234") is False


# ============================================================================
# validate_upc tests
# ============================================================================
class TestValidateUpc:
    """Tests for UPC/EAN validation (12 or 13 digits)."""

    def test_valid_upc_12_digits(self):
        assert validate_upc("012345678901") is True

    def test_valid_upc_13_digits(self):
        """13-digit EAN codes should also be valid."""
        assert validate_upc("0123456789012") is True

    def test_invalid_upc_11_digits(self):
        assert validate_upc("01234567890") is False

    def test_invalid_upc_14_digits(self):
        assert validate_upc("01234567890123") is False

    def test_invalid_upc_letters(self):
        assert validate_upc("0123456789AB") is False

    def test_invalid_upc_mixed(self):
        assert validate_upc("0123456789a1") is False

    def test_invalid_upc_spaces(self):
        assert validate_upc("012345 78901") is False

    def test_invalid_upc_empty(self):
        assert validate_upc("") is False

    def test_invalid_upc_none(self):
        assert validate_upc(None) is False

    def test_invalid_upc_integer(self):
        """Non-string input should return False."""
        assert validate_upc(123456789012) is False

    def test_valid_upc_all_zeros(self):
        assert validate_upc("000000000000") is True

    def test_valid_upc_all_nines(self):
        assert validate_upc("999999999999") is True


# ============================================================================
# validate_price tests
# ============================================================================
class TestValidatePrice:
    """Tests for price validation (0.01 to 10000.00)."""

    def test_valid_price_normal(self):
        assert validate_price(Decimal("29.99")) is True

    def test_valid_price_minimum_boundary(self):
        """Exactly $0.01 should be valid."""
        assert validate_price(Decimal("0.01")) is True

    def test_valid_price_maximum_boundary(self):
        """Exactly $10,000.00 should be valid."""
        assert validate_price(Decimal("10000.00")) is True

    def test_valid_price_one_dollar(self):
        assert validate_price(Decimal("1.00")) is True

    def test_valid_price_integer_like(self):
        assert validate_price(Decimal("100")) is True

    def test_invalid_price_zero(self):
        assert validate_price(Decimal("0")) is False

    def test_invalid_price_negative(self):
        assert validate_price(Decimal("-10.00")) is False

    def test_invalid_price_too_high(self):
        assert validate_price(Decimal("10000.01")) is False

    def test_invalid_price_very_small(self):
        """Below minimum $0.01."""
        assert validate_price(Decimal("0.001")) is False

    def test_valid_price_from_float(self):
        """Float input should be coerced to Decimal internally."""
        assert validate_price(29.99) is True

    def test_valid_price_from_int(self):
        """Integer input should be coerced to Decimal internally."""
        assert validate_price(50) is True

    def test_valid_price_from_string(self):
        """String input should be coerced to Decimal internally."""
        assert validate_price("15.50") is True

    def test_invalid_price_non_numeric_string(self):
        assert validate_price("abc") is False

    def test_invalid_price_none(self):
        assert validate_price(None) is False


# ============================================================================
# validate_quantity tests
# ============================================================================
class TestValidateQuantity:
    """Tests for quantity validation (positive integer)."""

    def test_valid_quantity(self):
        assert validate_quantity(10) is True

    def test_valid_quantity_one(self):
        assert validate_quantity(1) is True

    def test_valid_quantity_large(self):
        assert validate_quantity(100000) is True

    def test_invalid_quantity_zero(self):
        assert validate_quantity(0) is False

    def test_invalid_quantity_negative(self):
        assert validate_quantity(-5) is False

    def test_invalid_quantity_float(self):
        assert validate_quantity(5.5) is False

    def test_invalid_quantity_string(self):
        assert validate_quantity("10") is False

    def test_invalid_quantity_none(self):
        assert validate_quantity(None) is False


# ============================================================================
# sanitize_string tests
# ============================================================================
class TestSanitizeString:
    """Tests for string sanitization (strip + truncate)."""

    def test_normal_string(self):
        assert sanitize_string("Hello World") == "Hello World"

    def test_strips_whitespace(self):
        assert sanitize_string("  hello  ") == "hello"

    def test_truncation_at_max_length(self):
        result = sanitize_string("abcdefghij", max_length=5)
        assert result == "abcde"
        assert len(result) == 5

    def test_truncation_default_max_length(self):
        """Default max_length is 500."""
        long_string = "x" * 1000
        result = sanitize_string(long_string)
        assert len(result) == 500

    def test_none_input(self):
        assert sanitize_string(None) == ""

    def test_empty_string(self):
        assert sanitize_string("") == ""

    def test_whitespace_only(self):
        """String of only spaces should be stripped to empty."""
        assert sanitize_string("   ") == ""

    def test_string_shorter_than_max(self):
        result = sanitize_string("short", max_length=100)
        assert result == "short"

    def test_string_exactly_max_length(self):
        result = sanitize_string("12345", max_length=5)
        assert result == "12345"

    def test_strips_then_truncates(self):
        """Whitespace should be stripped first, then truncation applied."""
        result = sanitize_string("  abcdef  ", max_length=4)
        assert result == "abcd"

    def test_newlines_and_tabs(self):
        result = sanitize_string("\t hello \n")
        assert result == "hello"


# ============================================================================
# generate_po_id tests
# ============================================================================
class TestGeneratePoId:
    """Tests for PO ID generation (format: PO-{ASIN}-{SUPPLIER_ID}-{TIMESTAMP})."""

    def test_format(self):
        po_id = generate_po_id("B0ABCD1234", 42)
        assert po_id.startswith("PO-B0ABCD1234-42-")

    def test_contains_timestamp(self):
        po_id = generate_po_id("B0ABCD1234", 1)
        parts = po_id.split("-")
        # Format: PO-ASIN-SUPPLIERID-TIMESTAMP
        # After splitting: ['PO', 'B0ABCD1234', '1', 'YYYYMMDDHHMMSS']
        timestamp_part = parts[-1]
        assert len(timestamp_part) == 14  # YYYYMMDDHHmmSS
        assert timestamp_part.isdigit()

    def test_different_inputs_produce_different_ids(self):
        po_id_1 = generate_po_id("B0ABCD1234", 1)
        po_id_2 = generate_po_id("B0EFGH5678", 2)
        assert po_id_1 != po_id_2

    def test_uniqueness_sequential_calls(self):
        """Two rapid calls should ideally produce different IDs due to timestamp."""
        po_id_1 = generate_po_id("B0ABCD1234", 1)
        time.sleep(1.1)  # Sleep just over 1 second for timestamp difference
        po_id_2 = generate_po_id("B0ABCD1234", 1)
        assert po_id_1 != po_id_2

    def test_supplier_id_in_output(self):
        po_id = generate_po_id("B0ABCD1234", 999)
        assert "-999-" in po_id

    def test_asin_in_output(self):
        po_id = generate_po_id("B0TESTTEST", 5)
        assert "B0TESTTEST" in po_id
