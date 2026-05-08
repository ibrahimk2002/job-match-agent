from unittest.mock import MagicMock, patch


def test_extract_resume_profile_raises_on_null_output():
    """MalformedOutputError is raised when output_parsed is None."""
    from integrations import MalformedOutputError
    from integrations.openai_client import extract_resume_profile
    from config.user_profile import ResumeExtractionResult

    mock_response = MagicMock()
    mock_response.output_parsed = None
    mock_response.usage = MagicMock()

    mock_client = MagicMock()
    mock_client.responses.parse.return_value = mock_response

    import pytest
    with patch("integrations.openai_client.get_openai_client", return_value=mock_client):
        with pytest.raises(MalformedOutputError):
            extract_resume_profile(
                system_prompt="test prompt",
                resume_text="some resume text",
                model="gpt-4.1-nano",
                prompt_cache_key="test-key",
            )


def test_extract_resume_profile_returns_parsed_and_usage():
    """Returns (parsed, usage) tuple on success."""
    from integrations.openai_client import extract_resume_profile
    from config.user_profile import ResumeExtractionResult

    fake_parsed = MagicMock(spec=ResumeExtractionResult)
    mock_response = MagicMock()
    mock_response.output_parsed = fake_parsed
    mock_response.usage = MagicMock()

    mock_client = MagicMock()
    mock_client.responses.parse.return_value = mock_response

    with patch("integrations.openai_client.get_openai_client", return_value=mock_client):
        parsed, usage = extract_resume_profile(
            system_prompt="test",
            resume_text="Jane Doe, Python developer",
            model="gpt-4.1-nano",
            prompt_cache_key="test-key",
        )

    assert parsed is fake_parsed
    assert usage is mock_response.usage
