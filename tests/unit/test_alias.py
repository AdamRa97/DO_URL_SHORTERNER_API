import string

import pytest

from app.core.alias import ALPHABET, generate_alias, validate_custom_alias


class TestGenerateAlias:
    def test_default_length(self):
        assert len(generate_alias()) == 7

    def test_custom_length(self):
        assert len(generate_alias(12)) == 12

    def test_charset_is_base62(self):
        for _ in range(50):
            alias = generate_alias()
            assert all(c in ALPHABET for c in alias)

    def test_uniqueness(self):
        aliases = {generate_alias() for _ in range(1000)}
        # With 62^7 possibilities, 1000 aliases should all be unique
        assert len(aliases) == 1000


class TestValidateCustomAlias:
    def test_valid_alias(self):
        assert validate_custom_alias("my-link_1") == "my-link_1"

    def test_valid_all_alpha(self):
        assert validate_custom_alias("hello") == "hello"

    def test_too_short(self):
        with pytest.raises(ValueError, match="3 and 50"):
            validate_custom_alias("ab")

    def test_too_long(self):
        with pytest.raises(ValueError, match="3 and 50"):
            validate_custom_alias("a" * 51)

    def test_exact_min_length(self):
        assert validate_custom_alias("abc") == "abc"

    def test_exact_max_length(self):
        assert validate_custom_alias("a" * 50) == "a" * 50

    def test_invalid_space(self):
        with pytest.raises(ValueError, match="only contain"):
            validate_custom_alias("my link")

    def test_invalid_special_char(self):
        with pytest.raises(ValueError, match="only contain"):
            validate_custom_alias("my@link!")

    def test_reserved_word_api(self):
        with pytest.raises(ValueError, match="reserved"):
            validate_custom_alias("api")

    def test_reserved_word_health(self):
        with pytest.raises(ValueError, match="reserved"):
            validate_custom_alias("health")

    def test_reserved_word_docs(self):
        with pytest.raises(ValueError, match="reserved"):
            validate_custom_alias("docs")

    def test_reserved_case_insensitive(self):
        with pytest.raises(ValueError, match="reserved"):
            validate_custom_alias("Health")
