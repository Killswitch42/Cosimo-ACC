from app.services.ares_service import _names_roughly_match, validate_dic_format


def test_valid_czech_dic():
    errors = validate_dic_format("CZ12345678")
    assert errors == []


def test_valid_czech_dic_10_digits():
    errors = validate_dic_format("CZ1234567890")
    assert errors == []


def test_invalid_dic_non_numeric():
    errors = validate_dic_format("CZ1234ABCD")
    assert len(errors) > 0


def test_invalid_dic_too_short():
    errors = validate_dic_format("CZ123")
    assert len(errors) > 0


def test_eu_dic_passes_format_check():
    errors = validate_dic_format("DE123456789")
    assert errors == []


def test_name_match_sro_variants():
    assert _names_roughly_match("Novák s.r.o.", "Novák s. r. o.")
    assert _names_roughly_match("ACME a.s.", "ACME a. s.")


def test_name_mismatch_detected():
    assert not _names_roughly_match("Novák s.r.o.", "Svoboda s.r.o.")
